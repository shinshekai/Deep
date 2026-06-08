"""Knowledge Base routes."""

import asyncio
import json
import logging
import os
import shutil
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app import state
from app.config import get_settings
from app.services.document_processor import extract_text
from app.services.security import resolve_within, safe_doc_id, safe_name
from app.services.task_registry import _global_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "knowledge_bases"
KB_UPLOADS_DIR = DATA_DIR / "uploads"
REGISTRY_PATH = DATA_DIR / "registry.json"

# File size limit: 50 MB. Anything larger is rejected before OOM.
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Minimum free-disk ratio for accepting a new upload. Below this, we
# reject the request with 507 Insufficient Storage so the user can
# clean up before we start a write that will fail halfway through.
MIN_DISK_FREE_RATIO = 0.10  # 10% of total disk must be free

# Whitelist of accepted file extensions. We keep this small on purpose
# so the document processor doesn't get handed an arbitrary binary that
# could trigger parser bugs. Add to this set deliberately.
ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pdf",
        ".txt",
        ".md",
        ".markdown",
        ".docx",
        ".pptx",
        ".xlsx",
        ".html",
        ".htm",
        ".rtf",
        ".odt",
        ".epub",
        ".msg",
        ".eml",
        ".csv",
        ".tsv",
        ".json",
        ".xml",
        ".log",
    }
)

# MIME types we will accept. Empty Content-Type is allowed because the
# browser may omit it on simple form uploads.
ALLOWED_MIME_PREFIXES: tuple[str, ...] = (
    "application/pdf",
    "text/",
    "application/json",
    "application/xml",
    "application/vnd.openxmlformats-officedocument",
    "application/vnd.ms-excel",
    "application/vnd.oasis.opendocument",
    "application/epub+zip",
    "application/rtf",
    "application/vnd.ms-outlook",
    "message/rfc822",
)

# Lock file for atomic registry writes. ``filelock`` is cross-platform
# (uses ``fcntl`` on POSIX and ``msvcrt`` on Windows) and survives
# between processes — important for the upload worker and the HTTP
# server, which may run in separate Python interpreters.
_REGISTRY_LOCK_PATH = DATA_DIR / "registry.lock"

_tasks: dict = {}

# In-process lock for serializing mutations to _kb_registry.  The
# file-level ``_acquire_registry_lock`` handles inter-process safety;
# this asyncio.Lock handles concurrency *within* a single event loop.
_registry_lock = asyncio.Lock()


