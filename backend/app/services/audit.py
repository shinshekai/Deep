"""Security / compliance audit trail with SQLite persistence.

Structured audit events logged to both Python logger (SIEM feed) and
SQLite audit_events table (queryable, exportable). Pattern from
Simon Willison's sqlite-history-json approach.
"""

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("app.audit")

AUDIT_DB = Path("data/audit/audit_events.db")

AUDIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event TEXT NOT NULL,
    timestamp REAL NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_audit_event ON audit_events(event);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_events(timestamp);
"""

EVENT_CATALOG = {
    "auth.ws_failure": "WebSocket authentication failure",
    "auth.ws_success": "WebSocket authentication success",
    "auth.token_generated": "New auth token generated",
    "config.field_changed": "Runtime configuration field modified",
    "config.secret_rotated": "API key or secret rotated",
    "config.settings_saved": "Settings saved via frontend",
    "kb.upload": "Document uploaded to knowledge base",
    "kb.delete": "Document deleted from knowledge base",
    "model.load": "LLM model loaded into GPU memory",
    "model.unload": "LLM model unloaded from GPU memory",
    "model.select": "Model selected for tier slot",
    "solve.started": "Solve pipeline initiated",
    "solve.completed": "Solve pipeline completed",
    "solve.failed": "Solve pipeline error",
    "query.executed": "Query executed against KB",
    "backup.created": "Knowledge base backup created",
    "backup.restored": "Knowledge base backup restored",
    "data.exported": "User data export requested",
    "data.deleted": "User data deletion requested",
    "provider.health_check": "Model provider health check",
    "provider.config_saved": "Provider configuration saved",
    "cache.evicted": "VRAM cache entry evicted",
    "memory.episode_stored": "Memory episode stored",
    "memory.fact_stored": "Memory fact extracted and stored",
    "memory.dead_end_stored": "Dead end recorded in exploration DAG",
    "provenance.upgraded": "Entity provenance tag upgraded",
    "maintenance.cleanup": "Maintenance cleanup session executed",
}


def _get_db() -> sqlite3.Connection:
    AUDIT_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(AUDIT_DB))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(AUDIT_SCHEMA)
    return conn


def audit(event: str, **fields: Any) -> None:
    """Emit a structured audit log entry to both logger and SQLite."""

    # Text logger (existing — SIEM feed)
    parts = [f"event={event}", f"ts={time.time():.3f}"]
    for k, v in sorted(fields.items()):
        if isinstance(v, str):
            parts.append(f"{k}={v!r}")
        else:
            parts.append(f"{k}={v}")
    logger.warning(" ".join(parts))

    # SQLite persistence
    try:
        conn = _get_db()
        conn.execute(
            "INSERT INTO audit_events (event, timestamp, data_json) VALUES (?, ?, ?)",
            (event, time.time(), json.dumps(fields, default=str)),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug("Failed to persist audit event to SQLite: %s", e)


def export_audit_log(
    format: str = "json",
    event_filter: str | None = None,
    limit: int = 1000,
) -> str:
    """Export audit events as JSON or CSV.

    Args:
        format: "json" or "csv"
        event_filter: Optional event type to filter by
        limit: Maximum events to return
    """
    try:
        conn = _get_db()
        if event_filter:
            rows = conn.execute(
                "SELECT event, timestamp, data_json, created_at FROM audit_events WHERE event = ? ORDER BY timestamp DESC LIMIT ?",
                (event_filter, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT event, timestamp, data_json, created_at FROM audit_events ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        conn.close()

        if format == "csv":
            import csv, io

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["event", "timestamp", "data", "created_at"])
            for row in rows:
                writer.writerow([row[0], row[1], row[2], row[3]])
            return output.getvalue()

        # JSON format
        events = []
        for row in rows:
            events.append({
                "event": row[0],
                "timestamp": row[1],
                "data": json.loads(row[2]) if row[2] else {},
                "created_at": row[3],
            })
        return json.dumps(events, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


def get_audit_stats() -> dict:
    """Return audit event statistics."""
    try:
        conn = _get_db()
        total = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        by_type = {}
        for row in conn.execute(
            "SELECT event, COUNT(*) FROM audit_events GROUP BY event ORDER BY COUNT(*) DESC"
        ):
            by_type[row[0]] = row[1]
        conn.close()
        return {"total_events": total, "by_type": by_type, "catalog": EVENT_CATALOG}
    except Exception as e:
        return {"error": str(e)}
