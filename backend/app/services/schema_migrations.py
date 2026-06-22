"""Schema migration framework with version tracking.

Replaces ad-hoc `_migrate_*` calls that run on every startup.
Each migration has a version number and is applied exactly once,
tracked in the `schema_versions` table.
"""

import logging

logger = logging.getLogger(__name__)

SCHEMA_VERSIONS_DDL = """
CREATE TABLE IF NOT EXISTS schema_versions (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT NOT NULL
);
"""


async def apply_migrations(db, migrations: list[tuple[int, str]]) -> int:
    """Apply all unapplied migrations in version order. Returns count applied.

    `migrations` is a list of (version, description) tuples.
    The caller must check versions and run the corresponding logic.
    """
    await db.executescript(SCHEMA_VERSIONS_DDL)
    await db.commit()

    cursor = await db.execute("SELECT MAX(version) FROM schema_versions")
    row = await cursor.fetchone()
    current = row[0] if row[0] is not None else 0

    unapplied = [(v, d) for v, d in migrations if v > current]
    if not unapplied:
        return 0

    logger.info("Found %d unapplied migration(s) (current version: %d)", len(unapplied), current)
    return len(unapplied)


async def mark_migration_applied(db, version: int, description: str) -> None:
    """Record that a migration has been successfully applied."""
    await db.execute(
        "INSERT INTO schema_versions (version, description) VALUES (?, ?)",
        (version, description),
    )
    await db.commit()
    logger.info("Migration v%d applied: %s", version, description)

