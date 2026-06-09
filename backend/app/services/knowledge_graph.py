"""Knowledge Graph service — entity-relation graph for dual-index RAG.

Implements DeepTutor's dual-index pattern: KG + Dense Embeddings.
Stores entities and relations extracted from episodes/facts, enabling
graph-based retrieval alongside vector search.
"""

import json
import logging
import sqlite3
import time
from pathlib import Path

from app.services.telemetry import trace_span

logger = logging.getLogger(__name__)

KG_DB_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "memory" / "knowledge_graph.db"
)


class KnowledgeGraph:
    def __init__(self, db_path: str | Path | None = None):
        self._db_path = Path(db_path) if db_path else KG_DB_PATH
        self._conn: sqlite3.Connection | None = None

    def initialize(self):
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()
        logger.info("Knowledge graph initialized at %s", self._db_path)

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("KnowledgeGraph not initialized")
        return self._conn

    def add_entity(
        self,
        name: str,
        entity_type: str,
        device_id: str,
        metadata: dict | None = None,
        confidence: float = 0.5,
    ) -> str:
        with trace_span("kg.add_entity", {"entity_type": entity_type}):
            conn = self._get_conn()
            entity_id = name.lower().strip().replace(" ", "_")
            now = time.time()
            conn.execute(
                """INSERT INTO kg_entities (id, name, entity_type, device_id, metadata, confidence, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       confidence = MAX(confidence, excluded.confidence),
                       metadata = COALESCE(excluded.metadata, metadata)""",
                (
                    entity_id,
                    name,
                    entity_type,
                    device_id,
                    json.dumps(metadata or {}),
                    confidence,
                    now,
                ),
            )
            conn.commit()
            return entity_id

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        device_id: str,
        weight: float = 1.0,
        metadata: dict | None = None,
    ) -> str:
        with trace_span("kg.add_relation", {"relation_type": relation_type}):
            conn = self._get_conn()
            relation_id = f"{source_id}:{relation_type}:{target_id}"
            now = time.time()
            conn.execute(
                """INSERT INTO kg_relations (id, source_id, target_id, relation_type, device_id, weight, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       weight = MAX(weight, excluded.weight)""",
                (
                    relation_id,
                    source_id,
                    target_id,
                    relation_type,
                    device_id,
                    weight,
                    json.dumps(metadata or {}),
                    now,
                ),
            )
            conn.commit()
            return relation_id

    def query_entities(
        self, entity_type: str | None = None, device_id: str | None = None, limit: int = 50
    ) -> list[dict]:
        conn = self._get_conn()
        sql = "SELECT id, name, entity_type, device_id, confidence, created_at FROM kg_entities WHERE 1=1"
        params: list = []
        if entity_type:
            sql += " AND entity_type = ?"
            params.append(entity_type)
        if device_id:
            sql += " AND device_id = ?"
            params.append(device_id)
        sql += " ORDER BY confidence DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [
            {
                "id": r[0],
                "name": r[1],
                "entity_type": r[2],
                "device_id": r[3],
                "confidence": r[4],
                "created_at": r[5],
            }
            for r in rows
        ]

    def query_relations(
        self, entity_id: str, direction: str = "both", limit: int = 50
    ) -> list[dict]:
        conn = self._get_conn()
        if direction == "outgoing":
            sql = """SELECT id, source_id, target_id, relation_type, weight, created_at
                     FROM kg_relations WHERE source_id = ? ORDER BY weight DESC LIMIT ?"""
            rows = conn.execute(sql, (entity_id, limit)).fetchall()
        elif direction == "incoming":
            sql = """SELECT id, source_id, target_id, relation_type, weight, created_at
                     FROM kg_relations WHERE target_id = ? ORDER BY weight DESC LIMIT ?"""
            rows = conn.execute(sql, (entity_id, limit)).fetchall()
        else:
            sql = """SELECT id, source_id, target_id, relation_type, weight, created_at
                     FROM kg_relations WHERE source_id = ? OR target_id = ?
                     ORDER BY weight DESC LIMIT ?"""
            rows = conn.execute(sql, (entity_id, entity_id, limit)).fetchall()
        return [
            {
                "id": r[0],
                "source_id": r[1],
                "target_id": r[2],
                "relation_type": r[3],
                "weight": r[4],
                "created_at": r[5],
            }
            for r in rows
        ]

    def search_by_name(
        self, query: str, device_id: str | None = None, limit: int = 10
    ) -> list[dict]:
        conn = self._get_conn()
        sql = """SELECT id, name, entity_type, device_id, confidence
                 FROM kg_entities WHERE name LIKE ?"""
        params: list = [f"%{query}%"]
        if device_id:
            sql += " AND device_id = ?"
            params.append(device_id)
        sql += " ORDER BY confidence DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [
            {"id": r[0], "name": r[1], "entity_type": r[2], "device_id": r[3], "confidence": r[4]}
            for r in rows
        ]

    def get_entity_neighbors(self, entity_id: str, depth: int = 1, limit: int = 20) -> dict:
        visited = set()
        result = {"entity": entity_id, "neighbors": []}

        def _traverse(eid: str, d: int):
            if d > depth or eid in visited:
                return
            visited.add(eid)
            rels = self.query_relations(eid, limit=limit)
            for rel in rels:
                neighbor = rel["target_id"] if rel["source_id"] == eid else rel["source_id"]
                if neighbor not in visited:
                    result["neighbors"].append(
                        {
                            "entity_id": neighbor,
                            "relation": rel["relation_type"],
                            "weight": rel["weight"],
                        }
                    )
                    _traverse(neighbor, d + 1)

        _traverse(entity_id, 0)
        return result

    def stats(self) -> dict:
        conn = self._get_conn()
        entity_count = conn.execute("SELECT COUNT(*) FROM kg_entities").fetchone()[0]
        relation_count = conn.execute("SELECT COUNT(*) FROM kg_relations").fetchone()[0]
        type_counts = conn.execute(
            "SELECT entity_type, COUNT(*) FROM kg_entities GROUP BY entity_type"
        ).fetchall()
        return {
            "entity_count": entity_count,
            "relation_count": relation_count,
            "entity_types": {r[0]: r[1] for r in type_counts},
        }


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS kg_entities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    device_id TEXT NOT NULL,
    metadata TEXT,
    confidence REAL DEFAULT 0.5,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_kg_entities_type ON kg_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_kg_entities_device ON kg_entities(device_id);
CREATE INDEX IF NOT EXISTS idx_kg_entities_name ON kg_entities(name);

CREATE TABLE IF NOT EXISTS kg_relations (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    device_id TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    metadata TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_kg_relations_source ON kg_relations(source_id);
CREATE INDEX IF NOT EXISTS idx_kg_relations_target ON kg_relations(target_id);
CREATE INDEX IF NOT EXISTS idx_kg_relations_type ON kg_relations(relation_type);
"""

_kg: KnowledgeGraph | None = None


def get_knowledge_graph() -> KnowledgeGraph:
    global _kg
    if _kg is None:
        _kg = KnowledgeGraph()
    return _kg
