"""Strategy Learner — closes the agent strategy learning loop.

Before solve: reads agent_strategies table, passes best strategy as context.
After solve: uses store_episode to update success_rate based on outcome.

Transforms the write-only agent_strategies table into a self-improving system.
"""

import hashlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _pattern_key(agent_type: str, query: str) -> str:
    return hashlib.sha256(f"{agent_type}:{query[:200]}".encode()).hexdigest()[:16]


class StrategyLearner:
    """Read and update agent strategies based on solve outcomes."""

    def __init__(self, memory_service):
        self.mem = memory_service

    async def get_best_strategy(self, agent_type: str, query: str) -> dict[str, Any]:
        """Look up the best-known strategy for a query pattern."""
        pattern = _pattern_key(agent_type, query)
        strategies = await self.mem.get_agent_strategies(agent_type, pattern)
        if not strategies:
            return {"strategy": None, "success_rate": 0.0, "sample_count": 0}
        best = strategies[0]
        return {
            "strategy": best.get("best_strategy"),
            "success_rate": best.get("success_rate", 0.0),
            "sample_count": best.get("sample_count", 0),
        }

    async def record_outcome(
        self, device_id: str, query: str, answer: str, model_used: str, success: bool,
    ) -> None:
        """Store solve outcome as an episode, which updates agent_strategies."""
        await self.mem.store_episode(
            device_id=device_id,
            query=query,
            answer=answer,
            agents=["dispatch"],
            model_used=model_used,
            session_type="solve",
            outcome_rating=1.0 if success else 0.0,
        )
        logger.info("Strategy loop: recorded outcome success=%s", success)