def _acquire_registry_lock():
    """Acquire an inter-process lock for registry writes.

    Returns a ``filelock.FileLock`` context manager. ``filelock``
    serializes writers across processes and threads on both POSIX
    (``fcntl.flock``) and Windows (``msvcrt.locking``). Falls back to
    a no-op if the package is missing — preferable to a hard crash on
    a stripped-down install.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from filelock import FileLock

        # 30s timeout: long enough for legitimate concurrent writers
        # (e.g. upload worker + HTTP request) but short enough that a
        # crashed writer doesn't deadlock the registry forever.
        return FileLock(str(_REGISTRY_LOCK_PATH), timeout=30)
    except ImportError:
        logger.warning("filelock not available — registry writes are not serialized")

        # No-op context manager
        class _NullLock:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        return _NullLock()


def _load_registry() -> dict:
    if REGISTRY_PATH.exists():
        try:
            return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load KB registry: {e}")
    return {}


def _save_registry():
    """Atomically write the KB registry under an exclusive file lock.

    Uses tempfile + os.replace for crash-safety so a partial write
    never corrupts the existing registry.
    """
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with _acquire_registry_lock():
            # Re-read inside the lock so we don't clobber a concurrent writer
            current = _load_registry()
            current.update(_kb_registry)
            _kb_registry.clear()
            _kb_registry.update(current)

            tmp_path = REGISTRY_PATH.with_suffix(".json.tmp")
            tmp_path.write_text(json.dumps(_kb_registry, indent=2), encoding="utf-8")
            os.replace(tmp_path, REGISTRY_PATH)
    except Exception as e:
        logger.error(f"Failed to save KB registry: {e}", exc_info=True)


_kb_registry: dict = _load_registry()


def _check_disk_space(path: Path = DATA_DIR) -> tuple[bool, dict]:
    """Check whether the disk containing ``path`` has enough free space
    to safely accept another upload.

    Returns ``(ok, info)`` where ``ok`` is True when free space is
    above ``MIN_DISK_FREE_RATIO`` of the partition total, and ``info``
    is a small dict with ``free_bytes``, ``total_bytes`` and
    ``free_ratio`` for the caller's log line.
    """
    try:
        usage = shutil.disk_usage(path)
    except OSError as e:
        # If we can't determine disk usage (e.g. path on a network
        # share that's offline) we fail open — let the upload proceed
        # and surface the real error on write.
        logger.warning(f"disk_usage failed for {path}: {e}")
        return True, {"free_bytes": -1, "total_bytes": -1, "free_ratio": -1.0}
    free_ratio = usage.free / usage.total if usage.total else 0.0
    return (
        free_ratio >= MIN_DISK_FREE_RATIO,
        {
            "free_bytes": usage.free,
            "total_bytes": usage.total,
            "free_ratio": free_ratio,
        },
    )


def _ensure_kb(kb_name: str):
    """Ensure KB directories exist and register the KB.

    The ``kb_name`` must already be sanitized via ``safe_name``.
    """
    if not safe_name(kb_name):
        raise HTTPException(status_code=400, detail="Invalid knowledge base name")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    KB_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    kb_dir = DATA_DIR / kb_name
    pageindex_dir = kb_dir / "pageindex"
    uploads_kb_dir = KB_UPLOADS_DIR / kb_name

    # Defense in depth: resolve and verify all dirs live under DATA_DIR
    resolve_within(DATA_DIR, kb_dir)
    resolve_within(DATA_DIR, pageindex_dir)
    resolve_within(DATA_DIR, uploads_kb_dir)

    kb_dir.mkdir(parents=True, exist_ok=True)
    pageindex_dir.mkdir(parents=True, exist_ok=True)
    uploads_kb_dir.mkdir(parents=True, exist_ok=True)

    if kb_name not in _kb_registry:
        _kb_registry[kb_name] = {
            "name": kb_name,
            "status": "active",
            "total_pages": 0,
            "total_docs": 0,
            "created_at": time.time(),
        }
        _save_registry()


# Ensure default knowledge base exists at startup
_ensure_kb("default")


async def _build_vectors(
    doc_content: str | dict,
    doc_id: str,
    kb_name: str,
    embedding_service,
    text_chunker,
    vector_kb_service,
) -> int:
    """Chunk text, embed, and store vectors. Returns chunk count or 0 on failure."""
    try:
        import numpy as np

        # Extract string text — extract_text may return dict or str depending on format
        if isinstance(doc_content, dict):
            text_to_chunk = doc_content.get("content", "") or ""
        else:
            text_to_chunk = doc_content or ""

        chunks = text_chunker.chunk_text(text_to_chunk, doc_id=doc_id, kb_name=kb_name)
        if not chunks:
            logger.info(f"No chunks produced for {doc_id}")
            return 0

        texts = [c.text for c in chunks]
        vectors = await embedding_service.embed_texts(texts)

        if not vectors or all(len(v) == 0 for v in vectors):
            logger.warning(f"Embedding returned empty for {doc_id} — skipping vector store")
            return 0

        chunk_dicts = [c.to_dict() for c in chunks]
        emb_array = np.array(
            [v if v else [0.0] * len(vectors[0]) for v in vectors],
            dtype=np.float32,
        )
        count = await vector_kb_service.store_vectors(kb_name, doc_id, emb_array, chunk_dicts)
        return count
    except Exception as e:
        logger.error(f"_build_vectors failed for {doc_id}: {e}", exc_info=True)
        return 0


async def _process_document(
    task_id: str,
    file_bytes: bytes,
    doc_id: str,
    kb_name: str,
    pageindex_generator,
    embedding_service=None,
    text_chunker=None,
    vector_kb_service=None,
):
    """Background task: extract text, build PageIndex tree + vector embeddings in parallel."""
    _tasks[task_id]["status"] = "processing"
    _tasks[task_id]["progress"] = 10

    try:
        # Save file
        upload_path = KB_UPLOADS_DIR / kb_name / doc_id
        resolve_within(KB_UPLOADS_DIR, upload_path)
        upload_path.write_bytes(file_bytes)

        _tasks[task_id]["progress"] = 20

        # Extract text
        doc_content = await extract_text(upload_path)
        if doc_content is None:
            _tasks[task_id]["status"] = "failed"
            _tasks[task_id]["progress"] = 0
            _tasks[task_id]["message"] = "Failed to extract text from document"
            return

        _tasks[task_id]["progress"] = 35

        # Determine model
        settings = get_settings()
        model_id = settings.pageindex_model or settings.llm_model or "Qwen3-4B-Q4_K_M"

        _tasks[task_id]["progress"] = 32

        # Run PageIndex tree FIRST (sequential), then vector+ARA in parallel
        _tasks[task_id]["message"] = "Generating PageIndex tree..."
        tree = await pageindex_generator.build_tree(doc_content, model_id, doc_id)
        _tasks[task_id]["progress"] = 50
        _tasks[task_id]["message"] = "Building vectors and ARA..."

        run_vectors = (
            embedding_service is not None
            and text_chunker is not None
            and vector_kb_service is not None
        )

        # Run remaining work in parallel: vector building + ARA
        parallel_tasks = []
        if run_vectors:
            parallel_tasks.append(
                _build_vectors(
                    doc_content, doc_id, kb_name, embedding_service, text_chunker, vector_kb_service
                )
            )

        # Add ARA compilation
        from app.services.ara_compiler import ARACompiler

        ara_compiler = ARACompiler(state.lm_client)
        parallel_tasks.append(
            ara_compiler.compile(doc_id=doc_id, text=doc_content, model_id=model_id, title=doc_id)
        )

        results = await asyncio.gather(*parallel_tasks, return_exceptions=True)
        vector_count = results[0] if run_vectors else 0
        ara_result = results[-1]

        if isinstance(vector_count, Exception):
            logger.error(f"Vector pipeline error (non-fatal): {vector_count}")
            vector_count = 0

        _tasks[task_id]["progress"] = 90

        # Write tree
        tree_path = DATA_DIR / kb_name / "pageindex" / f"{doc_id}.json"
        resolve_within(DATA_DIR, tree_path)
        tree_path.parent.mkdir(parents=True, exist_ok=True)
        tree_path.write_text(json.dumps(tree, indent=2))

        # Save ARA artifact if successful
        ara_status = "skipped"
        if not isinstance(ara_result, Exception):
            ara_compiler.persist(ara_result, DATA_DIR / kb_name)
            ara_status = "completed"
        else:
            logger.error(f"ARA compilation failed (non-fatal): {ara_result}")
            ara_status = f"failed ({ara_result})"

        _tasks[task_id]["status"] = "complete"
        _tasks[task_id]["progress"] = 100

        len(tree.get("root", {}).get("children", []))
        tree_pages = tree.get("total_pages", 0)

        msg_parts = [f"PageIndex tree ({tree_pages} pages)"]
        if vector_count:
            msg_parts.append(f"Vector KB ({vector_count} chunks)")
        msg_parts.append(f"ARA compilation: {ara_status}")

        _tasks[task_id]["message"] = "Generated: " + ", ".join(msg_parts)

        # Update KB registry
        async with _registry_lock:
            if kb_name in _kb_registry:
                _kb_registry[kb_name]["total_docs"] += 1
                _kb_registry[kb_name]["total_pages"] += tree_pages
                _save_registry()

    except Exception as e:
        logger.error(f"Document processing failed: {e}", exc_info=True)
        _tasks[task_id]["status"] = "failed"
        _tasks[task_id]["progress"] = 0
        _tasks[task_id]["message"] = str(e)


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    kb_name: str = Form("default"),
):
    """Upload document and start PageIndex tree generation."""
    # Sanitize inputs to prevent path traversal
    kb_name = safe_name(kb_name)
    if not kb_name:
        raise HTTPException(status_code=400, detail="Invalid kb_name")

    # Derive doc_id from filename (basename only) and sanitize
    raw_name = Path(file.filename or "").name or f"doc_{int(time.time())}"
    doc_id = safe_doc_id(raw_name, default=f"doc_{int(time.time())}")
    if not doc_id:
        raise HTTPException(status_code=400, detail="Invalid document filename")

    # ── File-type validation ───────────────────────────────────────
    # Two-layer check: (1) extension must be in the allowlist and
    # (2) declared MIME type, if present, must look like a document.
    # Either check failing rejects the upload with 415 Unsupported
    # Media Type so the caller can correct the request.
    extension = Path(raw_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"File extension {extension!r} is not allowed. "
                f"Accepted: {sorted(ALLOWED_EXTENSIONS)}"
            ),
        )
    declared_mime = (file.content_type or "").lower()
    if declared_mime and not any(
        declared_mime.startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES
    ):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Declared Content-Type {declared_mime!r} is not in the document MIME allowlist."
            ),
        )

    _ensure_kb(kb_name)

    # Disk-space guard — refuse the upload before we start writing if
    # the partition is below MIN_DISK_FREE_RATIO. Better a fast 507 than
    # a half-written 25 GB file that fails on close().
    ok, info = _check_disk_space()
    if not ok:
        free_mb = info["free_bytes"] / (1024 * 1024)
        total_mb = info["total_bytes"] / (1024 * 1024)
        logger.warning(
            f"Upload rejected: disk full ({free_mb:.0f} MB free of "
            f"{total_mb:.0f} MB = {info['free_ratio'] * 100:.1f}%)"
        )
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail=(
                f"Refusing upload: only {free_mb:.0f} MB free "
                f"({info['free_ratio'] * 100:.1f}% of disk). "
                "Free up space and try again."
            ),
        )

    # Read with explicit size guard — prevents OOM on huge uploads.
    # We accumulate in chunks and reject as soon as we exceed the limit.
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)  # 1 MB
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
            )
        chunks.append(chunk)
    file_bytes = b"".join(chunks)

    task_id = f"task_{uuid.uuid4().hex[:12]}"

    # Check if LM Studio is available
    health_ok = await state.lm_client.check_health()

    if health_ok:
        # Real processing via background task
        _tasks[task_id] = {
            "task_id": task_id,
            "status": "processing",
            "progress": 5,
            "message": "Starting document processing",
            "doc_id": doc_id,
            "kb_name": kb_name,
        }

        # Fire and forget -- client polls via /tasks/{task_id}
        async def _with_timeout():
            try:
                await asyncio.wait_for(
                    _process_document(
                        task_id,
                        file_bytes,
                        doc_id,
                        kb_name,
                        state.pageindex_generator,
                        embedding_service=state.embedding_service,
                        text_chunker=state.text_chunker,
                        vector_kb_service=state.vector_kb_service,
                    ),
                    timeout=600.0,
                )
            except asyncio.TimeoutError:
                _tasks[task_id]["status"] = "failed"
                _tasks[task_id]["progress"] = 0
                _tasks[task_id]["message"] = "Document processing timed out after 10 minutes"

        _global_registry.spawn(_with_timeout())
    else:
        # Fallback: create a minimal stub tree
        tree = {
            "doc_id": doc_id,
            "title": doc_id,
            "total_pages": 0,
            "root": {
                "node_id": "root",
                "title": "Document (LLM not available)",
                "summary": "LM Studio is not connected. This is a stub tree.",
                "start_index": 0,
                "end_index": 0,
                "page_start": 1,
                "page_end": 1,
                "children": [],
            },
        }
        tree_path = DATA_DIR / kb_name / "pageindex" / f"{doc_id}.json"
        resolve_within(DATA_DIR, tree_path)
        tree_path.parent.mkdir(parents=True, exist_ok=True)
        tree_path.write_text(json.dumps(tree, indent=2))

        async with _registry_lock:
            _kb_registry[kb_name]["total_docs"] += 1
            _save_registry()
        _tasks[task_id] = {
            "task_id": task_id,
            "status": "complete",
            "progress": 100,
            "message": "Stub tree created (LM Studio not connected)",
            "doc_id": doc_id,
            "kb_name": kb_name,
        }

    _audit_upload(kb_name, doc_id, len(file_bytes))
    return {"task_id": task_id, "status": "processing", "doc_id": doc_id}


# Helper module-level hook for upload audit (avoids repeating the
# import inside the handler).
def _audit_upload(kb_name: str, doc_id: str, size_bytes: int) -> None:
    from app.services.audit import audit

    audit("kb.uploaded", kb_name=kb_name, doc_id=doc_id, size_bytes=size_bytes)


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    return _tasks.get(
        task_id,
        {
            "task_id": task_id,
            "status": "unknown",
            "progress": 0,
        },
    )


@router.get("/bases")
async def list_knowledge_bases():
    return list(_kb_registry.values())


@router.post("/bases")
async def create_knowledge_base(kb_name: str = Form(...)):
    """Create a new empty knowledge base."""
    kb_name = safe_name(kb_name)
    if not kb_name:
        raise HTTPException(status_code=400, detail="Invalid knowledge base name")
    _ensure_kb(kb_name)
    from app.services.audit import audit

    audit("kb.created", kb_name=kb_name)
    return _kb_registry[kb_name]


@router.get("/bases/{kb_name}")
async def get_knowledge_base(kb_name: str):
    # Sanitize on the way in — even though routers don't enforce
    # match-traversal-safe by default, the value still reaches disk ops.
    safe = safe_name(kb_name)
    if not safe:
        raise HTTPException(status_code=400, detail="Invalid knowledge base name")
    return _kb_registry.get(
        safe,
        {
            "name": safe,
            "status": "inactive",
            "total_pages": 0,
            "total_docs": 0,
        },
    )


@router.delete("/bases/{kb_name}")
async def delete_knowledge_base(kb_name: str):
    """Delete a knowledge base directory and its registry entry."""
    kb_name = safe_name(kb_name)
    if not kb_name:
        raise HTTPException(status_code=400, detail="Invalid knowledge base name")

    kb_path = DATA_DIR / kb_name
    # Resolve and verify the path is inside DATA_DIR before deletion.
    # This is the critical fix for the arbitrary-directory-deletion bug.
    try:
        resolve_within(DATA_DIR, kb_path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid knowledge base name")

    if kb_path.exists():
        shutil.rmtree(kb_path)
    async with _registry_lock:
        _kb_registry.pop(kb_name, None)
        _save_registry()
    logger.info(f"Deleted knowledge base: {kb_name}")
    from app.services.audit import audit

    audit("kb.deleted", kb_name=kb_name)
    return {"deleted": True, "kb_name": kb_name}


@router.get("/bases/{kb_name}/pageindex/{doc_id}")
async def get_pageindex_tree(kb_name: str, doc_id: str):
    safe_kb = safe_name(kb_name)
    safe_doc = safe_doc_id(doc_id)
    if not safe_kb or not safe_doc:
        return {
            "doc_id": doc_id,
            "title": doc_id,
            "total_pages": 0,
            "root": {
                "node_id": "root",
                "title": "Not Found",
                "summary": f"Invalid identifiers for {doc_id} in {kb_name}",
                "start_index": 0,
                "end_index": 0,
                "page_start": 1,
                "page_end": 1,
                "children": [],
            },
        }
    tree_path = DATA_DIR / safe_kb / "pageindex" / f"{safe_doc}.json"
    if tree_path.exists():
        return json.loads(tree_path.read_text())
    return {
        "doc_id": doc_id,
        "title": doc_id,
        "total_pages": 0,
        "root": {
            "node_id": "root",
            "title": "Not Found",
            "summary": f"No tree for {doc_id} in {kb_name}",
            "start_index": 0,
            "end_index": 0,
            "page_start": 1,
            "page_end": 1,
            "children": [],
        },
    }


@router.delete("/bases/{kb_name}/documents/{doc_id}", status_code=204)
async def delete_document(kb_name: str, doc_id: str):
    """Remove a single document from a knowledge base.

    Deletes:
    - Tree JSON from pageindex/ directory
    - Raw upload file from uploads/ directory
    - Vector data (if exists) from vectors/ directory
    - Updates KB registry counts

    Returns 204 on success, 404 if document not found.
    """
    safe_kb = safe_name(kb_name)
    safe_doc = safe_doc_id(doc_id)
    if not safe_kb or not safe_doc:
        raise HTTPException(status_code=400, detail="Invalid identifiers")

    tree_path = DATA_DIR / safe_kb / "pageindex" / f"{safe_doc}.json"
    upload_dir = KB_UPLOADS_DIR / safe_kb

    # Check if document exists (tree JSON is the canonical indicator)
    if not tree_path.exists():
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found in {kb_name}")

    # Load tree data before deletion to get page count for registry update
    page_count = 0
    try:
        tree_data = json.loads(tree_path.read_text(encoding="utf-8"))
        page_count = tree_data.get("total_pages", 0)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Could not read tree data for {doc_id}: {e}")

    # Delete tree JSON file
    try:
        tree_path.unlink()
        logger.info(f"Deleted tree JSON for {safe_kb}/{safe_doc}")
    except OSError as e:
        logger.error(f"Failed to delete tree JSON for {doc_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete document data")

    # Find and delete raw upload file (check various extensions)
    upload_patterns = [
        upload_dir / safe_doc,  # No extension
        upload_dir / f"{safe_doc}.pdf",
        upload_dir / f"{safe_doc}.txt",
        upload_dir / f"{safe_doc}.md",
    ]
    # Also check for any file starting with doc_id
    if upload_dir.exists():
        for f in upload_dir.iterdir():
            if f.name.startswith(safe_doc):
                upload_patterns.append(f)

    for upload_path in set(upload_patterns):
        try:
            if upload_path.exists():
                # Verify each upload path is inside the upload dir
                try:
                    resolve_within(KB_UPLOADS_DIR, upload_path)
                except ValueError:
                    continue
                upload_path.unlink()
                logger.info(f"Deleted upload file: {upload_path}")
        except OSError as e:
            logger.warning(f"Failed to delete upload file {upload_path}: {e}")

    # Delete vector data if exists
    try:
        state.vector_kb_service.delete_vectors(safe_kb, safe_doc)
    except Exception as e:
        logger.warning(f"delete_document: could not remove vectors for {doc_id}: {e}")

    # Update KB registry
    if safe_kb in _kb_registry:
        kb = _kb_registry[safe_kb]
        if kb["total_docs"] > 0:
            kb["total_docs"] -= 1
        if page_count > 0 and kb.get("total_pages", 0) >= page_count:
            kb["total_pages"] -= page_count
        _save_registry()
        logger.info(
            f"Updated KB registry for {safe_kb}: docs={kb['total_docs']}, "
            f"pages={kb.get('total_pages', 0)}"
        )

    from app.services.audit import audit

    audit("kb.document_deleted", kb_name=safe_kb, doc_id=safe_doc, page_count=page_count)

    # Return 204 No Content (status_code=204 set on router)
    return None
