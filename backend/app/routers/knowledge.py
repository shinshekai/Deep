"""Knowledge Base routes."""

import asyncio
import json
import logging
import re
import time
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form

from app.config import get_settings
from app.services.document_processor import extract_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "knowledge_bases"
KB_UPLOADS_DIR = DATA_DIR / "uploads"
REGISTRY_PATH = DATA_DIR / "registry.json"

_tasks: dict = {}

def _load_registry() -> dict:
    if REGISTRY_PATH.exists():
        try:
            return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to load KB registry: {e}")
    return {}

def _save_registry():
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        REGISTRY_PATH.write_text(json.dumps(_kb_registry, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to save KB registry: {e}")

_kb_registry: dict = _load_registry()


def _ensure_kb(kb_name: str):
    """Ensure KB directories exist and register the KB."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    KB_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / kb_name / "pageindex").mkdir(parents=True, exist_ok=True)
    (KB_UPLOADS_DIR / kb_name).mkdir(parents=True, exist_ok=True)
    if kb_name not in _kb_registry:
        _kb_registry[kb_name] = {
            "name": kb_name, "status": "active",
            "total_pages": 0, "total_docs": 0,
            "created_at": time.time(),
        }
        _save_registry()


async def _build_vectors(
    doc_content: str,
    doc_id: str,
    kb_name: str,
    embedding_service,
    text_chunker,
    vector_kb_service,
) -> int:
    """Chunk text, embed, and store vectors. Returns chunk count or 0 on failure."""
    try:
        import numpy as np  # noqa: PLC0415

        chunks = text_chunker.chunk_text(doc_content, doc_id=doc_id, kb_name=kb_name)
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

        # Run PageIndex tree + vector embedding + ARA compilation in PARALLEL
        tasks_to_run = [pageindex_generator.build_tree(doc_content, model_id, doc_id)]
        run_vectors = (
            embedding_service is not None
            and text_chunker is not None
            and vector_kb_service is not None
        )
        if run_vectors:
            tasks_to_run.append(
                _build_vectors(doc_content, doc_id, kb_name,
                               embedding_service, text_chunker, vector_kb_service)
            )

        # Add ARA compilation
        from app.services.ara_compiler import ARACompiler
        from app.state import lm_client
        ara_compiler = ARACompiler(lm_client)
        tasks_to_run.append(
            ara_compiler.compile(doc_id=doc_id, text=doc_content, model_id=model_id, title=doc_id)
        )

        results = await asyncio.gather(*tasks_to_run, return_exceptions=True)
        tree = results[0]
        vector_count = results[1] if run_vectors and len(results) > 2 else 0
        ara_result = results[-1]

        if isinstance(tree, Exception):
            raise tree
        if tree is None:
            raise ValueError("Tree generation returned None")
        if isinstance(vector_count, Exception):
            logger.error(f"Vector pipeline error (non-fatal): {vector_count}")
            vector_count = 0

        _tasks[task_id]["progress"] = 90

        # Write tree
        tree_path = DATA_DIR / kb_name / "pageindex" / f"{doc_id}.json"
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

        tree_sections = len(tree.get("root", {}).get("children", []))
        tree_pages = tree.get("total_pages", 0)
        
        msg_parts = [f"PageIndex tree ({tree_pages} pages)"]
        if vector_count:
            msg_parts.append(f"Vector KB ({vector_count} chunks)")
        msg_parts.append(f"ARA compilation: {ara_status}")
        
        _tasks[task_id]["message"] = "Generated: " + ", ".join(msg_parts)

        # Update KB registry
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
    kb_name = re.sub(r"[^a-zA-Z0-9_-]", "_", kb_name) or "default"
    doc_id = Path(file.filename or f"doc_{int(time.time())}").name
    _ensure_kb(kb_name)
    file_bytes = await file.read()

    task_id = f"task_{int(time.time() * 1000)}"

    # Check if LM Studio is available
    from app.state import lm_client
    health_ok = await lm_client.check_health()

    if health_ok:
        # Real processing via background task
        from app.state import pageindex_generator, embedding_service, text_chunker, vector_kb_service
        _tasks[task_id] = {
            "task_id": task_id,
            "status": "processing",
            "progress": 5,
            "message": "Starting document processing",
            "doc_id": doc_id,
            "kb_name": kb_name,
        }
        # Fire and forget -- client polls via /tasks/{task_id}
        asyncio.create_task(_process_document(
            task_id, file_bytes, doc_id, kb_name, pageindex_generator,
            embedding_service=embedding_service,
            text_chunker=text_chunker,
            vector_kb_service=vector_kb_service,
        ))
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
        tree_path.parent.mkdir(parents=True, exist_ok=True)
        tree_path.write_text(json.dumps(tree, indent=2))

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

    return {"task_id": task_id, "status": "processing", "doc_id": doc_id}


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    return _tasks.get(task_id, {
        "task_id": task_id, "status": "unknown", "progress": 0,
    })


@router.get("/bases")
async def list_knowledge_bases():
    return list(_kb_registry.values())


@router.get("/bases/{kb_name}")
async def get_knowledge_base(kb_name: str):
    return _kb_registry.get(kb_name, {
        "name": kb_name, "status": "inactive",
        "total_pages": 0, "total_docs": 0,
    })


@router.delete("/bases/{kb_name}")
async def delete_knowledge_base(kb_name: str):
    import shutil
    kb_path = DATA_DIR / kb_name
    if kb_path.exists():
        shutil.rmtree(kb_path)
    _kb_registry.pop(kb_name, None)
    _save_registry()
    return {"deleted": True, "kb_name": kb_name}


@router.get("/bases/{kb_name}/pageindex/{doc_id}")
async def get_pageindex_tree(kb_name: str, doc_id: str):
    tree_path = DATA_DIR / kb_name / "pageindex" / f"{doc_id}.json"
    if tree_path.exists():
        return json.loads(tree_path.read_text())
    return {
        "doc_id": doc_id, "title": doc_id, "total_pages": 0,
        "root": {
            "node_id": "root", "title": "Not Found",
            "summary": f"No tree for {doc_id} in {kb_name}",
            "start_index": 0, "end_index": 0,
            "page_start": 1, "page_end": 1, "children": [],
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
    from fastapi import HTTPException

    tree_path = DATA_DIR / kb_name / "pageindex" / f"{doc_id}.json"
    upload_dir = KB_UPLOADS_DIR / kb_name

    # Check if document exists (tree JSON is the canonical indicator)
    if not tree_path.exists():
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found in {kb_name}")

    # Load tree data before deletion to get page count for registry update
    page_count = 0
    try:
        tree_data = json.loads(tree_path.read_text(encoding="utf-8"))
        page_count = tree_data.get("total_pages", 0)
    except Exception as e:
        logger.warning(f"Could not read tree data for {doc_id}: {e}")

    # Delete tree JSON file
    try:
        tree_path.unlink()
        logger.info(f"Deleted tree JSON for {kb_name}/{doc_id}")
    except Exception as e:
        logger.error(f"Failed to delete tree JSON for {doc_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete document data")

    # Find and delete raw upload file (check various extensions)
    upload_patterns = [
        upload_dir / doc_id,  # No extension
        upload_dir / f"{doc_id}.pdf",
        upload_dir / f"{doc_id}.txt",
        upload_dir / f"{doc_id}.md",
    ]
    # Also check for any file starting with doc_id
    if upload_dir.exists():
        for f in upload_dir.iterdir():
            if f.name.startswith(doc_id):
                upload_patterns.append(f)

    for upload_path in set(upload_patterns):
        try:
            if upload_path.exists():
                upload_path.unlink()
                logger.info(f"Deleted upload file: {upload_path}")
        except Exception as e:
            logger.warning(f"Failed to delete upload file {upload_path}: {e}")

    # Delete vector data if exists
    try:
        from app.state import vector_kb_service
        vector_kb_service.delete_vectors(kb_name, doc_id)
    except Exception as e:
        logger.warning(f"delete_document: could not remove vectors for {doc_id}: {e}")

    # Update KB registry
    if kb_name in _kb_registry:
        kb = _kb_registry[kb_name]
        if kb["total_docs"] > 0:
            kb["total_docs"] -= 1
        if page_count > 0 and kb.get("total_pages", 0) >= page_count:
            kb["total_pages"] -= page_count
        _save_registry()
        logger.info(f"Updated KB registry for {kb_name}: docs={kb['total_docs']}, pages={kb.get('total_pages', 0)}")

    # Return 204 No Content (status_code=204 set on router)
    return None
