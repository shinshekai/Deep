import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import aiosqlite

from app.services.schema_migrations import apply_migrations, mark_migration_applied
from app.services.telemetry import trace_span
from app.services.memory.episodes import (
    store_episode as _store_episode_impl,
    recall_episodes as _recall_episodes_impl,
    get_episode as _get_episode_impl,
    delete_episode as _delete_episode_impl,
    rate_episode as _rate_episode_impl,
    list_episodes as _list_episodes_impl,
    update_episode_rating as _update_episode_rating_impl,
    _store_chunks as _store_chunks_fn,
)
from app.services.memory.facts import (
    store_fact as _store_fact_impl,
    recall_facts as _recall_facts_impl,
    detect_contradictions as _detect_contradictions_impl,
    batch_resolve_contradictions as _batch_resolve_contradictions_impl,
    resolve_contradiction as _resolve_contradiction_impl,
)
from app.services.memory.observations import (
    stage_observation as _stage_observation_impl,
    crystallize_observations as _crystallize_observations_impl,
    get_staged_observations as _get_staged_observations_impl,
)
from app.services.memory.dead_ends import (
    store_dead_end as _store_dead_end_impl,
    recall_dead_ends as _recall_dead_ends_impl,
    get_dead_end_preventions as _get_dead_end_preventions_impl,
)
from app.services.memory.profiles import (
    get_profile as _get_profile_impl,
    update_profile as _update_profile_impl,
    record_agent_outcome as _record_agent_outcome_impl,
    get_agent_strategies as _get_agent_strategies_impl,
    get_project_profile as _get_project_profile_impl,
    update_project_profile as _update_project_profile_impl,
    get_l3 as _get_l3_impl,
    get_l3_all as _get_l3_all_impl,
    update_l3_preference as _update_l3_preference_impl,
    read_l3_concat as _read_l3_concat_impl,
    upgrade_provenance as _upgrade_provenance_impl,
    get_provenance_lineage as _get_provenance_lineage_impl,
)

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

