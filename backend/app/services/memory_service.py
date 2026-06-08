import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from app.services.telemetry import trace_span

logger = logging.getLogger(__name__)

DB_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "memory"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS episodes (
    id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    session_type TEXT NOT NULL,
    query TEXT NOT NULL,
    answer TEXT NOT NULL,
    agents TEXT,
    model_used TEXT,
    tier INTEGER,
    citations TEXT,
    outcome_rating REAL,
    created_at REAL NOT NULL,
    archived INTEGER DEFAULT 0
);

CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts USING fts5(
    query, answer, content=episodes, content_rowid=rowid,
    tokenize='porter unicode61'
);

CREATE TABLE IF NOT EXISTS facts (
    id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    content TEXT NOT NULL,
    source_type TEXT,
    source_id TEXT,
    confidence REAL DEFAULT 0.5,
    created_at REAL NOT NULL,
    last_accessed REAL,
    access_count INTEGER DEFAULT 0,
    archived INTEGER DEFAULT 0
);

CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
    content, content=facts, content_rowid=rowid,
    tokenize='porter unicode61'
);

CREATE TABLE IF NOT EXISTS fact_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_fact_id TEXT NOT NULL,
    target_fact_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    FOREIGN KEY (source_fact_id) REFERENCES facts(id),
    FOREIGN KEY (target_fact_id) REFERENCES facts(id)
);

