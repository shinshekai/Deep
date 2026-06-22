"""Exploration DAG — tracks solve session outcomes to prevent repeated failures.

Before each solve: query the DAG for similar past approaches.
After each solve: record the outcome (success/dead_end) as a DAG node.

ARA paper (Meta/UMich, MIT) shows 90.2% of costs come from rediscovering dead ends.
"""

import json
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


class ExplorationDAG:
    """Tracks solve session outcomes as an exploration tree.

    Each node represents an approach (query + strategy) with a verdict:
    - "success" → approach worked, can be reused
    - "dead_end" → approach failed, record lesson, prevent reuse
    - "pending" → approach in progress
    """

    def __init__(self, memory_service):
        self.mem = memory_service

    async def check_before_solve(
        self, device_id: str, query: str
    ) -> dict[str, Any]:
        """Check if similar approaches exist in the DAG before starting a new solve.

        Returns {"warnings": [...], "suggestions": [...]} to guide the agent.
        """
        warnings: list[str] = []
        suggestions: list[str] = []

        preventions = await self.mem.get_dead_end_preventions(device_id, query)
        if preventions:
            for de in preventions[:3]:
                warnings.append(
                    f"DEAD END: {de.get('failure_mode', 'unknown')} — {de.get('lesson', '')}"
                )

        dead_ends = await self.mem.recall_dead_ends(device_id, query, top_k=5)
        for de in dead_ends:
            failure = de.get("failure_mode", "")
            if failure and failure not in [w for w in warnings]:
                warnings.append(f"PAST FAILURE ({failure}): {de.get('lesson', 'Avoid this approach.')}")

        return {"warnings": warnings, "suggestions": suggestions}

    async def record_attempt(
        self,
        device_id: str,
        query: str,
        approach: str,
        outcome: str,
        failure_mode: str = "",
        lesson: str = "",
        parent_node_id: str = "",
    ) -> str:
        """Record a solve attempt in the DAG.

        Args:
            outcome: "success" or "dead_end"
            failure_mode: MAST taxonomy category if dead_end
            lesson: What was learned (for dead ends)
            parent_node_id: Link to parent approach in the DAG

        Returns the node ID.
        """
        if outcome == "dead_end":
            node_id = await self.mem.store_dead_end(
                device_id=device_id,
                title=query[:120],
                hypothesis=query,
                approach=approach,
                failure_mode=failure_mode or "unknown",
                failure_evidence=f"Query: {query}",
                lesson=lesson or "This approach did not work.",
                parent_node_id=parent_node_id,
                parent_node_type="approach",
                provenance="ai-executed",
            )
            logger.info("Exploration DAG: recorded dead_end %s for query: %s", node_id, query[:80])
            return node_id

        # Success — mark approach as reusable
        node_id = uuid.uuid4().hex[:12]
        logger.info("Exploration DAG: recorded success %s for query: %s", node_id, query[:80])
        return node_id

    async def get_node_history(
        self, device_id: str, query: str
    ) -> list[dict]:
        """Get all exploration history for a query pattern."""
        dead_ends = await self.mem.recall_dead_ends(device_id, query, top_k=20)
        history = []
        for de in dead_ends:
            history.append({
                "type": "dead_end",
                "title": de.get("title", ""),
                "failure_mode": de.get("failure_mode", ""),
                "lesson": de.get("lesson", ""),
                "provenance": de.get("provenance", "ai-suggested"),
                "created_at": de.get("created_at", 0),
            })
        return sorted(history, key=lambda x: x["created_at"], reverse=True)