CREATE TABLE IF NOT EXISTS episode_chunks (
    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY (source_id) REFERENCES episodes(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts USING fts5(
    chunk_text,
    content='',
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

CREATE TABLE IF NOT EXISTS fact_chunks (
    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY (source_id) REFERENCES facts(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
    chunk_text,
    content='',
    tokenize='porter unicode61'
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

CREATE TABLE IF NOT EXISTS staged_observations (
    id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    content TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    metadata TEXT,
    created_at REAL NOT NULL,
    crystallized INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_staged_device ON staged_observations(device_id, crystallized);

CREATE TABLE IF NOT EXISTS dead_ends (
    id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    title TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    approach TEXT NOT NULL,
    failure_mode TEXT NOT NULL,
    failure_evidence TEXT,
    lesson TEXT NOT NULL,
    parent_node_id TEXT,
    parent_node_type TEXT,
    provenance TEXT NOT NULL DEFAULT 'ai-suggested',
    tags TEXT,
    confidence REAL DEFAULT 0.5,
    created_at REAL NOT NULL,
    archived INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_dead_ends_device ON dead_ends(device_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dead_ends_failure_mode ON dead_ends(failure_mode);

CREATE VIRTUAL TABLE IF NOT EXISTS dead_ends_fts USING fts5(
    chunk_text,
    content='',
    tokenize='porter unicode61'
);

CREATE TABLE IF NOT EXISTS dead_end_chunks (
    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY (source_id) REFERENCES dead_ends(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_dead_end_chunks_source ON dead_end_chunks(source_id);

CREATE TABLE IF NOT EXISTS user_l3 (
    device_id TEXT NOT NULL,
    slot TEXT NOT NULL CHECK(slot IN ('profile', 'recent', 'scope', 'preferences')),
    content TEXT NOT NULL DEFAULT '{}',
    entry_count INTEGER NOT NULL DEFAULT 0,
    last_consolidated_at REAL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (device_id, slot)
);
CREATE INDEX IF NOT EXISTS idx_l3_device ON user_l3(device_id);

CREATE TABLE IF NOT EXISTS provenance_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    provenance_type TEXT NOT NULL,
    parent_provenance_id INTEGER,
    original_provenance TEXT,
    reasoning TEXT,
    source_tool TEXT,
    session_id TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_provenance_entity ON provenance_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_provenance_type ON provenance_log(provenance_type);

CREATE TABLE IF NOT EXISTS memory_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f','now')),
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_device ON memory_usage(device_id);
CREATE INDEX IF NOT EXISTS idx_usage_metric ON memory_usage(metric_name);
CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON memory_usage(timestamp);

CREATE INDEX IF NOT EXISTS idx_episodes_device_created ON episodes(device_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_episodes_device_archived ON episodes(device_id, archived);
CREATE INDEX IF NOT EXISTS idx_episode_chunks_source ON episode_chunks(source_id);
CREATE INDEX IF NOT EXISTS idx_facts_device_created ON facts(device_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_facts_device_archived ON facts(device_id, archived);
CREATE INDEX IF NOT EXISTS idx_fact_chunks_source ON fact_chunks(source_id);
CREATE INDEX IF NOT EXISTS idx_agent_outcomes_device ON agent_outcomes(device_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_outcomes_type ON agent_outcomes(agent_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_strategies_pattern ON agent_strategies(agent_type, pattern_signature);
CREATE UNIQUE INDEX IF NOT EXISTS idx_facts_summary_unique ON facts(source_type, source_id) WHERE source_type = 'session_summary' AND source_id IS NOT NULL;
"""

FTS_SYNC_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS episode_chunks_ai AFTER INSERT ON episode_chunks BEGIN
    INSERT INTO episodes_fts(rowid, chunk_text)
    VALUES (new.chunk_id, new.chunk_text);
END;

CREATE TRIGGER IF NOT EXISTS episode_chunks_ad AFTER DELETE ON episode_chunks BEGIN
    INSERT INTO episodes_fts(episodes_fts, rowid, chunk_text)
    VALUES ('delete', old.chunk_id, old.chunk_text);
END;

CREATE TRIGGER IF NOT EXISTS episode_chunks_au AFTER UPDATE ON episode_chunks BEGIN
    INSERT INTO episodes_fts(episodes_fts, rowid, chunk_text)
    VALUES ('delete', old.chunk_id, old.chunk_text);
    INSERT INTO episodes_fts(rowid, chunk_text)
    VALUES (new.chunk_id, new.chunk_text);
END;

CREATE TRIGGER IF NOT EXISTS fact_chunks_ai AFTER INSERT ON fact_chunks BEGIN
    INSERT INTO facts_fts(rowid, chunk_text)
    VALUES (new.chunk_id, new.chunk_text);
END;

CREATE TRIGGER IF NOT EXISTS fact_chunks_ad AFTER DELETE ON fact_chunks BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, chunk_text)
    VALUES ('delete', old.chunk_id, old.chunk_text);
END;

CREATE TRIGGER IF NOT EXISTS fact_chunks_au AFTER UPDATE ON fact_chunks BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, chunk_text)
    VALUES ('delete', old.chunk_id, old.chunk_text);
    INSERT INTO facts_fts(rowid, chunk_text)
    VALUES (new.chunk_id, new.chunk_text);
END;

CREATE TRIGGER IF NOT EXISTS dead_end_chunks_ai AFTER INSERT ON dead_end_chunks BEGIN
    INSERT INTO dead_ends_fts(rowid, chunk_text)
    VALUES (new.chunk_id, new.chunk_text);
END;

CREATE TRIGGER IF NOT EXISTS dead_end_chunks_ad AFTER DELETE ON dead_end_chunks BEGIN
    INSERT INTO dead_ends_fts(dead_ends_fts, rowid, chunk_text)
    VALUES ('delete', old.chunk_id, old.chunk_text);
END;

CREATE TRIGGER IF NOT EXISTS dead_end_chunks_au AFTER UPDATE ON dead_end_chunks BEGIN
    INSERT INTO dead_ends_fts(dead_ends_fts, rowid, chunk_text)
    VALUES ('delete', old.chunk_id, old.chunk_text);
    INSERT INTO dead_ends_fts(rowid, chunk_text)
    VALUES (new.chunk_id, new.chunk_text);
END;
"""


class MemoryService:
    def __init__(self, db_path: str = "data/memory/deep_memory.db"):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None
        self._resolved_path: Path | None = None
        self._profile_backoff_state: dict[str, float] = {}
        self._write_lock = asyncio.Lock()
        self._last_health_check: float = 0.0

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
        self._resolved_path = db_path

        self._db = await aiosqlite.connect(str(db_path))
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.execute("PRAGMA busy_timeout=5000")
        await self._db.execute("PRAGMA journal_size_limit=67108864")
        await self._db.execute("PRAGMA cache_size=-8192")
        await self._db.executescript(SCHEMA_SQL)
        await self._db.executescript(FTS_SYNC_TRIGGERS)
        await self._db.commit()

        migrations = [
            (1, "FTS5 porter unicode61 tokenizer", self._migrate_fts_tokenizer),
            (2, "Add provenance columns", self._migrate_provenance),
        ]
        pending = await apply_migrations(self._db, [(v, d) for v, d, _ in migrations])
        if pending > 0:
            cursor = await self._db.execute("SELECT MAX(version) FROM schema_versions")
            row = await cursor.fetchone()
            current = row[0] if row[0] is not None else 0
            for v, desc, fn in migrations:
                if v > current:
                    try:
                        await fn()
                        await mark_migration_applied(self._db, v, desc)
                    except Exception as e:
                        logger.warning("Migration v%d (%s) failed: %s", v, desc, e)

        recovered = await self.recover_partial_compactions()
        if recovered:
            logger.info("Startup recovery: fixed %d orphaned compacted episodes", recovered)
        logger.info(f"MemoryService initialized at {db_path}")

    async def _migrate_fts_tokenizer(self):
        db = self._db
        for table_name in ("episodes_fts", "facts_fts"):
            try:
                row = await db.execute_fetchall(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,),
                )
                if not row:
                    continue
                sql = row[0][0] or ""
                if "content=" in sql and "content=''" not in sql:
                    logger.info(f"Migrating {table_name} to contentless FTS5 with chunks")
                    chunk_table = (
                        "episode_chunks" if table_name == "episodes_fts" else "fact_chunks"
                    )
                    source_table = "episodes" if table_name == "episodes_fts" else "facts"
                    col = (
                        "content"
                        if table_name == "facts_fts"
                        else "query || char(10) || char(10) || answer"
                    )
                    await db.execute(f"DROP TABLE IF EXISTS {table_name}")
                    await db.execute(
                        f"CREATE VIRTUAL TABLE {table_name} USING fts5("
                        f"chunk_text, content='',"
                        f"tokenize='porter unicode61')"
                    )
                    rows = await db.execute_fetchall(
                        f"SELECT id, device_id, created_at FROM {source_table}"
                    )
                    for source_row in rows:
                        sid, did, created = source_row
                        text_row = await db.execute_fetchall(
                            f"SELECT {col} FROM {source_table} WHERE id = ?", (sid,)
                        )
                        if text_row and text_row[0][0]:
                            await _store_chunks_fn(db, chunk_table, sid, did, text_row[0][0], created)
                    await db.commit()
                elif "porter" not in sql:
                    logger.info(f"Migrating {table_name} to porter unicode61 tokenizer")
                    await db.execute(f"DROP TABLE IF EXISTS {table_name}")
                    await db.execute(
                        f"CREATE VIRTUAL TABLE {table_name} USING fts5("
                        f"chunk_text, content='',"
                        f"tokenize='porter unicode61')"
                    )
                    await db.commit()
            except Exception as e:
                logger.warning(f"FTS5 migration for {table_name} failed: {e}")

    async def _migrate_provenance(self):
        db = self._db
        for table in ("episodes", "facts", "agent_outcomes"):
            try:
                row = await db.execute_fetchall("PRAGMA table_info(" + table + ")")
                cols = [r[1] for r in row] if row else []
                if "provenance" not in cols:
                    default = "ai-executed" if table == "agent_outcomes" else "user"
                    await db.execute(
                        f"ALTER TABLE {table} ADD COLUMN provenance TEXT NOT NULL DEFAULT '{default}'"
                    )
                    await db.commit()
                    logger.info("Added provenance column to %s", table)
            except Exception as e:
                logger.warning("Provenance migration for %s skipped: %s", table, e)

    async def _get_db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("MemoryService not initialized — call initialize() first")
        now = time.time()
        if now - self._last_health_check > 30.0:
            self._last_health_check = now
            try:
                await self._db.execute("SELECT 1")
            except Exception:
                logger.warning("Database connection unhealthy, reconnecting")
                await self._reconnect()
        return self._db

    async def _reconnect(self):
        async with self._write_lock:
            with suppress(Exception):
                await self._db.close()
            self._db = await aiosqlite.connect(str(self._resolved_path))
            await self._db.execute("PRAGMA journal_mode=WAL")
            await self._db.execute("PRAGMA busy_timeout=5000")
            await self._db.execute("PRAGMA foreign_keys=ON")
            await self._db.execute("PRAGMA journal_size_limit=67108864")
            await self._db.execute("PRAGMA cache_size=-8192")

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
        provenance: str = "user",
    ) -> str:
        return await _store_episode_impl(
            await self._get_db(), self._write_lock,
            device_id, query, answer, agents, model_used, tier,
            citations, session_type, provenance,
        )

    async def recall_episodes(self, device_id: str, query: str, top_k: int = 5) -> list[dict]:
        return await _recall_episodes_impl(
            await self._get_db(), self._write_lock, device_id, query, top_k,
        )

    async def get_episode(self, episode_id: str) -> dict | None:
        return await _get_episode_impl(await self._get_db(), episode_id)

    async def delete_episode(self, episode_id: str) -> bool:
        return await _delete_episode_impl(await self._get_db(), self._write_lock, episode_id)

    async def rate_episode(self, device_id: str, episode_id: str, rating: float) -> bool:
        return await _rate_episode_impl(
            await self._get_db(), self._write_lock, device_id, episode_id, rating,
        )

    async def list_episodes(self, device_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
        return await _list_episodes_impl(await self._get_db(), device_id, limit, offset)

    # ── Progressive Crystallization ─────────────────────────────────────────

    async def stage_observation(
        self,
        device_id: str,
        content: str,
        source_type: str = "observation",
        source_id: str = "",
        confidence: float = 0.5,
        metadata: dict | None = None,
    ) -> str:
        return await _stage_observation_impl(
            await self._get_db(), self._write_lock,
            device_id, content, source_type, source_id, confidence, metadata,
        )

    async def crystallize_observations(self, device_id: str) -> int:
        return await _crystallize_observations_impl(
            await self._get_db(), self._write_lock, device_id,
        )

    async def get_staged_observations(self, device_id: str) -> list[dict]:
        return await _get_staged_observations_impl(await self._get_db(), device_id)

    # ── Facts ─────────────────────────────────────────────────────────────────

    async def store_fact(
        self,
        device_id: str,
        content: str,
        source_type: str = "conversation",
        source_id: str = "",
        confidence: float = 0.5,
        provenance: str = "user",
    ) -> str:
        return await _store_fact_impl(
            await self._get_db(), self._write_lock,
            device_id, content, source_type, source_id, confidence, provenance,
        )

    async def recall_facts(self, device_id: str, query: str, top_k: int = 10) -> list[dict]:
        return await _recall_facts_impl(
            await self._get_db(), self._write_lock, device_id, query, top_k,
        )

    async def detect_contradictions(self, new_fact: str, device_id: str) -> list[dict]:
        return await _detect_contradictions_impl(await self._get_db(), new_fact, device_id)

    async def batch_resolve_contradictions(self, device_id: str, batch_size: int = 10) -> dict:
        return await _batch_resolve_contradictions_impl(await self._get_db(), device_id, batch_size)

    async def resolve_contradiction(
        self, device_id: str, fact_ids: list[str], keep: str, merge: bool = True
    ) -> dict:
        return await _resolve_contradiction_impl(
            await self._get_db(), self._write_lock, device_id, fact_ids, keep, merge,
        )

    # ── User Profile ──────────────────────────────────────────────────────────

    async def get_profile(self, device_id: str) -> dict:
        return await _get_profile_impl(
            await self._get_db(), self._profile_backoff_state, device_id,
        )

    async def update_profile(self, device_id: str, updates: dict) -> dict:
        return await _update_profile_impl(
            await self._get_db(), self._write_lock, self._profile_backoff_state, device_id, updates,
        )

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
        return await _record_agent_outcome_impl(
            await self._get_db(), self._write_lock,
            agent_type, query_pattern, strategy, outcome_quality, device_id, model_used, tier,
        )

    async def get_agent_strategies(self, agent_type: str, query_pattern: str = "") -> list[dict]:
        return await _get_agent_strategies_impl(await self._get_db(), agent_type, query_pattern)

    # ── Project Memory ────────────────────────────────────────────────────────

    async def get_project_profile(self, kb_name: str) -> dict | None:
        return await _get_project_profile_impl(await self._get_db(), kb_name)

    async def update_project_profile(self, kb_name: str, profile: dict) -> None:
        return await _update_project_profile_impl(
            await self._get_db(), self._write_lock, kb_name, profile,
        )

    # ── Maintenance ───────────────────────────────────────────────────────────

    async def decay_old_facts(self, days: int = 30, decay_rate: float = 0.1) -> int:
        with trace_span("memory.decay_old_facts", {"days": days, "decay_rate": decay_rate}):
            db = await self._get_db()
            cutoff = time.time() - days * 86400
            async with self._write_lock, self._transaction():
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

    async def update_episode_rating(self, episode_id: str, rating: float) -> bool:
        return await _update_episode_rating_impl(
            await self._get_db(), self._write_lock, episode_id, rating,
        )

    async def compact_episodes(self, older_than_days: int = 90) -> int:
        with trace_span("memory.compact_episodes", {"older_than_days": older_than_days}):
            async with self._write_lock:
                db = await self._get_db()
                cutoff = time.time() - older_than_days * 86400
                rows = await db.execute_fetchall(
                    """SELECT id, device_id, session_type, query, answer, citations, outcome_rating
                       FROM episodes
                       WHERE archived = 0 AND created_at < ?""",
                    (cutoff,),
                )
                if not rows:
                    return 0
                episode_ids = [r[0] for r in rows]
                now = time.time()
                try:
                    await db.execute("BEGIN IMMEDIATE")
                    placeholders = ",".join("?" * len(episode_ids))
                    await db.execute(
                        f"UPDATE episodes SET archived = 1 WHERE id IN ({placeholders})",
                        episode_ids,
                    )
                    for (
                        ep_id,
                        device_id,
                        session_type,
                        query,
                        answer,
                        citations_json,
                        rating,
                    ) in rows:
                        answer_snippet = (answer or "")[:300]
                        citations = json.loads(citations_json) if citations_json else []
                        citation_summary = f" [{len(citations)} sources]" if citations else ""
                        rating_str = f" (rating={rating:.1f})" if rating else ""
                        summary = f"Session ({session_type}){rating_str}: Q: {query[:200]} A: {answer_snippet}{citation_summary}"
                        fact_id = uuid.uuid4().hex[:12]
                        await db.execute(
                            """INSERT INTO facts
                               (id, device_id, content, source_type, source_id,
                                confidence, created_at, last_accessed, access_count, provenance)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                               ON CONFLICT(source_type, source_id)
                               WHERE source_type = 'session_summary' AND source_id IS NOT NULL
                               DO NOTHING""",
                            (
                                fact_id,
                                device_id,
                                summary,
                                "session_summary",
                                ep_id,
                                0.5,
                                now,
                                now,
                                0,
                                "ai-executed",
                            ),
                        )
                    await db.commit()
                except Exception:
                    try:
                        await db.execute("ROLLBACK")
                    except Exception:
                        logger.exception(
                            "Failed to rollback compact_episodes, invalidating connection"
                        )
                        self._db = None
                    raise
                device_counts: dict[str, int] = {}
                for r in rows:
                    did = r[1]
                    device_counts[did] = device_counts.get(did, 0) + 1
                for did, count in device_counts.items():
                    await self._track_usage_nolock(did, "episodes_compacted", count)
                return len(episode_ids)

    async def recover_partial_compactions(self) -> int:
        db = await self._get_db()
        orphaned = await db.execute_fetchall(
            """SELECT e.id, e.device_id, e.session_type, e.query
               FROM episodes e
               WHERE e.archived = 1
                 AND NOT EXISTS (
                   SELECT 1 FROM facts f
                   WHERE f.source_type = 'session_summary' AND f.source_id = e.id
                 )"""
        )
        if not orphaned:
            return 0
        now = time.time()
        async with self._write_lock:
            try:
                await db.execute("BEGIN IMMEDIATE")
                for ep_id, device_id, session_type, query in orphaned:
                    summary = f"Session summary ({session_type}): {query[:200]}"
                    fact_id = uuid.uuid4().hex[:12]
                    await db.execute(
                        """INSERT OR IGNORE INTO facts
                           (id, device_id, content, source_type, source_id,
                            confidence, created_at, last_accessed, access_count)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (fact_id, device_id, summary, "session_summary", ep_id, 0.5, now, now, 0),
                    )
                await db.commit()
            except Exception:
                try:
                    await db.execute("ROLLBACK")
                except Exception:
                    logger.exception("Failed to rollback recovery")
                raise
        logger.info("Recovered %d orphaned compacted episodes", len(orphaned))
        return len(orphaned)

    # ── Dead Ends (A4) ────────────────────────────────────────────────────

    async def store_dead_end(
        self,
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
        return await _store_dead_end_impl(
            await self._get_db(), self._write_lock,
            device_id, title, hypothesis, approach, failure_mode, lesson,
            provenance, failure_evidence, parent_node_id, parent_node_type, tags,
        )

    async def recall_dead_ends(self, device_id: str, query: str, top_k: int = 5) -> list[dict]:
        return await _recall_dead_ends_impl(await self._get_db(), device_id, query, top_k)

    async def get_dead_end_preventions(
        self, device_id: str, approach_description: str
    ) -> list[dict]:
        return await _get_dead_end_preventions_impl(
            await self._get_db(), device_id, approach_description,
        )

    # ── L3 Cross-Surface Synthesis (A3) ───────────────────────────────────

    async def get_l3(self, device_id: str, slot: str) -> dict:
        return await _get_l3_impl(await self._get_db(), device_id, slot)

    async def get_l3_all(self, device_id: str) -> dict:
        return await _get_l3_all_impl(await self._get_db(), device_id)

    async def update_l3_preference(self, device_id: str, updates: dict) -> dict:
        return await _update_l3_preference_impl(
            await self._get_db(), self._write_lock, device_id, updates,
        )

    async def read_l3_concat(self, device_id: str) -> str:
        return await _read_l3_concat_impl(await self._get_db(), device_id)

    # ── Provenance (A5) ───────────────────────────────────────────────────

    async def upgrade_provenance(
        self,
        entity_type: str,
        entity_id: str,
        new_provenance: str,
        reasoning: str = "",
    ) -> bool:
        return await _upgrade_provenance_impl(
            await self._get_db(), self._write_lock, entity_type, entity_id,
            new_provenance, reasoning,
        )

    async def get_provenance_lineage(self, entity_type: str, entity_id: str) -> list[dict]:
        return await _get_provenance_lineage_impl(await self._get_db(), entity_type, entity_id)

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
                de_row = await db.execute_fetchall(
                    "SELECT COUNT(*) FROM dead_ends WHERE device_id = ?",
                    (device_id,),
                )
                strat_row = await db.execute_fetchall(
                    "SELECT COUNT(*) FROM agent_strategies WHERE device_id = ?",
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
                    "total_dead_ends": de_row[0][0] if de_row else 0,
                    "total_strategies": strat_row[0][0] if strat_row else 0,
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

    async def _track_usage_nolock(
        self, device_id: str, metric_name: str, metric_value: float
    ) -> None:
        """Insert a usage metric WITHOUT acquiring _write_lock.

        For internal callers that already hold _write_lock (asyncio.Lock is
        non-reentrant, so re-acquiring it on the same task would deadlock).
        """
        db = await self._get_db()
        await db.execute(
            "INSERT INTO memory_usage (device_id, metric_name, metric_value) VALUES (?, ?, ?)",
            (device_id, metric_name, metric_value),
        )
        await db.commit()

    async def track_usage(self, device_id: str, metric_name: str, metric_value: float):
        async with self._write_lock:
            await self._track_usage_nolock(device_id, metric_name, metric_value)

    async def get_usage(
        self, device_id: str, metric_name: str | None = None, hours: int = 24
    ) -> list:
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

    async def prune_usage(self, retention_days: int = 90) -> int:
        db = await self._get_db()
        async with self._write_lock:
            cursor = await db.execute(
                "DELETE FROM memory_usage WHERE timestamp < datetime('now', ?)",
                (f"-{retention_days} days",),
            )
            await db.commit()
        deleted = cursor.rowcount
        if deleted:
            logger.info("pruned %d memory_usage rows older than %d days", deleted, retention_days)
        return deleted

    async def close(self):
        if self._db:
            await self._db.close()
            self._db = None
