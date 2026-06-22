import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

from app.services.telemetry import trace_span

from .episodes import _store_chunks

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _transaction(db):
    try:
        await db.execute("BEGIN IMMEDIATE")
        yield
        await db.commit()
    except Exception:
        try:
            await db.execute("ROLLBACK")
        except Exception:
            logger.exception("Failed to rollback transaction")
        raise


async def _track_usage_nolock(
    db, device_id: str, metric_name: str, metric_value: float
) -> None:
    await db.execute(
        "INSERT INTO memory_usage (device_id, metric_name, metric_value) VALUES (?, ?, ?)",
        (device_id, metric_name, metric_value),
    )
    await db.commit()


async def store_fact(
    db,
    write_lock,
    device_id: str,
    content: str,
    source_type: str = "conversation",
    source_id: str = "",
    confidence: float = 0.5,
    provenance: str = "user",
) -> str:
    with trace_span("memory.store_fact", {"device_id": device_id, "source_type": source_type}):
        fact_id = uuid.uuid4().hex[:12]
        now = time.time()
        async with write_lock:
            await db.execute(
                """INSERT INTO facts
                   (id, device_id, content, source_type, source_id,
                    confidence, created_at, last_accessed, access_count, provenance)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    fact_id,
                    device_id,
                    content,
                    source_type,
                    source_id,
                    confidence,
                    now,
                    now,
                    0,
                    provenance,
                ),
            )
            await _store_chunks(db, "fact_chunks", fact_id, device_id, content, now)
            await db.commit()
            await _track_usage_nolock(db, device_id, "facts_stored", 1)
        return fact_id


async def recall_facts(
    db, write_lock, device_id: str, query: str, top_k: int = 10
) -> list[dict]:
    with trace_span("memory.recall_facts", {"device_id": device_id, "top_k": top_k}):
        now = time.time()

        try:
            rows = await db.execute_fetchall(
                """SELECT f.id, f.device_id, f.content, f.source_type, f.source_id,
                          f.confidence, f.created_at, f.last_accessed, f.access_count,
                          MIN(fts.rank) as best_rank
                   FROM facts_fts fts
                   JOIN fact_chunks c ON c.chunk_id = fts.rowid
                   JOIN facts f ON f.id = c.source_id
                   WHERE facts_fts MATCH ? AND f.device_id = ? AND f.archived = 0
                   GROUP BY f.id
                   ORDER BY best_rank
                   LIMIT ?""",
                (query, device_id, top_k * 2),
            )
        except Exception:
            rows = await db.execute_fetchall(
                """SELECT id, device_id, content, source_type, source_id,
                          confidence, created_at, last_accessed, access_count, 0
                   FROM facts
                   WHERE device_id = ? AND archived = 0
                   ORDER BY created_at DESC, id
                   LIMIT ?""",
                (device_id, top_k * 2),
            )

        results = []
        for row in rows:
            recency = now - row[6] if row[6] else 0
            recency_score = 1.0 / (1.0 + recency / 86400.0)
            fts_score = -row[9] if row[9] else 0.0
            combined = 0.4 * fts_score + 0.3 * recency_score + 0.3 * (row[5] or 0.5)

            results.append(
                {
                    "id": row[0],
                    "device_id": row[1],
                    "content": row[2],
                    "source_type": row[3] or "",
                    "source_id": row[4] or "",
                    "confidence": row[5] or 0.5,
                    "created_at": row[6],
                    "last_accessed": row[7],
                    "access_count": row[8] or 0,
                    "score": round(combined, 4),
                }
            )

        results.sort(key=lambda r: r["score"], reverse=True)
        selected = results[:top_k]
        selected_ids = [r["id"] for r in selected]

        if selected_ids:
            async with write_lock:
                async with _transaction(db):
                    placeholders = ",".join("?" * len(selected_ids))
                    await db.execute(
                        f"UPDATE facts SET last_accessed = ?, access_count = access_count + 1 WHERE id IN ({placeholders})",
                        [now, *selected_ids],
                    )

        return selected


async def detect_contradictions(
    db, new_fact: str, device_id: str
) -> list[dict]:
    with trace_span("memory.detect_contradictions", {"device_id": device_id}):
        new_words = set(new_fact.lower().split())
        if not new_words:
            return []

        rows = await db.execute_fetchall(
            """SELECT id, content, confidence, created_at
               FROM facts
               WHERE device_id = ? AND archived = 0
               ORDER BY created_at DESC
               LIMIT 200""",
            (device_id,),
        )

        contradictions = []
        for row in rows:
            existing_words = set(row[1].lower().split())
            overlap = len(new_words & existing_words)
            total = len(new_words | existing_words)
            if total == 0:
                continue
            jaccard = overlap / total
            negation = False
            new_lower = new_fact.lower()
            existing_lower = row[1].lower()
            negations = ["not", "no", "never", "isn't", "aren't", "wasn't", "won't", "can't"]
            for neg in negations:
                if neg in new_lower and neg not in existing_lower:
                    negation = True
                    break
                if neg not in new_lower and neg in existing_lower:
                    negation = True
                    break

            if jaccard > 0.4 and negation:
                contradictions.append(
                    {
                        "existing_fact_id": row[0],
                        "existing_content": row[1],
                        "existing_confidence": row[2] or 0.5,
                        "new_fact": new_fact,
                        "overlap_score": round(jaccard, 4),
                        "relation_type": "contradicts",
                    }
                )

        return contradictions


async def batch_resolve_contradictions(
    db, device_id: str, batch_size: int = 10
) -> dict:
    with trace_span("memory.batch_resolve_contradictions", {"device_id": device_id}):
        rows = await db.execute_fetchall(
            """SELECT id, content, confidence, created_at
               FROM facts
               WHERE device_id = ? AND archived = 0
               ORDER BY created_at DESC
               LIMIT 200""",
            (device_id,),
        )
        if len(rows) < 2:
            return {"resolved": 0, "groups": 0, "candidates": []}

        negations = ["not", "no", "never", "isn't", "aren't", "wasn't", "won't", "can't"]
        groups: list[list[dict]] = []
        seen: set[str] = set()

        for i in range(len(rows)):
            if rows[i][0] in seen:
                continue
            words_i = set(rows[i][1].lower().split())
            if not words_i:
                continue
            group = [{"id": rows[i][0], "content": rows[i][1], "confidence": rows[i][2] or 0.5}]
            for j in range(i + 1, len(rows)):
                if rows[j][0] in seen:
                    continue
                words_j = set(rows[j][1].lower().split())
                if not words_j:
                    continue
                overlap = len(words_i & words_j)
                total = len(words_i | words_j)
                if total == 0:
                    continue
                jaccard = overlap / total
                negation = False
                ci = rows[i][1].lower()
                cj = rows[j][1].lower()
                for neg in negations:
                    if (neg in ci) != (neg in cj):
                        negation = True
                        break
                if jaccard > 0.3 and negation:
                    group.append(
                        {
                            "id": rows[j][0],
                            "content": rows[j][1],
                            "confidence": rows[j][2] or 0.5,
                        }
                    )
                    seen.add(rows[j][0])
            if len(group) > 1:
                seen.add(rows[i][0])
                groups.append(group)

        candidates = []
        for group in groups[:batch_size]:
            candidates.append(
                {
                    "facts": group,
                    "suggested_resolution": "; ".join(item["content"] for item in group),
                }
            )
        return {
            "resolved": 0,
            "groups": len(candidates),
            "candidates": candidates,
        }


async def resolve_contradiction(
    db,
    write_lock,
    device_id: str,
    fact_ids: list[str],
    keep: str,
    merge: bool = True,
) -> dict:
    with trace_span("memory.resolve_contradiction", {"device_id": device_id}):
        if not fact_ids:
            return {"resolved": 0}
        async with write_lock:
            async with _transaction(db):
                if merge:
                    merged_content = keep
                    ep_id = uuid.uuid4().hex[:12]
                    now = time.time()
                    await db.execute(
                        """INSERT INTO episodes
                           (id, device_id, session_type, query, answer, agents,
                            model_used, tier, citations, outcome_rating, created_at, provenance)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            ep_id,
                            device_id,
                            "maintenance",
                            "contradiction resolution",
                            merged_content,
                            json.dumps([]),
                            "",
                            0,
                            json.dumps([]),
                            0.0,
                            now,
                            "user",
                        ),
                    )
                    combined = f"contradiction resolution\n\n{merged_content}"
                    await _store_chunks(db, "episode_chunks", ep_id, device_id, combined, now)
                placeholders = ",".join("?" * len(fact_ids))
                await db.execute(
                    f"UPDATE facts SET archived = 1 WHERE id IN ({placeholders})",
                    fact_ids,
                )
        return {"resolved": len(fact_ids)}
