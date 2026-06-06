"""Agent routes: research, questions, learning, content creation (FR-4 to FR-7).

All endpoints accept Pydantic request models. The previous version of this
file used raw ``dict`` payloads which let an attacker smuggle arbitrary
fields into downstream services (Pydantic now rejects unknown fields via
``extra='forbid'`` on the models below). Defaults are preserved so the
existing tests and clients continue to work.
"""

import re
import time
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app import state
from app.services.question_generator import QuestionGenService
from app.services.guided_learning import GuidedLearningService
from app.services.security import safe_name
from app.services.content_creation import NotebookService, CoWriterService, IdeaGenService

router = APIRouter(prefix="/api/v1", tags=["agents"])

# Model ids that the CLI subprocess is allowed to receive. Any value
# outside this set is rejected before we ever invoke ``lms load/unload``,
# closing the command-injection vector where the user controlled a
# string passed to a subprocess.
_ALLOWED_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9._:/\-]{1,128}$")


def _validate_model_id(model_id: str) -> str:
    """Whitelist check on a model id used for the ``lms`` CLI subprocess.

    ``create_subprocess_exec`` already prevents shell injection, but
    ``lms`` itself may interpret flag-like values. Restrict the charset
    and length to keep the surface area as small as possible.
    """
    if not isinstance(model_id, str) or not _ALLOWED_MODEL_ID_RE.match(model_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid model_id — must match [A-Za-z0-9._:/-] and be ≤128 chars",
        )
    return model_id


# ── Request models ────────────────────────────────────────────────────────