CREATE TABLE IF NOT EXISTS user_profiles (
    device_id TEXT PRIMARY KEY,
    profile_json TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_type TEXT NOT NULL,
    query_pattern TEXT,
    strategy_used TEXT,
    outcome_quality REAL,
    model_used TEXT,
    tier INTEGER,
    device_id TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_type TEXT NOT NULL,
    pattern_signature TEXT NOT NULL,
    best_strategy TEXT,
    success_rate REAL DEFAULT 0.5,
    sample_count INTEGER DEFAULT 1,
    last_updated REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS project_profiles (
    kb_name TEXT PRIMARY KEY,
    profile_json TEXT NOT NULL,
    document_count INTEGER DEFAULT 0,
    total_pages INTEGER DEFAULT 0,
    created_at REAL NOT NULL,
    last_queried REAL
);

CREATE TABLE IF NOT EXISTS memory_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f','now')),
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_device ON memory_usage(device_id);
CREATE INDEX IF NOT EXISTS idx_usage_metric ON memory_usage(metric_name);

CREATE INDEX IF NOT EXISTS idx_episodes_device_created ON episodes(device_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_episodes_device_archived ON episodes(device_id, archived);
CREATE INDEX IF NOT EXISTS idx_facts_device_created ON facts(device_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_facts_device_archived ON facts(device_id, archived);
CREATE INDEX IF NOT EXISTS idx_fact_relationships_source ON fact_relationships(source_fact_id);
CREATE INDEX IF NOT EXISTS idx_fact_relationships_target ON fact_relationships(target_fact_id);
CREATE INDEX IF NOT EXISTS idx_agent_outcomes_device ON agent_outcomes(device_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_outcomes_type ON agent_outcomes(agent_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_strategies_pattern ON agent_strategies(agent_type, pattern_signature);
"""

FTS_SYNC_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS episodes_ai AFTER INSERT ON episodes BEGIN
    INSERT INTO episodes_fts(rowid, query, answer)
    VALUES (new.rowid, new.query, new.answer);
END;

CREATE TRIGGER IF NOT EXISTS episodes_ad AFTER DELETE ON episodes BEGIN
    INSERT INTO episodes_fts(episodes_fts, rowid, query, answer)
    VALUES ('delete', old.rowid, old.query, old.answer);
END;

CREATE TRIGGER IF NOT EXISTS episodes_au AFTER UPDATE ON episodes BEGIN
    INSERT INTO episodes_fts(episodes_fts, rowid, query, answer)
    VALUES ('delete', old.rowid, old.query, old.answer);
    INSERT INTO episodes_fts(rowid, query, answer)
    VALUES (new.rowid, new.query, new.answer);
END;

CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO facts_fts(rowid, content)
    VALUES (new.rowid, new.content);
END;

CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, content)
    VALUES ('delete', old.rowid, old.content);
END;

CREATE TRIGGER IF NOT EXISTS facts_au AFTER UPDATE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, content)
    VALUES ('delete', old.rowid, old.content);
    INSERT INTO facts_fts(rowid, content)
    VALUES (new.rowid, new.content);
END;
"""


class MemoryService:
    def __init__(self, db_path: str = "data/memory/deep_memory.db"):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def _safe(self, coro, default=None):
        try:
            return await coro
        except Exception as e:
            logger.warning(f"Memory operation failed: {e}")
            return default

    async def get_memory_stats_summary(self) -> dict:
        stats = await self.get_stats()
        return {"episodes": stats.get("episodes_active", 0), "facts": stats.get("facts_active", 0)}

    async def initialize(self):
        db_path = Path(self.db_path)
        if not db_path.is_absolute():
            db_path = Path(__file__).resolve().parent.parent.parent.parent / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._db = await aiosqlite.connect(str(db_path))
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.executescript(SCHEMA_SQL)
        await self._db.executescript(FTS_SYNC_TRIGGERS)
        await self._db.commit()
        logger.info(f"MemoryService initialized at {db_path}")

    async def _get_db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("MemoryService not initialized — call initialize() first")
        return self._db

    @asynccontextmanager
    async def _transaction(self):
        try:
            await self._db.execute("BEGIN IMMEDIATE")
            yield self._db
            await self._db.commit()
        except Exception:
            try:
                await self._db.execute("ROLLBACK")
            except Exception:
                logger.exception("Failed to rollback transaction")
            raise

    # ── Episodic ──────────────────────────────────────────────────────────────

    async def store_episode(
        self,
        device_id: str,
        query: str,
        answer: str,
        agents: list[str] | None = None,
        model_used: str = "",
        tier: int = 0,
        citations: list | None = None,
        session_type: str = "chat",
    ) -> str:
        with trace_span(
            "memory.store_episode", {"device_id": device_id, "session_type": session_type}
        ):
            db = await self._get_db()
            episode_id = uuid.uuid4().hex[:12]
            now = time.time()
            await db.execute(
                """INSERT INTO episodes
                   (id, device_id, session_type, query, answer, agents,
                    model_used, tier, citations, outcome_rating, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                ),
            )
            await db.commit()
            await self.track_usage(device_id, "episodes_stored", 1)
            return episode_id

    async def recall_episodes(self, device_id: str, query: str, top_k: int = 5) -> list[dict]:
        with trace_span("memory.recall_episodes", {"device_id": device_id, "top_k": top_k}):
            db = await self._get_db()
            now = time.time()
            try:
                rows = await db.execute_fetchall(
                    """SELECT e.id, e.device_id, e.session_type, e.query, e.answer,
                              e.agents, e.model_used, e.tier, e.citations,
                              e.outcome_rating, e.created_at,
                              rank
                       FROM episodes_fts fts
                       JOIN episodes e ON e.rowid = fts.rowid
                       WHERE episodes_fts MATCH ? AND e.device_id = ? AND e.archived = 0
                       ORDER BY rank, e.rowid
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
            await self.track_usage(device_id, "recalls", 1)
            return results[:top_k]

    async def get_episode(self, episode_id: str) -> dict | None:
        with trace_span("memory.get_episode", {"episode_id": episode_id}):
            db = await self._get_db()
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

    async def delete_episode(self, episode_id: str) -> bool:
        with trace_span("memory.delete_episode", {"episode_id": episode_id}):
            db = await self._get_db()
            cursor = await db.execute("DELETE FROM episodes WHERE id = ?", (episode_id,))
            await db.commit()
            return cursor.rowcount > 0

    async def list_episodes(self, device_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
        with trace_span(
            "memory.list_episodes", {"device_id": device_id, "limit": limit, "offset": offset}
        ):
            db = await self._get_db()
            rows = await db.execute_fetchall(
                """SELECT id, device_id, session_type, query, answer, agents,
                          model_used, tier, citations, outcome_rating, created_at
                   FROM episodes
                   WHERE device_id = ? AND archived = 0
                   ORDER BY created_at DESC
                   LIMIT ? OFFSET ?""",
                (device_id, limit, offset),
            )
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

    # ── Facts ─────────────────────────────────────────────────────────────────

    async def store_fact(
        self,
        device_id: str,
        content: str,
        source_type: str = "conversation",
        source_id: str = "",
        confidence: float = 0.5,
    ) -> str:
        with trace_span("memory.store_fact", {"device_id": device_id, "source_type": source_type}):
            db = await self._get_db()
            fact_id = uuid.uuid4().hex[:12]
            now = time.time()
            await db.execute(
                """INSERT INTO facts
                   (id, device_id, content, source_type, source_id,
                    confidence, created_at, last_accessed, access_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (fact_id, device_id, content, source_type, source_id, confidence, now, now, 0),
            )
            await db.commit()
            await self.track_usage(device_id, "facts_stored", 1)
            return fact_id

    async def recall_facts(self, device_id: str, query: str, top_k: int = 10) -> list[dict]:
        with trace_span("memory.recall_facts", {"device_id": device_id, "top_k": top_k}):
            db = await self._get_db()
            now = time.time()
            async with self._transaction():
                try:
                    rows = await db.execute_fetchall(
                        """SELECT f.id, f.device_id, f.content, f.source_type, f.source_id,
                                  f.confidence, f.created_at, f.last_accessed, f.access_count,
                                  rank
                           FROM facts_fts fts
                           JOIN facts f ON f.rowid = fts.rowid
                           WHERE facts_fts MATCH ? AND f.device_id = ? AND f.archived = 0
                           ORDER BY rank, f.rowid
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

                    await db.execute(
                        "UPDATE facts SET last_accessed = ?, access_count = access_count + 1 WHERE id = ?",
                        (now, row[0]),
                    )

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
                return results[:top_k]

    async def detect_contradictions(self, new_fact: str, device_id: str) -> list[dict]:
        with trace_span("memory.detect_contradictions", {"device_id": device_id}):
            db = await self._get_db()
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

    # ── User Profile ──────────────────────────────────────────────────────────

    async def get_profile(self, device_id: str) -> dict:
        with trace_span("memory.get_profile", {"device_id": device_id}):
            db = await self._get_db()
            row = await db.execute_fetchall(
                "SELECT profile_json, updated_at FROM user_profiles WHERE device_id = ?",
                (device_id,),
            )
            if not row:
                return {"device_id": device_id, "preferences": {}, "updated_at": 0}
            return {
                "device_id": device_id,
                **json.loads(row[0][0]),
                "updated_at": row[0][1],
            }

    async def update_profile(self, device_id: str, updates: dict) -> dict:
        with trace_span("memory.update_profile", {"device_id": device_id}):
            db = await self._get_db()
            now = time.time()
            existing = await self.get_profile(device_id)
            merged = {k: v for k, v in existing.items() if k not in ("device_id", "updated_at")}
            merged.update(updates)

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

    # ── Agent Memory ──────────────────────────────────────────────────────────

    async def record_agent_outcome(
        self,
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
            db = await self._get_db()
            now = time.time()
            async with self._transaction():
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

    async def get_agent_strategies(self, agent_type: str, query_pattern: str = "") -> list[dict]:
        with trace_span("memory.get_agent_strategies", {"agent_type": agent_type}):
            db = await self._get_db()
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

    # ── Project Memory ────────────────────────────────────────────────────────

    async def get_project_profile(self, kb_name: str) -> dict | None:
        with trace_span("memory.get_project_profile", {"kb_name": kb_name}):
            db = await self._get_db()
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

    async def update_project_profile(self, kb_name: str, profile: dict) -> None:
        with trace_span("memory.update_project_profile", {"kb_name": kb_name}):
            db = await self._get_db()
            now = time.time()
            existing = await self.get_project_profile(kb_name)
            doc_count = profile.get("document_count", existing["document_count"] if existing else 0)
            total_pages = profile.get("total_pages", existing["total_pages"] if existing else 0)
            profile_filtered = {
                k: v for k, v in profile.items() if k not in ("document_count", "total_pages")
            }

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

    # ── Maintenance ───────────────────────────────────────────────────────────

    async def decay_old_facts(self, days: int = 30, decay_rate: float = 0.1) -> int:
        with trace_span("memory.decay_old_facts", {"days": days, "decay_rate": decay_rate}):
            db = await self._get_db()
            cutoff = time.time() - days * 86400
            async with self._transaction():
                rows = await db.execute_fetchall(
                    """SELECT id, confidence FROM facts
                       WHERE archived = 0 AND created_at < ?""",
                    (cutoff,),
                )

                count = 0
                for fact_id, conf in rows:
                    new_conf = max(0.0, conf - decay_rate)
                    if new_conf <= 0.0:
                        await db.execute("UPDATE facts SET archived = 1 WHERE id = ?", (fact_id,))
                    else:
                        await db.execute(
                            "UPDATE facts SET confidence = ? WHERE id = ?", (new_conf, fact_id)
                        )
                    count += 1

                return count

    async def compact_episodes(self, older_than_days: int = 90) -> int:
        with trace_span("memory.compact_episodes", {"older_than_days": older_than_days}):
            db = await self._get_db()
            cutoff = time.time() - older_than_days * 86400
            rows = await db.execute_fetchall(
                """SELECT id, device_id, session_type, query
                   FROM episodes
                   WHERE archived = 0 AND created_at < ? AND outcome_rating < 0.3""",
                (cutoff,),
            )
            if not rows:
                return 0
            episode_ids = [r[0] for r in rows]
            placeholders = ",".join("?" * len(episode_ids))
            await db.execute(
                f"UPDATE episodes SET archived = 1 WHERE id IN ({placeholders})",
                episode_ids,
            )
            await db.commit()
            for ep_id, device_id, session_type, query in rows:
                summary = f"Session summary ({session_type}): {query[:200]}"
                await self.store_fact(
                    device_id=device_id,
                    content=summary,
                    source_type="session_summary",
                    source_id=ep_id,
                )
            return len(episode_ids)

    async def get_stats(self, device_id: str | None = None) -> dict:
        with trace_span("memory.get_stats", {"device_id": device_id}):
            db = await self._get_db()

            if device_id:
                ep_row = await db.execute_fetchall(
                    "SELECT COUNT(*) FROM episodes WHERE device_id = ? AND archived = 0",
                    (device_id,),
                )
                fact_row = await db.execute_fetchall(
                    "SELECT COUNT(*) FROM facts WHERE device_id = ? AND archived = 0",
                    (device_id,),
                )
                profile_row = await db.execute_fetchall(
                    "SELECT COUNT(*) FROM user_profiles WHERE device_id = ?",
                    (device_id,),
                )
                usage_rows = await db.execute_fetchall(
                    "SELECT metric_name, SUM(metric_value) as total FROM memory_usage WHERE device_id = ? AND timestamp > datetime('now', '-7 days') GROUP BY metric_name",
                    (device_id,),
                )
                return {
                    "episodes": ep_row[0][0] if ep_row else 0,
                    "facts": fact_row[0][0] if fact_row else 0,
                    "profiles": profile_row[0][0] if profile_row else 0,
                    "usage_7d": {r[0]: r[1] for r in usage_rows},
                }

            ep_total = await db.execute_fetchall("SELECT COUNT(*) FROM episodes")
            ep_active = await db.execute_fetchall(
                "SELECT COUNT(*) FROM episodes WHERE archived = 0"
            )
            fact_total = await db.execute_fetchall("SELECT COUNT(*) FROM facts")
            fact_active = await db.execute_fetchall("SELECT COUNT(*) FROM facts WHERE archived = 0")
            profile_count = await db.execute_fetchall("SELECT COUNT(*) FROM user_profiles")
            agent_count = await db.execute_fetchall("SELECT COUNT(*) FROM agent_outcomes")
            strategy_count = await db.execute_fetchall("SELECT COUNT(*) FROM agent_strategies")
            project_count = await db.execute_fetchall("SELECT COUNT(*) FROM project_profiles")

            return {
                "episodes_total": ep_total[0][0] if ep_total else 0,
                "episodes_active": ep_active[0][0] if ep_active else 0,
                "facts_total": fact_total[0][0] if fact_total else 0,
                "facts_active": fact_active[0][0] if fact_active else 0,
                "profiles": profile_count[0][0] if profile_count else 0,
                "agent_outcomes": agent_count[0][0] if agent_count else 0,
                "agent_strategies": strategy_count[0][0] if strategy_count else 0,
                "projects": project_count[0][0] if project_count else 0,
            }

    async def track_usage(self, device_id: str, metric_name: str, metric_value: float):
        db = await self._get_db()
        await db.execute(
            "INSERT OR IGNORE INTO memory_usage (device_id, metric_name, metric_value) VALUES (?, ?, ?)",
            (device_id, metric_name, metric_value),
        )
        await db.commit()

    async def get_usage(self, device_id: str, metric_name: str = None, hours: int = 24) -> list:
        db = await self._get_db()
        if metric_name:
            rows = await db.execute_fetchall(
                "SELECT timestamp, metric_name, metric_value FROM memory_usage WHERE device_id = ? AND metric_name = ? AND timestamp > datetime('now', ?) ORDER BY timestamp DESC",
                (device_id, metric_name, f"-{hours} hours"),
            )
        else:
            rows = await db.execute_fetchall(
                "SELECT timestamp, metric_name, metric_value FROM memory_usage WHERE device_id = ? AND timestamp > datetime('now', ?) ORDER BY timestamp DESC",
                (device_id, f"-{hours} hours"),
            )
        return [{"timestamp": r[0], "metric_name": r[1], "metric_value": r[2]} for r in rows]

    async def close(self):
        if self._db:
            await self._db.close()
            self._db = None
