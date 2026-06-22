import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager

from app.services.telemetry import trace_span

logger = logging.getLogger(__name__)

PROFILE_STALE_THRESHOLD = 300
MAX_BACKOFF = 10.0


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


def _get_profile_backoff(profile_backoff_state: dict, device_id: str) -> float:
    return profile_backoff_state.get(device_id, 0.0)


async def get_profile(
    db, profile_backoff_state: dict, device_id: str
) -> dict:
    with trace_span("memory.get_profile", {"device_id": device_id}):
        backoff = _get_profile_backoff(profile_backoff_state, device_id)
        if backoff > 0:
            await asyncio.sleep(backoff)
        row = await db.execute_fetchall(
            "SELECT profile_json, updated_at FROM user_profiles WHERE device_id = ?",
            (device_id,),
        )
        if not row:
            return {"device_id": device_id, "preferences": {}, "updated_at": 0}
        updated_at = row[0][1]
        now = time.time()
        if now - updated_at > PROFILE_STALE_THRESHOLD:
            current = profile_backoff_state.get(device_id, 0.0)
            if current == 0.0:
                profile_backoff_state[device_id] = 0.5
            else:
                profile_backoff_state[device_id] = min(current * 2, MAX_BACKOFF)
        else:
            profile_backoff_state.pop(device_id, None)
        return {
            "device_id": device_id,
            **json.loads(row[0][0]),
            "updated_at": updated_at,
        }


async def update_profile(
    db, write_lock, profile_backoff_state: dict, device_id: str, updates: dict
) -> dict:
    with trace_span("memory.update_profile", {"device_id": device_id}):
        now = time.time()
        existing = await get_profile(db, profile_backoff_state, device_id)
        merged = {k: v for k, v in existing.items() if k not in ("device_id", "updated_at")}
        merged.update(updates)

        async with write_lock:
            await db.execute(
                """INSERT INTO user_profiles (device_id, profile_json, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(device_id) DO UPDATE SET
                       profile_json = excluded.profile_json,
                       updated_at = excluded.updated_at""",
                (device_id, json.dumps(merged), now),
            )
            await db.commit()
        return {"device_id": device_id, **merged, "updated_at": now}


async def record_agent_outcome(
    db,
    write_lock,
    agent_type: str,
    query_pattern: str,
    strategy: str,
    outcome_quality: float,
    device_id: str,
    model_used: str = "",
    tier: int = 0,
) -> None:
    with trace_span(
        "memory.record_agent_outcome", {"agent_type": agent_type, "device_id": device_id}
    ):
        now = time.time()
        async with write_lock:
            async with _transaction(db):
                await db.execute(
                    """INSERT INTO agent_outcomes
                       (agent_type, query_pattern, strategy_used, outcome_quality,
                        model_used, tier, device_id, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        agent_type,
                        query_pattern,
                        strategy,
                        outcome_quality,
                        model_used,
                        tier,
                        device_id,
                        now,
                    ),
                )

                rows = await db.execute_fetchall(
                    """SELECT id, best_strategy, success_rate, sample_count
                       FROM agent_strategies
                       WHERE agent_type = ? AND pattern_signature = ?""",
                    (agent_type, query_pattern),
                )

                if rows:
                    sid, best_strat, rate, count = rows[0]
                    new_count = count + 1
                    new_rate = (rate * count + outcome_quality) / new_count
                    if outcome_quality > rate:
                        best_strat = strategy
                    await db.execute(
                        """UPDATE agent_strategies
                           SET best_strategy = ?, success_rate = ?, sample_count = ?,
                               last_updated = ?
                           WHERE id = ?""",
                        (best_strat, new_rate, new_count, now, sid),
                    )
                else:
                    await db.execute(
                        """INSERT INTO agent_strategies
                           (agent_type, pattern_signature, best_strategy, success_rate,
                            sample_count, last_updated)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (agent_type, query_pattern, strategy, outcome_quality, 1, now),
                    )


async def get_agent_strategies(
    db, agent_type: str, query_pattern: str = ""
) -> list[dict]:
    with trace_span("memory.get_agent_strategies", {"agent_type": agent_type}):
        if query_pattern:
            rows = await db.execute_fetchall(
                """SELECT agent_type, pattern_signature, best_strategy,
                          success_rate, sample_count, last_updated
                   FROM agent_strategies
                   WHERE agent_type = ? AND pattern_signature = ?
                   ORDER BY success_rate DESC""",
                (agent_type, query_pattern),
            )
        else:
            rows = await db.execute_fetchall(
                """SELECT agent_type, pattern_signature, best_strategy,
                          success_rate, sample_count, last_updated
                   FROM agent_strategies
                   WHERE agent_type = ?
                   ORDER BY success_rate DESC
                   LIMIT 50""",
                (agent_type,),
            )

        return [
            {
                "agent_type": r[0],
                "pattern_signature": r[1],
                "best_strategy": r[2],
                "success_rate": r[3] or 0.5,
                "sample_count": r[4] or 0,
                "last_updated": r[5],
            }
            for r in rows
        ]


