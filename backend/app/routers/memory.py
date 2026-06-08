import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


class RecallRequest(BaseModel):
    query: str
    device_id: str
    top_k: int = 5


class SearchRequest(BaseModel):
    query: str
    device_id: str
    top_k: int = 10


class FeedbackRequest(BaseModel):
    episode_id: str
    device_id: str
    rating: float


class ProfileInteractionRequest(BaseModel):
    interaction: dict


class EpisodeRequest(BaseModel):
    device_id: str
    query: str
    answer: str
    agents: list = []
    model_used: str = ""
    session_type: str = "chat"


class FactRequest(BaseModel):
    device_id: str
    content: str
    source_type: str = "conversation"
    source_id: str = ""


def _require_memory():
    if state.memory_service is None:
        raise HTTPException(status_code=503, detail="Memory service not available")
    return state.memory_service


@router.post("/recall")
async def recall(request: RecallRequest):
    svc = _require_memory()
    episodes = await svc.recall_episodes(request.device_id, request.query, top_k=request.top_k)
    facts = await svc.recall_facts(request.device_id, request.query)
    profile = await svc.get_profile(request.device_id)
    return {"episodes": episodes, "facts": facts, "profile": profile}


@router.get("/profile/{device_id}")
async def get_profile(device_id: str):
    svc = _require_memory()
    profile = await svc.get_profile(device_id)
    return {"device_id": device_id, "profile": profile}


@router.post("/profile/{device_id}")
async def update_profile(device_id: str, request: ProfileInteractionRequest):
    svc = _require_memory()
    profile = await svc.update_profile(device_id, request.interaction)
    return {"profile": profile}


@router.post("/episode")
async def create_episode(request: EpisodeRequest):
    svc = _require_memory()
    episode_id = await svc.store_episode(
        device_id=request.device_id,
        query=request.query,
        answer=request.answer,
        agents=request.agents,
        model_used=request.model_used,
        session_type=request.session_type,
    )
    return {"episode_id": episode_id}


@router.get("/episodes/{device_id}")
async def list_episodes(device_id: str, limit: int = 20, offset: int = 0):
    svc = _require_memory()
    result = await svc.list_episodes(device_id, limit=limit, offset=offset)
    return {"episodes": result, "total": len(result)}


@router.delete("/episode/{episode_id}")
async def delete_episode(episode_id: str, device_id: str):
    svc = _require_memory()
    episode = await svc.get_episode(episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    if episode.get("device_id") != device_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this episode")
    deleted = await svc.delete_episode(episode_id)
    return {"deleted": deleted}


@router.post("/fact")
async def create_fact(request: FactRequest):
    svc = _require_memory()
    fact_id = await svc.store_fact(
        device_id=request.device_id,
        content=request.content,
        source_type=request.source_type,
        source_id=request.source_id,
    )
    return {"fact_id": fact_id}


@router.get("/facts/{device_id}")
async def list_facts(device_id: str, query: str = "", top_k: int = 10):
    svc = _require_memory()
    result = await svc.recall_facts(device_id, query=query, top_k=top_k)
    return {"facts": result}


@router.get("/stats/{device_id}")
async def get_stats(device_id: str):
    svc = _require_memory()
    stats = await svc.get_stats(device_id)
    return stats


@router.get("/usage/{device_id}")
async def get_usage(device_id: str, metric: str | None = None, hours: int = 24):
    svc = _require_memory()
    usage = await svc.get_usage(device_id, metric_name=metric, hours=hours)
    return {"device_id": device_id, "usage": usage}


@router.post("/decay")
async def run_decay():
    svc = _require_memory()
    decayed = await svc.decay_old_facts()
    compacted = await svc.compact_episodes()
    return {"decayed_facts": decayed, "compacted_episodes": compacted}


@router.post("/search")
async def search(request: SearchRequest):
    svc = _require_memory()
    episodes = await svc.recall_episodes(request.device_id, request.query, top_k=request.top_k)
    facts = await svc.recall_facts(request.device_id, request.query)
    return {"episodes": episodes, "facts": facts}


@router.get("/history")
async def get_history(device_id: str, limit: int = 20, offset: int = 0):
    svc = _require_memory()
    result = await svc.list_episodes(device_id, limit=limit, offset=offset)
    return {"episodes": result, "total": len(result)}


@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    svc = _require_memory()
    if not 0.0 <= request.rating <= 5.0:
        raise HTTPException(status_code=400, detail="Rating must be between 0.0 and 5.0")

    episode = await svc.get_episode(request.episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    if episode.get("device_id") != request.device_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this episode")

    db = await svc._get_db()
    await db.execute(
        "UPDATE episodes SET outcome_rating = ? WHERE id = ?",
        (request.rating, request.episode_id),
    )
    await db.commit()
    return {"updated": True, "episode_id": request.episode_id, "rating": request.rating}


@router.get("/health")
async def memory_health():
    svc = state.memory_service
    if svc is None:
        return {"status": "unavailable", "db_exists": False}
    try:
        stats = await svc.get_stats()
        return {"status": "healthy", "db_exists": True, **stats}
    except Exception as e:
        return {"status": "error", "error": str(e), "db_exists": False}