class _StrictModel(BaseModel):
    """Base model: reject unknown fields so attackers can't smuggle extras."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ResearchRequest(_StrictModel):
    kb_name: str = "default_kb"
    query: str = "General Research"
    mode: Literal["parallel", "sequential", "auto"] = "parallel"
    retrieval_pipeline: Literal["tree", "hybrid", "naive", "combined"] = "combined"
    model_id: str = "Qwen3-1.7B-Q4_K_M"
    device_id: str = ""

    def sanitized(self) -> "ResearchRequest":
        """Return a copy with kb_name sanitized to a path-safe value."""
        return self.model_copy(update={"kb_name": safe_name(self.kb_name, default="default_kb")})


class QuestionsRequest(_StrictModel):
    kb_name: str = "default_kb"
    topic: str = "General Knowledge"
    count: int = Field(default=5, ge=1, le=50)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    type: Literal["multiple_choice", "open_ended", "true_false", "short_answer"] = "multiple_choice"
    mode: Literal["custom", "from_documents", "from_topic"] = "custom"
    reference_text: Optional[str] = None
    retrieval_pipeline: Literal["tree", "hybrid", "naive", "combined"] = "tree"
    model_id: str = "Qwen3-1.7B-Q4_K_M"

    def sanitized(self) -> "QuestionsRequest":
        return self.model_copy(update={"kb_name": safe_name(self.kb_name, default="default_kb")})


class LearningStartRequest(_StrictModel):
    kb_name: str = "default_kb"
    topic: str = "General Knowledge"
    retrieval_pipeline: Literal["tree", "hybrid", "naive", "combined"] = "tree"
    model_id: str = "Qwen3-1.7B-Q4_K_M"
    device_id: str = ""

    def sanitized(self) -> "LearningStartRequest":
        return self.model_copy(update={"kb_name": safe_name(self.kb_name, default="default_kb")})


class LearningPageRequest(_StrictModel):
    point_index: int = 0
    model_id: str = "Qwen3-1.7B-Q4_K_M"
    device_id: str = ""


class LearningChatRequest(_StrictModel):
    point_index: int = 0
    message: str = ""
    model_id: str = "Qwen3-1.7B-Q4_K_M"
    device_id: str = ""


class LearningEndRequest(_StrictModel):
    model_id: str = "Qwen3-1.7B-Q4_K_M"


class NotebookCreateRequest(_StrictModel):
    title: str = Field(default="New Notebook", min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    device_id: str = ""


class NoteAddRequest(_StrictModel):
    content: str = Field(default="", max_length=100_000)
    device_id: str = ""


class CoWriterEditRequest(_StrictModel):
    text: str = Field(default="", max_length=50_000)
    action: Literal["rewrite", "shorten", "expand", "tone", "summarize", "translate", "custom"] = "rewrite"
    instruction: str = Field(default="", max_length=2000)
    model_id: str = "Qwen3-1.7B-Q4_K_M"


class CoWriterAnnotateRequest(_StrictModel):
    text: str = Field(default="", max_length=50_000)
    kb_name: str = "default_kb"
    retrieval_pipeline: Literal["tree", "hybrid", "naive", "combined"] = "tree"
    model_id: str = "Qwen3-1.7B-Q4_K_M"

    def sanitized(self) -> "CoWriterAnnotateRequest":
        return self.model_copy(update={"kb_name": safe_name(self.kb_name, default="default_kb")})


class IdeaGenRequest(_StrictModel):
    notebook_ids: list[str] = Field(default_factory=list, max_length=50)
    model_id: str = "Qwen3-1.7B-Q4_K_M"

    def sanitized(self) -> "IdeaGenRequest":
        # Each notebook id is used as a filesystem path segment downstream
        return self.model_copy(update={
            "notebook_ids": [safe_name(nid, default="default") for nid in self.notebook_ids]
        })


# ── Research endpoints ────────────────────────────────────────────────────


@router.post("/research")
async def start_research(payload: ResearchRequest):
    from app.services.telemetry import trace_span
    with trace_span("agent.start_research", {
        "kb_name": payload.kb_name,
        "mode": payload.mode,
    }):
        payload = payload.sanitized()
        model_id = _validate_model_id(payload.model_id)
        dr_service = state.deep_research_service
        session_id = await dr_service.start_research(
            kb_name=payload.kb_name,
            query=payload.query,
            mode=payload.mode,
            retrieval_pipeline=payload.retrieval_pipeline,
            model_id=model_id,
            device_id=payload.device_id,
        )
    return {"session_id": session_id, "status": "RESEARCHING"}


@router.get("/research/{session_id}")
async def get_research_status(session_id: str):
    session_id = safe_name(session_id, max_len=64)
    dr_service = state.deep_research_service
    try:
        return dr_service.get_status(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found")


# ── Question generation endpoint ──────────────────────────────────────────


@router.post("/questions/generate")
async def generate_questions(payload: QuestionsRequest):
    from app.services.telemetry import trace_span
    with trace_span("agent.generate_questions", {
        "kb_name": payload.kb_name,
        "count": payload.count,
    }):
        payload = payload.sanitized()
        model_id = _validate_model_id(payload.model_id)
        qgen_service = QuestionGenService(lm_client=state.lm_client)
        questions = await qgen_service.generate_questions(
            kb_name=payload.kb_name,
            topic=payload.topic,
            count=payload.count,
            difficulty=payload.difficulty,
            question_type=payload.type,
            mode=payload.mode,
            reference_text=payload.reference_text,
            retrieval_pipeline=payload.retrieval_pipeline,
            model_id=model_id,
        )
    return {"questions": questions, "total": len(questions)}


# ── Guided learning endpoints ─────────────────────────────────────────────


@router.post("/learning/start")
async def start_learning(payload: LearningStartRequest):
    from app.services.telemetry import trace_span
    with trace_span("agent.start_learning", {"topic": payload.topic}):
        payload = payload.sanitized()
        model_id = _validate_model_id(payload.model_id)
        gl_service = GuidedLearningService(lm_client=state.lm_client)
        return await gl_service.start_session(
            kb_name=payload.kb_name,
            topic=payload.topic,
            retrieval_pipeline=payload.retrieval_pipeline,
            model_id=model_id,
            device_id=payload.device_id,
        )


@router.post("/learning/{session_id}/page")
async def generate_learning_page(session_id: str, payload: LearningPageRequest):
    session_id = safe_name(session_id, max_len=64)
    model_id = _validate_model_id(payload.model_id)
    gl_service = GuidedLearningService(lm_client=state.lm_client)
    html_content = await gl_service.generate_interactive_page(
        session_id=session_id, point_index=payload.point_index, model_id=model_id, device_id=payload.device_id
    )
    return {"html": html_content}


@router.post("/learning/{session_id}/chat")
async def learning_chat(session_id: str, payload: LearningChatRequest):
    session_id = safe_name(session_id, max_len=64)
    model_id = _validate_model_id(payload.model_id)
    gl_service = GuidedLearningService(lm_client=state.lm_client)
    answer = await gl_service.chat(
        session_id=session_id,
        point_index=payload.point_index,
        user_message=payload.message,
        model_id=model_id,
        device_id=payload.device_id,
    )
    return {"answer": answer}


@router.post("/learning/{session_id}/end")
async def end_learning(session_id: str, payload: LearningEndRequest):
    session_id = safe_name(session_id, max_len=64)
    model_id = _validate_model_id(payload.model_id)
    gl_service = GuidedLearningService(lm_client=state.lm_client)
    return await gl_service.end_session(session_id, model_id=model_id)


# ── Content Creation (FR-7) ───────────────────────────────────────────────


@router.post("/notebooks")
async def create_notebook(payload: NotebookCreateRequest):
    nb_service = NotebookService()
    try:
        return nb_service.create_notebook(payload.title, payload.description, payload.device_id)
    except OSError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Could not persist notebook: {e}",
        )


@router.get("/notebooks")
async def list_notebooks():
    nb_service = NotebookService()
    return nb_service.list_notebooks()


@router.post("/notebooks/{notebook_id}/notes")
async def add_note(notebook_id: str, payload: NoteAddRequest):
    notebook_id = safe_name(notebook_id, max_len=64)
    nb_service = NotebookService()
    try:
        return nb_service.add_note(notebook_id, payload.content, device_id=payload.device_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Notebook not found.")
    except ValueError as e:
        # Corrupted notebook — surface as 500 with a generic message so
        # the client doesn't see filesystem paths.
        raise HTTPException(status_code=500, detail="Notebook is corrupted.")
    except OSError as e:
        raise HTTPException(status_code=503, detail=f"Could not persist note: {e}")


@router.post("/cowriter/edit")
async def cowriter_edit(payload: CoWriterEditRequest):
    model_id = _validate_model_id(payload.model_id)
    cw_service = CoWriterService(lm_client=state.lm_client)
    result = await cw_service.edit_text(
        payload.text, payload.action, payload.instruction, model_id
    )
    return {"text": result["text"], "provenance": result["provenance"]}


@router.post("/cowriter/annotate")
async def cowriter_annotate(payload: CoWriterAnnotateRequest):
    payload = payload.sanitized()
    model_id = _validate_model_id(payload.model_id)
    cw_service = CoWriterService(lm_client=state.lm_client)
    result = await cw_service.auto_annotate(
        payload.text, payload.kb_name, payload.retrieval_pipeline, model_id
    )
    return {"text": result["text"], "provenance": result["provenance"]}


@router.post("/ideagen/generate")
async def ideagen_generate(payload: IdeaGenRequest):
    payload = payload.sanitized()
    model_id = _validate_model_id(payload.model_id)
    nb_service = NotebookService()
    ig_service = IdeaGenService(lm_client=state.lm_client, notebook_service=nb_service)
    ideas = await ig_service.generate_ideas(payload.notebook_ids, model_id)
    return {"ideas": ideas}
