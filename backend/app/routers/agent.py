"""Agent routes: research, questions, learning (stub implementations)."""

import time
from typing import Optional
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["agents"])


@router.post("/query")
async def query(payload: dict):
    return {"answer": "Stub response. Connect LM Studio for real answers.", "citations": []}


@router.post("/retrieve")
async def retrieve(payload: dict):
    return {"results": [], "total": 0}


@router.post("/research")
async def start_research(payload: dict):
    return {"session_id": f"research_{int(time.time())}", "status": "queued"}


@router.post("/questions/generate")
async def generate_questions(payload: dict):
    return {"questions": [], "total": 0}


@router.post("/learning/start")
async def start_learning(payload: dict):
    return {"session_id": f"learn_{int(time.time())}", "status": "active"}
