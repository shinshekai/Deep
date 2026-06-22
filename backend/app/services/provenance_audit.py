"""Provenance audit log integrity verification.

Checks the provenance_log for consistency with actual entity tables.
Returns counts of verified, orphaned, and mismatched provenance records.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

ENTITY_TABLES = ["episodes", "facts", "agent_outcomes", "dead_ends"]


async def verify_provenance_integrity(db) -> dict:
    """Verify provenance_log integrity against entity tables.

    Returns:
        dict with total_entries, verified, orphaned (no matching entity),
        mismatched (provenance differs from entity.provenance), table_counts.
    """
    result = {
        "total_entries": 0,
        "verified": 0,
        "orphaned": 0,
        "mismatched": 0,
        "by_table": {},
        "status": "ok",
    }

    cursor = await db.execute("SELECT COUNT(*) FROM provenance_log")
    row = await cursor.fetchone()
    result["total_entries"] = row[0] if row else 0

    if result["total_entries"] == 0:
        result["status"] = "empty"
        return result

    for table in ENTITY_TABLES:
        table_result = {"entries": 0, "verified": 0, "orphaned": 0, "mismatched": 0}

        try:
            rows = await db.execute_fetchall(
                f"""SELECT pl.id, pl.entity_id, pl.provenance_type, pl.original_provenance
                    FROM provenance_log pl
                    WHERE pl.entity_type = ?""",
                (table,),
            )

            if not rows:
                continue

            table_result["entries"] = len(rows)
            for row_data in rows:
                pl_id, entity_id, new_prov, orig_prov = row_data
                entity_row = await db.execute_fetchall(
                    f"SELECT provenance FROM {table} WHERE id = ?", (entity_id,)
                )
                if not entity_row:
                    table_result["orphaned"] += 1
                else:
                    current_prov = entity_row[0][0]
                    if current_prov == new_prov:
                        table_result["verified"] += 1
                    else:
                        table_result["mismatched"] += 1

        except Exception as e:
            logger.warning("Provenance verification failed for table %s: %s", table, e)
            table_result["error"] = str(e)

        result["by_table"][table] = table_result
        result["verified"] += table_result["verified"]
        result["orphaned"] += table_result["orphaned"]
        result["mismatched"] += table_result["mismatched"]

    if result["orphaned"] > 0 or result["mismatched"] > 0:
        result["status"] = "inconsistent"

    logger.info(
        "Provenance integrity: %d total, %d verified, %d orphaned, %d mismatched — %s",
        result["total_entries"], result["verified"],
        result["orphaned"], result["mismatched"], result["status"],
    )
    return result