async def get_project_profile(db, kb_name: str) -> dict | None:
    with trace_span("memory.get_project_profile", {"kb_name": kb_name}):
        row = await db.execute_fetchall(
            """SELECT profile_json, document_count, total_pages,
                      created_at, last_queried
               FROM project_profiles WHERE kb_name = ?""",
            (kb_name,),
        )
        if not row:
            return None
        return {
            "kb_name": kb_name,
            **json.loads(row[0][0]),
            "document_count": row[0][1],
            "total_pages": row[0][2],
            "created_at": row[0][3],
            "last_queried": row[0][4],
        }


async def update_project_profile(
    db, write_lock, kb_name: str, profile: dict
) -> None:
    with trace_span("memory.update_project_profile", {"kb_name": kb_name}):
        now = time.time()
        existing = await get_project_profile(db, kb_name)
        doc_count = profile.get("document_count", existing["document_count"] if existing else 0)
        total_pages = profile.get("total_pages", existing["total_pages"] if existing else 0)
        profile_filtered = {
            k: v for k, v in profile.items() if k not in ("document_count", "total_pages")
        }

        async with write_lock:
            await db.execute(
                """INSERT INTO project_profiles
                   (kb_name, profile_json, document_count, total_pages, created_at, last_queried)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(kb_name) DO UPDATE SET
                       profile_json = excluded.profile_json,
                       document_count = excluded.document_count,
                       total_pages = excluded.total_pages,
                       last_queried = excluded.last_queried""",
                (
                    kb_name,
                    json.dumps(profile_filtered),
                    doc_count,
                    total_pages,
                    existing["created_at"] if existing else now,
                    now,
                ),
            )
            await db.commit()


async def get_l3(db, device_id: str, slot: str) -> dict:
    with trace_span("memory.get_l3", {"device_id": device_id, "slot": slot}):
        row = await db.execute_fetchall(
            """SELECT content, entry_count, last_consolidated_at, updated_at
               FROM user_l3 WHERE device_id = ? AND slot = ?""",
            (device_id, slot),
        )
        if not row:
            return {
                "slot": slot,
                "content": {},
                "entry_count": 0,
                "last_consolidated_at": None,
                "updated_at": None,
            }
        return {
            "slot": slot,
            "content": json.loads(row[0][0]) if row[0][0] else {},
            "entry_count": row[0][1],
            "last_consolidated_at": row[0][2],
            "updated_at": row[0][3],
        }


async def get_l3_all(db, device_id: str) -> dict:
    result = {}
    for slot in ("profile", "recent", "scope", "preferences"):
        result[slot] = await get_l3(db, device_id, slot)
    return result


async def update_l3_preference(
    db, write_lock, device_id: str, updates: dict
) -> dict:
    with trace_span("memory.update_l3_preference", {"device_id": device_id}):
        now = time.time()
        current = await get_l3(db, device_id, "preferences")
        content = {**current["content"], **updates}
        async with write_lock:
            await db.execute(
                """INSERT INTO user_l3 (device_id, slot, content, entry_count, updated_at)
                   VALUES (?, 'preferences', ?, 1, ?)
                   ON CONFLICT(device_id, slot) DO UPDATE SET
                      content = excluded.content,
                      entry_count = excluded.entry_count,
                      updated_at = excluded.updated_at""",
                (device_id, json.dumps(content), now),
            )
            await db.commit()
        return content


async def read_l3_concat(db, device_id: str) -> str:
    all_l3 = await get_l3_all(db, device_id)
    parts = []
    for slot in ("profile", "recent", "scope", "preferences"):
        data = all_l3[slot]["content"]
        if data:
            parts.append(f"[{slot}]: {json.dumps(data)}")
    return "\n".join(parts) if parts else ""


async def upgrade_provenance(
    db,
    write_lock,
    entity_type: str,
    entity_id: str,
    new_provenance: str,
    reasoning: str = "",
) -> bool:
    with trace_span("memory.upgrade_provenance", {"entity_type": entity_type}):
        now = time.time()
        table = {"episode": "episodes", "fact": "facts"}.get(entity_type)
        if not table:
            return False
        row = await db.execute_fetchall(
            f"SELECT provenance FROM {table} WHERE id = ?", (entity_id,)
        )
        if not row:
            return False
        old = row[0][0]
        valid = {"user", "ai-suggested", "ai-executed", "user-revised"}
        if new_provenance not in valid:
            return False
        async with write_lock:
            await db.execute(
                f"UPDATE {table} SET provenance = ? WHERE id = ?",
                (new_provenance, entity_id),
            )
            await db.execute(
                """INSERT INTO provenance_log
                   (entity_type, entity_id, provenance_type, original_provenance,
                    reasoning, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (entity_type, entity_id, new_provenance, old, reasoning, now),
            )
            await db.commit()
        return True


async def get_provenance_lineage(
    db, entity_type: str, entity_id: str
) -> list[dict]:
    rows = await db.execute_fetchall(
        """SELECT provenance_type, original_provenance, reasoning, created_at
           FROM provenance_log
           WHERE entity_type = ? AND entity_id = ?
           ORDER BY created_at""",
        (entity_type, entity_id),
    )
    return [
        {"provenance": r[0], "was": r[1], "reasoning": r[2] or "", "at": r[3]} for r in rows
    ]
