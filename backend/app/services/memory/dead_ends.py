import json
import logging
import time
import uuid

from app.services.telemetry import trace_span

from .episodes import _store_chunks

logger = logging.getLogger(__name__)


async def _track_usage_nolock(
    db, device_id: str, metric_name: str, metric_value: float
) -> None:
    await db.execute(
        "INSERT INTO memory_usage (device_id, metric_name, metric_value) VALUES (?, ?, ?)",
        (device_id, metric_name, metric_value),
    )
    await db.commit()


async def store_dead_end(
    db,
    write_lock,
    device_id: str,
    title: str,
    hypothesis: str,
    approach: str,
    failure_mode: str,
    lesson: str,
    provenance: str = "ai-suggested",
    failure_evidence: str = "",
    parent_node_id: str = "",
    parent_node_type: str = "",
    tags: list[str] | None = None,
) -> str:
    with trace_span("memory.store_dead_end", {"device_id": device_id}):
        dead_end_id = uuid.uuid4().hex[:12]
        now = time.time()
        searchable = f"{title} {hypothesis} {approach} {failure_mode} {lesson}"
        async with write_lock:
            await db.execute(
                """INSERT INTO dead_ends
                   (id, device_id, title, hypothesis, approach, failure_mode,
                    failure_evidence, lesson, parent_node_id, parent_node_type,
                    provenance, tags, confidence, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    dead_end_id,
                    device_id,
                    title,
                    hypothesis,
                    approach,
                    failure_mode,
                    failure_evidence,
                    lesson,
                    parent_node_id,
                    parent_node_type,
                    provenance,
                    json.dumps(tags or []),
                    0.5,
                    now,
                ),
            )
            await _store_chunks(db, "dead_end_chunks", dead_end_id, device_id, searchable, now)
            await db.commit()
            await _track_usage_nolock(db, device_id, "dead_ends_stored", 1)
        return dead_end_id


async def recall_dead_ends(
    db, device_id: str, query: str, top_k: int = 5
) -> list[dict]:
    with trace_span("memory.recall_dead_ends", {"device_id": device_id}):
        try:
            rows = await db.execute_fetchall(
                """SELECT d.id, d.device_id, d.title, d.hypothesis, d.approach,
                          d.failure_mode, d.failure_evidence, d.lesson,
                          d.parent_node_id, d.parent_node_type,
                          d.provenance, d.tags, d.confidence, d.created_at,
                          MIN(fts.rank) as best_rank
                   FROM dead_ends_fts fts
                   JOIN dead_end_chunks c ON c.chunk_id = fts.rowid
                   JOIN dead_ends d ON d.id = c.source_id
                   WHERE dead_ends_fts MATCH ? AND d.device_id = ? AND d.archived = 0
                   GROUP BY d.id
                   ORDER BY best_rank
                   LIMIT ?""",
                (query, device_id, top_k),
            )
        except Exception:
            rows = await db.execute_fetchall(
                """SELECT id, device_id, title, hypothesis, approach,
                          failure_mode, failure_evidence, lesson,
                          parent_node_id, parent_node_type,
                          provenance, tags, confidence, created_at, 0
                   FROM dead_ends
                   WHERE device_id = ? AND archived = 0
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (device_id, top_k),
            )
        return [
            {
                "id": r[0],
                "device_id": r[1],
                "title": r[2],
                "hypothesis": r[3],
                "approach": r[4],
                "failure_mode": r[5],
                "failure_evidence": r[6] or "",
                "lesson": r[7],
                "parent_node_id": r[8] or "",
                "parent_node_type": r[9] or "",
                "provenance": r[10],
                "tags": json.loads(r[11]) if r[11] else [],
                "confidence": r[12] or 0.5,
                "created_at": r[13],
            }
            for r in rows
        ]


async def get_dead_end_preventions(
    db, device_id: str, approach_description: str
) -> list[dict]:
    with trace_span("memory.get_dead_end_preventions", {"device_id": device_id}):
        try:
            rows = await db.execute_fetchall(
                """SELECT d.id, d.title, d.approach, d.failure_mode, d.lesson, d.confidence
                   FROM dead_ends_fts fts
                   JOIN dead_end_chunks c ON c.chunk_id = fts.rowid
                   JOIN dead_ends d ON d.id = c.source_id
                   WHERE dead_ends_fts MATCH ? AND d.device_id = ? AND d.archived = 0
                   GROUP BY d.id
                   ORDER BY MIN(fts.rank)
                   LIMIT 5""",
                (approach_description, device_id),
            )
        except Exception:
            return []
        return [
            {
                "id": r[0],
                "title": r[1],
                "approach": r[2],
                "failure_mode": r[3],
                "lesson": r[4],
                "confidence": r[5] or 0.5,
            }
            for r in rows
        ]
