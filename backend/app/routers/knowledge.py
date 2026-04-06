"""Knowledge Base routes."""

import asyncio
import json
import logging
import time
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form

from app.config import get_settings
from app.services.document_processor import extract_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

DATA_DIR = Path("data/knowledge_bases")
KB_UPLOADS_DIR = DATA_DIR / "uploads"
_tasks: dict = {}
_kb_registry: dict = {}


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


async def _process_document(
    task_id: str,
    file_bytes: bytes,
    doc_id: str,
    kb_name: str,
    pageindex_generator,
):
    """Background task: extract text and build PageIndex tree."""
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

        _tasks[task_id]["progress"] = 40

        # Determine model
        settings = get_settings()
        model_id = settings.pageindex_model or settings.llm_model or "Qwen3-4B-Q4_K_M"

        # Build tree
        tree = await pageindex_generator.build_tree(doc_content, model_id, doc_id)
        if tree is None:
            raise ValueError("Tree generation returned None")

        _tasks[task_id]["progress"] = 90

        # Write tree
        tree_path = DATA_DIR / kb_name / "pageindex" / f"{doc_id}.json"
        tree_path.parent.mkdir(parents=True, exist_ok=True)
        tree_path.write_text(json.dumps(tree, indent=2))

        _tasks[task_id]["status"] = "complete"
        _tasks[task_id]["progress"] = 100
        _tasks[task_id]["message"] = (
            f"Generated PageIndex tree with {tree.get('total_pages', 0)} pages and "
            f"{len(tree.get('root', {}).get('children', []))} top-level sections"
        )

        # Update KB registry
        if kb_name in _kb_registry:
            _kb_registry[kb_name]["total_docs"] += 1
            _kb_registry[kb_name]["total_pages"] += tree.get("total_pages", 0)

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
    _ensure_kb(kb_name)

    doc_id = file.filename or f"doc_{int(time.time())}"
    file_bytes = await file.read()

    task_id = f"task_{int(time.time() * 1000)}"

    # Check if LM Studio is available
    from app.main import lm_client
    health_ok = await lm_client.check_health()

    if health_ok:
        # Real processing via background task
        from app.main import pageindex_generator
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
            task_id, file_bytes, doc_id, kb_name, pageindex_generator
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
