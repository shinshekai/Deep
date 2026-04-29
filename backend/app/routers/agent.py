"""Agent routes: research, questions, learning (stub implementations)."""

import time
from typing import Optional
from fastapi import APIRouter
from app.state import lm_client
from app.services.question_generator import QuestionGenService
from app.services.guided_learning import GuidedLearningService
from app.services.deep_research import DeepResearchService
from app.services.content_creation import NotebookService, CoWriterService, IdeaGenService

router = APIRouter(prefix="/api/v1", tags=["agents"])


@router.post("/query")
async def query(payload: dict):
    return {"answer": "Stub response. Connect LM Studio for real answers.", "citations": []}


@router.post("/retrieve")
async def retrieve(payload: dict):
    return {"results": [], "total": 0}


@router.post("/research")
async def start_research(payload: dict):
    kb_name = payload.get("kb_name", "default_kb")
    query = payload.get("query", "General Research")
    mode = payload.get("mode", "parallel")
    retrieval_pipeline = payload.get("retrieval_pipeline", "combined")
    model_id = payload.get("model_id", "Qwen3-1.7B-Q4_K_M")
    
    dr_service = DeepResearchService(lm_client=lm_client)
    session_id = await dr_service.start_research(
        kb_name=kb_name, query=query, mode=mode, retrieval_pipeline=retrieval_pipeline, model_id=model_id
    )
    return {"session_id": session_id, "status": "RESEARCHING"}

@router.get("/research/{session_id}")
async def get_research_status(session_id: str):
    dr_service = DeepResearchService(lm_client=lm_client)
    try:
        status = dr_service.get_status(session_id)
        return status
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/questions/generate")
async def generate_questions(payload: dict):
    kb_name = payload.get("kb_name", "default_kb")
    topic = payload.get("topic", "General Knowledge")
    count = payload.get("count", 5)
    difficulty = payload.get("difficulty", "medium")
    question_type = payload.get("type", "multiple_choice")
    mode = payload.get("mode", "custom")
    reference_text = payload.get("reference_text")
    retrieval_pipeline = payload.get("retrieval_pipeline", "tree")
    
    # We could also support model selection here if provided, otherwise default.
    model_id = payload.get("model_id", "Qwen3-1.7B-Q4_K_M")

    qgen_service = QuestionGenService(lm_client=lm_client)
    
    questions = await qgen_service.generate_questions(
        kb_name=kb_name,
        topic=topic,
        count=count,
        difficulty=difficulty,
        question_type=question_type,
        mode=mode,
        reference_text=reference_text,
        retrieval_pipeline=retrieval_pipeline,
        model_id=model_id
    )
    
    return {"questions": questions, "total": len(questions)}


@router.post("/learning/start")
async def start_learning(payload: dict):
    kb_name = payload.get("kb_name", "default_kb")
    topic = payload.get("topic", "General Knowledge")
    retrieval_pipeline = payload.get("retrieval_pipeline", "tree")
    model_id = payload.get("model_id", "Qwen3-1.7B-Q4_K_M")
    
    gl_service = GuidedLearningService(lm_client=lm_client)
    session_data = await gl_service.start_session(
        kb_name=kb_name, topic=topic, retrieval_pipeline=retrieval_pipeline, model_id=model_id
    )
    return session_data

@router.post("/learning/{session_id}/page")
async def generate_learning_page(session_id: str, payload: dict):
    point_index = payload.get("point_index", 0)
    model_id = payload.get("model_id", "Qwen3-1.7B-Q4_K_M")
    
    gl_service = GuidedLearningService(lm_client=lm_client)
    html_content = await gl_service.generate_interactive_page(
        session_id=session_id, point_index=point_index, model_id=model_id
    )
    return {"html": html_content}

@router.post("/learning/{session_id}/chat")
async def learning_chat(session_id: str, payload: dict):
    point_index = payload.get("point_index", 0)
    message = payload.get("message", "")
    model_id = payload.get("model_id", "Qwen3-1.7B-Q4_K_M")
    
    gl_service = GuidedLearningService(lm_client=lm_client)
    answer = await gl_service.chat(
        session_id=session_id, point_index=point_index, user_message=message, model_id=model_id
    )
    return {"answer": answer}

@router.post("/learning/{session_id}/end")
async def end_learning(session_id: str, payload: dict):
    model_id = payload.get("model_id", "Qwen3-1.7B-Q4_K_M")
    
    gl_service = GuidedLearningService(lm_client=lm_client)
# --- Content Creation (FR-7) ---

@router.post("/notebooks")
async def create_notebook(payload: dict):
    title = payload.get("title", "New Notebook")
    desc = payload.get("description", "")
    nb_service = NotebookService()
    return nb_service.create_notebook(title, desc)

@router.get("/notebooks")
async def list_notebooks():
    nb_service = NotebookService()
    return nb_service.list_notebooks()

@router.post("/notebooks/{notebook_id}/notes")
async def add_note(notebook_id: str, payload: dict):
    content = payload.get("content", "")
    nb_service = NotebookService()
    return nb_service.add_note(notebook_id, content)

@router.post("/cowriter/edit")
async def cowriter_edit(payload: dict):
    text = payload.get("text", "")
    action = payload.get("action", "rewrite")
    instruction = payload.get("instruction", "")
    model_id = payload.get("model_id", "Qwen3-1.7B-Q4_K_M")
    
    cw_service = CoWriterService(lm_client=lm_client)
    edited = await cw_service.edit_text(text, action, instruction, model_id)
    return {"text": edited}

@router.post("/cowriter/annotate")
async def cowriter_annotate(payload: dict):
    text = payload.get("text", "")
    kb_name = payload.get("kb_name", "default_kb")
    retrieval_pipeline = payload.get("retrieval_pipeline", "tree")
    model_id = payload.get("model_id", "Qwen3-1.7B-Q4_K_M")
    
    cw_service = CoWriterService(lm_client=lm_client)
    annotated = await cw_service.auto_annotate(text, kb_name, retrieval_pipeline, model_id)
    return {"text": annotated}

@router.post("/ideagen/generate")
async def ideagen_generate(payload: dict):
    notebook_ids = payload.get("notebook_ids", [])
    model_id = payload.get("model_id", "Qwen3-1.7B-Q4_K_M")
    
    nb_service = NotebookService()
    ig_service = IdeaGenService(lm_client=lm_client, notebook_service=nb_service)
    ideas = await ig_service.generate_ideas(notebook_ids, model_id)
    return {"ideas": ideas}
