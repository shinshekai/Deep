import json
import logging
import time
import uuid

from app.services.telemetry import trace_span

from .facts import store_fact as _store_fact

logger = logging.getLogger(__name__)


async def stage_observation(
    db,
    write_lock,
    device_id: str,
    content: str,
    source_type: str = "observation",
    source_id: str = "",
    confidence: float = 0.5,
    metadata: dict | None = None,
) -> str:
    with trace_span("memory.stage_observation", {"device_id": device_id}):
        obs_id = uuid.uuid4().hex[:12]
        now = time.time()
        async with write_lock:
            await db.execute(
                """INSERT INTO staged_observations
                   (id, device_id, content, source_type, source_id,
                    confidence, metadata, created_at, crystallized)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                (
                    obs_id,
                    device_id,
                    content,
                    source_type,
                    source_id,
                    confidence,
                    json.dumps(metadata or {}),
                    now,
                ),
            )
            await db.commit()
        return obs_id


async def crystallize_observations(
    db, write_lock, device_id: str
) -> int:
    with trace_span("memory.crystallize_observations", {"device_id": device_id}):
        rows = await db.execute_fetchall(
            """SELECT id, content, source_type, source_id, confidence
               FROM staged_observations
               WHERE device_id = ? AND crystallized = 0""",
            (device_id,),
        )
        if not rows:
            return 0
        count = 0
        crystallized_ids = []
        for obs_id, content, source_type, source_id, confidence in rows:
            await _store_fact(
                db=db,
                write_lock=write_lock,
                device_id=device_id,
                content=content,
                source_type=source_type,
                source_id=source_id,
                confidence=confidence,
                provenance="ai-executed",
            )
            crystallized_ids.append(obs_id)
            count += 1
        async with write_lock:
            for obs_id in crystallized_ids:
                await db.execute(
                    "UPDATE staged_observations SET crystallized = 1 WHERE id = ?",
                    (obs_id,),
                )
            await db.commit()
        return count


async def get_staged_observations(db, device_id: str) -> list[dict]:
    rows = await db.execute_fetchall(
        """SELECT id, content, source_type, source_id, confidence, metadata, created_at
           FROM staged_observations
           WHERE device_id = ? AND crystallized = 0
           ORDER BY created_at DESC""",
        (device_id,),
    )
    return [
        {
            "id": r[0],
            "content": r[1],
            "source_type": r[2],
            "source_id": r[3],
            "confidence": r[4],
            "metadata": json.loads(r[5]) if r[5] else {},
            "created_at": r[6],
        }
        for r in rows
    ]
