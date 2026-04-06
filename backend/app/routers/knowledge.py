"""Knowledge Base routes."""
from fastapi import APIRouter, UploadFile, File, Form
import time
from pathlib import Path
import json

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

DATA_DIR = Path("data/knowledge_bases")
_tasks: dict = {}
_kb_registry: dict = {}

def _ensure_kb(kb_name: str):
    (DATA_DIR / kb_name / "pageindex").mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if kb_name not in _kb_registry:
        _kb_registry[kb_name] = {
            "name": kb_name, "status": "active",
            "total_pages": 0, "total_docs": 0,
            "created_at": time.time(),
        }

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    kb_name: str = Form("default"),
    chunk_size: int = Form(512),
    chunk_overlap: int = Form(64),
):
    _ensure_kb(kb_name)
    task_id = f"task_{int(time.time() * 1000)}"
    doc_id = file.filename or f"doc_{task_id}"
    _tasks[task_id] = {
        "task_id": task_id, "status": "complete", "progress": 100,
        "message": "Stub — connect LM Studio for real processing",
        "doc_id": doc_id, "kb_name": kb_name,
    }
    tree_path = DATA_DIR / kb_name / "pageindex" / f"{doc_id}.json"
    if not tree_path.exists():
        tree_path.write_text(json.dumps({
            "doc_id": doc_id,
            "tree": {"node_id": "root", "title": "Root", "summary": "Stub", "children": []},
        }))
    _kb_registry[kb_name]["total_docs"] += 1
    return {"task_id": task_id, "status": "processing"}

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
        import json as j
        return j.loads(tree_path.read_text())
    return {"doc_id": doc_id, "tree": {
        "node_id": "root", "title": "Not Found",
        "summary": f"No tree for {doc_id} in {kb_name}", "children": [],
    }}
