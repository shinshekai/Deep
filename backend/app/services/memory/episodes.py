import json
import logging
import time
import uuid

from app.services.telemetry import trace_span

logger = logging.getLogger(__name__)

CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200
VALID_CHUNK_TABLES = frozenset({"episode_chunks", "fact_chunks"})


def _chunk_text(
    text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            for sep in ("\n", ". ", "! ", "? "):
                last = text.rfind(sep, start + chunk_size // 2, end)
                if last > start:
                    end = last + len(sep)
                    break
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


async def _store_chunks(
    db, table: str, source_id: str, device_id: str, text: str, created_at: float
) -> None:
    if table not in VALID_CHUNK_TABLES:
        raise ValueError(f"Invalid chunk table: {table}")
    chunks = _chunk_text(text)
    await db.executemany(
        f"INSERT INTO {table} (source_id, device_id, chunk_index, chunk_text, created_at) "
        f"VALUES (?, ?, ?, ?, ?)",
        [(source_id, device_id, i, chunk, created_at) for i, chunk in enumerate(chunks)],
    )


async def _delete_chunks(db, table: str, source_id: str) -> None:
    if table not in VALID_CHUNK_TABLES:
        raise ValueError(f"Invalid chunk table: {table}")
    await db.execute(f"DELETE FROM {table} WHERE source_id = ?", (source_id,))


async def _stream_query(db, sql: str, params: tuple = (), chunk_size: int = 100):
    async with db.execute(sql, params) as cursor:
        while True:
            batch = await cursor.fetchmany(chunk_size)
            if not batch:
                break
            for row in batch:
                yield row


async def _track_usage_nolock(
    db, device_id: str, metric_name: str, metric_value: float
) -> None:
    await db.execute(
        "INSERT INTO memory_usage (device_id, metric_name, metric_value) VALUES (?, ?, ?)",
        (device_id, metric_name, metric_value),
    )
    await db.commit()


async def store_episode(
    db,
    write_lock,
    device_id: str,
    query: str,
    answer: str,
    agents: list[str] | None = None,
    model_used: str = "",
    tier: int = 0,
    citations: list | None = None,
    session_type: str = "chat",
    provenance: str = "user",
) -> str:
    with trace_span(
        "memory.store_episode", {"device_id": device_id, "session_type": session_type}
    ):
        episode_id = uuid.uuid4().hex[:12]
        now = time.time()
        combined = f"{query}\n\n{answer}"
        async with write_lock:
            await db.execute(
                """INSERT INTO episodes
                   (id, device_id, session_type, query, answer, agents,
                    model_used, tier, citations, outcome_rating, created_at, provenance)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    episode_id,
                    device_id,
                    session_type,
                    query,
                    answer,
                    json.dumps(agents or []),
                    model_used,
                    tier,
                    json.dumps(citations or []),
                    0.0,
                    now,
                    provenance,
                ),
            )
            await _store_chunks(db, "episode_chunks", episode_id, device_id, combined, now)
            await db.commit()
            await _track_usage_nolock(db, device_id, "episodes_stored", 1)
        return episode_id


async def recall_episodes(
    db, write_lock, device_id: str, query: str, top_k: int = 5
) -> list[dict]:
    with trace_span("memory.recall_episodes", {"device_id": device_id, "top_k": top_k}):
        now = time.time()
        try:
            rows = await db.execute_fetchall(
                """SELECT e.id, e.device_id, e.session_type, e.query, e.answer,
                          e.agents, e.model_used, e.tier, e.citations,
                          e.outcome_rating, e.created_at,
                          MIN(fts.rank) as best_rank
                   FROM episodes_fts fts
                   JOIN episode_chunks c ON c.chunk_id = fts.rowid
                   JOIN episodes e ON e.id = c.source_id
                   WHERE episodes_fts MATCH ? AND e.device_id = ? AND e.archived = 0
                   GROUP BY e.id
                   ORDER BY best_rank, e.created_at DESC, e.id
                   LIMIT ?""",
                (query, device_id, top_k),
            )
        except Exception:
            rows = await db.execute_fetchall(
                """SELECT id, device_id, session_type, query, answer, agents,
                          model_used, tier, citations, outcome_rating, created_at, 0
                   FROM episodes
                   WHERE device_id = ? AND archived = 0
                   ORDER BY created_at DESC, id
                   LIMIT ?""",
                (device_id, top_k),
            )

        results = []
        for row in rows:
            recency = now - row[10] if row[10] else 0
            recency_score = 1.0 / (1.0 + recency / 86400.0)
            fts_score = -row[11] if row[11] else 0.0
            combined = 0.6 * fts_score + 0.4 * recency_score

            results.append(
                {
                    "id": row[0],
                    "device_id": row[1],
                    "session_type": row[2],
                    "query": row[3],
                    "answer": row[4],
                    "agents": json.loads(row[5]) if row[5] else [],
                    "model_used": row[6] or "",
                    "tier": row[7] or 0,
                    "citations": json.loads(row[8]) if row[8] else [],
                    "outcome_rating": row[9] or 0.0,
                    "created_at": row[10],
                    "score": round(combined, 4),
                }
            )

        results.sort(key=lambda r: r["score"], reverse=True)
        async with write_lock:
            await _track_usage_nolock(db, device_id, "recalls", 1)
        return results[:top_k]


async def get_episode(db, episode_id: str) -> dict | None:
    with trace_span("memory.get_episode", {"episode_id": episode_id}):
        row = await db.execute_fetchall(
            """SELECT id, device_id, session_type, query, answer, agents,
                      model_used, tier, citations, outcome_rating, created_at
               FROM episodes WHERE id = ?""",
            (episode_id,),
        )
        if not row:
            return None
        r = row[0]
        return {
            "id": r[0],
            "device_id": r[1],
            "session_type": r[2],
            "query": r[3],
            "answer": r[4],
            "agents": json.loads(r[5]) if r[5] else [],
            "model_used": r[6] or "",
            "tier": r[7] or 0,
            "citations": json.loads(r[8]) if r[8] else [],
            "outcome_rating": r[9] or 0.0,
            "created_at": r[10],
        }


async def delete_episode(db, write_lock, episode_id: str) -> bool:
    with trace_span("memory.delete_episode", {"episode_id": episode_id}):
        async with write_lock:
            await _delete_chunks(db, "episode_chunks", episode_id)
            cursor = await db.execute("DELETE FROM episodes WHERE id = ?", (episode_id,))
            await db.commit()
        return cursor.rowcount > 0


async def rate_episode(
    db, write_lock, device_id: str, episode_id: str, rating: float
) -> bool:
    with trace_span("memory.rate_episode", {"device_id": device_id}):
        rating = max(0.0, min(1.0, float(rating)))
        async with write_lock:
            cursor = await db.execute(
                "UPDATE episodes SET outcome_rating = ? WHERE id = ? AND device_id = ?",
                (rating, episode_id, device_id),
            )
            await db.commit()
        return cursor.rowcount > 0


async def list_episodes(
    db, device_id: str, limit: int = 20, offset: int = 0
) -> list[dict]:
    with trace_span(
        "memory.list_episodes", {"device_id": device_id, "limit": limit, "offset": offset}
    ):
        sql = """SELECT id, device_id, session_type, query, answer, agents,
                        model_used, tier, citations, outcome_rating, created_at
                 FROM episodes
                 WHERE device_id = ? AND archived = 0
                 ORDER BY created_at DESC
                 LIMIT ? OFFSET ?"""
        params = (device_id, limit, offset)
        if limit > 100:
            results = []
            async for r in _stream_query(db, sql, params):
                results.append(
                    {
                        "id": r[0],
                        "device_id": r[1],
                        "session_type": r[2],
                        "query": r[3],
                        "answer": r[4],
                        "agents": json.loads(r[5]) if r[5] else [],
                        "model_used": r[6] or "",
                        "tier": r[7] or 0,
                        "citations": json.loads(r[8]) if r[8] else [],
                        "outcome_rating": r[9] or 0.0,
                        "created_at": r[10],
                    }
                )
            return results
        rows = await db.execute_fetchall(sql, params)
        results = []
        for r in rows:
            results.append(
                {
                    "id": r[0],
                    "device_id": r[1],
                    "session_type": r[2],
                    "query": r[3],
                    "answer": r[4],
                    "agents": json.loads(r[5]) if r[5] else [],
                    "model_used": r[6] or "",
                    "tier": r[7] or 0,
                    "citations": json.loads(r[8]) if r[8] else [],
                    "outcome_rating": r[9] or 0.0,
                    "created_at": r[10],
                }
            )
        return results


async def update_episode_rating(
    db, write_lock, episode_id: str, rating: float
) -> bool:
    with trace_span("memory.update_episode_rating", {"episode_id": episode_id}):
        clamped = max(0.0, min(1.0, float(rating)))
        async with write_lock:
            await db.execute(
                "UPDATE episodes SET outcome_rating = ? WHERE id = ?",
                (clamped, episode_id),
            )
            await db.commit()
        return True
