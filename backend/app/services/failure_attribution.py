"""Failure attribution — classify agent failures for targeted fixes.

Patterns validated against:
- MAST taxonomy (NeurIPS 2025 Spotlight) — 3 categories, 14 failure modes, 1600+ traces
- AgentDebug (ICLR 2026) — 5 modules, 17 error types, two-stage detection
- Who&When benchmark (ICML 2025 Spotlight) — binary search + counterfactual replay
- AgenTracer (ICLR 2026) — counterfactual replay + fault injection + RL
- Five-class coding taxonomy (2026) — context corruption = 40% of failures
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum

from app.services.lm_studio_client import LMStudioClient

logger = logging.getLogger(__name__)


class FailureType(Enum):
    TOOL_MISUSE = "tool_misuse"
    CONTEXT_LOSS = "context_loss"
    GOAL_DRIFT = "goal_drift"
    RETRY_LOOP = "retry_loop"
    CASCADING_ERROR = "cascading_error"
    SILENT_QUALITY = "silent_quality"
    HALLUCINATION = "hallucination"
    INCOMPLETE = "incomplete"
    WRONG_APPROACH = "wrong_approach"
    NONE = "none"


class ErrorModule(Enum):
    MEMORY = "memory"
    REFLECTION = "reflection"
    PLANNING = "planning"
    ACTION = "action"
    SYSTEM = "system"


ERROR_TAXONOMY = {
    ErrorModule.MEMORY: [
        "retrieval_failure", "stale_memory", "memory_overflow", "incorrect_update"
    ],
    ErrorModule.REFLECTION: [
        "incorrect_self_assessment", "missing_reflection", "over_confident"
    ],
    ErrorModule.PLANNING: [
        "goal_drift", "infeasible_plan", "missing_subgoal", "incorrect_decomposition"
    ],
    ErrorModule.ACTION: [
        "wrong_tool", "incorrect_args", "action_execution_mismatch"
    ],
    ErrorModule.SYSTEM: [
        "api_failure", "context_overflow", "timeout", "resource_exhaustion"
    ],
}


@dataclass
class StepError:
    step_index: int
    module: ErrorModule
    error_type: str
    confidence: float
    description: str


@dataclass
class FailureAttribution:
    failure_type: FailureType
    observation: str
    expected: str
    evidence: str
    next_step: str
    confidence: float = 0.5
    root_cause_step: int | None = None
    error_chain: list[StepError] = field(default_factory=list)


class FailureAttributionService:
    RULES = {
        FailureType.TOOL_MISUSE: [
            "tool called with wrong arguments",
            "tool called but result not used",
            "wrong tool selected for task",
            "tool_not_found",
            "schema validation failed",
            "missing required argument",
        ],
        FailureType.CONTEXT_LOSS: [
            "relevant information dropped",
            "conversation history truncated",
            "key details forgotten",
            "context window exceeded",
            "compaction event",
        ],
        FailureType.GOAL_DRIFT: [
            "agent stopped before completing task",
            "agent pursued tangent",
            "original objective abandoned",
            "yak-shaving drift",
        ],
        FailureType.RETRY_LOOP: [
            "same action repeated",
            "no progress after multiple attempts",
            "stuck in cycle",
            "identical tool calls",
            "regression oscillation",
        ],
        FailureType.CASCADING_ERROR: [
            "error in step N caused failure in step N+1",
            "upstream mistake propagated",
            "dependency failure",
        ],
        FailureType.SILENT_QUALITY: [
            "output looks correct but is wrong",
            "subtle error in response",
            "plausible but inaccurate",
            "phantom verification",
        ],
        FailureType.HALLUCINATION: [
            "made up information",
            "cited non-existent source",
            "fabricated data",
            "hallucinated tool call",
        ],
        FailureType.INCOMPLETE: [
            "partial answer given",
            "missing key components",
            "stopped too early",
        ],
        FailureType.WRONG_APPROACH: [
            "used incorrect method",
            "misunderstood the problem",
            "applied wrong solution pattern",
            "infeasible plan",
        ],
    }

    def __init__(self, llm_client: LMStudioClient):
        self.llm = llm_client

    async def attribute(
        self,
        query: str,
        trajectory: str,
        outcome: str,
        steps: list[dict] | None = None,
    ) -> FailureAttribution:
        rule_result = self._rule_based_classify(trajectory, outcome)
        if rule_result and rule_result.confidence > 0.7:
            return rule_result

        if steps and len(steps) >= 3:
            binary_result = await self._binary_search_attribution(steps)
            if binary_result and binary_result.confidence > 0.6:
                return binary_result

        llm_result = await self._llm_classify(query, trajectory, outcome)
        return llm_result

    async def _binary_search_attribution(
        self, steps: list[dict]
    ) -> FailureAttribution | None:
        low, high = 0, len(steps) - 1
        while low < high:
            mid = (low + high) // 2
            sub_trajectory = "\n".join(
                f"Step {i}: {s.get('action', '')} -> {s.get('result', '')[:100]}"
                for i, s in enumerate(steps[: mid + 1])
            )
            is_failing = await self._evaluate_subtrajectory(sub_trajectory)
            if is_failing:
                high = mid
            else:
                low = mid + 1

        if low < len(steps):
            failed_step = steps[low]
            return FailureAttribution(
                failure_type=self._classify_step_type(failed_step),
                observation=f"Step {low} failed: {failed_step.get('result', '')[:200]}",
                expected=f"Step {low} should succeed",
                evidence=f"Binary search localizes failure to step {low}/{len(steps)}",
                next_step=f"Investigate step {low}: {failed_step.get('action', '')}",
                confidence=0.75,
                root_cause_step=low,
            )
        return None

    async def _evaluate_subtrajectory(self, sub_trajectory: str) -> bool:
        prompt = f"""Does this sub-trajectory contain a failure that would cause the final outcome to fail?
Answer ONLY "yes" or "no".

Sub-trajectory:
{sub_trajectory[:800]}

Answer:"""
        response = await self.llm.stream_chat(
            messages=[{"role": "user", "content": prompt}]
        )
        return response.strip().lower().startswith("yes")

    def _classify_step_type(self, step: dict) -> FailureType:
        result = step.get("result", "").lower()
        action = step.get("action", "").lower()
        if "error" in result or "failed" in result:
            if "tool" in action or "call" in action:
                return FailureType.TOOL_MISUSE
            return FailureType.WRONG_APPROACH
        if "timeout" in result:
            return FailureType.CASCADING_ERROR
        return FailureType.INCOMPLETE

    def _rule_based_classify(
        self, trajectory: str, outcome: str
    ) -> FailureAttribution | None:
        trajectory_lower = trajectory.lower()
        outcome_lower = outcome.lower()

        for failure_type, patterns in self.RULES.items():
            matches = sum(1 for p in patterns if p in trajectory_lower)
            if matches >= 2:
                return FailureAttribution(
                    failure_type=failure_type,
                    observation=outcome[:200],
                    expected="Successful task completion",
                    evidence=f"Rule-based: {matches} pattern matches for {failure_type.value}",
                    next_step=f"Investigate {failure_type.value} in trajectory",
                    confidence=min(0.5 + matches * 0.1, 0.9),
                )

        if "error" in outcome_lower or "failed" in outcome_lower:
            return FailureAttribution(
                failure_type=FailureType.WRONG_APPROACH,
                observation=outcome[:200],
                expected="Successful task completion",
                evidence="Error/failure detected in outcome",
                next_step="Review approach and try alternative",
                confidence=0.4,
            )

        return None

    async def _llm_classify(
        self, query: str, trajectory: str, outcome: str
    ) -> FailureAttribution:
        prompt = f"""Classify this agent failure. Output JSON with:
- failure_type: one of [tool_misuse, context_loss, goal_drift, retry_loop, cascading_error, silent_quality, hallucination, incomplete, wrong_approach, none]
- observation: what happened (1 sentence)
- expected: what should have happened (1 sentence)
- evidence: supporting evidence (1 sentence)
- next_step: targeted fix direction (1 sentence)
- confidence: 0.0-1.0

Query: {query[:300]}
Trajectory: {trajectory[:500]}
Outcome: {outcome[:300]}

Output JSON:"""

        response = await self.llm.stream_chat(
            messages=[{"role": "user", "content": prompt}]
        )
        try:
            result = json.loads(response)
            return FailureAttribution(
                failure_type=FailureType(result.get("failure_type", "none")),
                observation=result.get("observation", ""),
                expected=result.get("expected", ""),
                evidence=result.get("evidence", ""),
                next_step=result.get("next_step", ""),
                confidence=float(result.get("confidence", 0.5)),
            )
        except Exception:
            return FailureAttribution(
                failure_type=FailureType.NONE,
                observation=outcome[:200],
                expected="Successful task completion",
                evidence="LLM classification failed",
                next_step="Manual review needed",
                confidence=0.1,
            )

    async def detect_module_errors(
        self, steps: list[dict]
    ) -> list[StepError]:
        errors = []
        for i, step in enumerate(steps):
            for module, error_types in ERROR_TAXONOMY.items():
                for error_type in error_types:
                    if self._check_error_pattern(step, error_type):
                        errors.append(StepError(
                            step_index=i,
                            module=module,
                            error_type=error_type,
                            confidence=0.7,
                            description=f"Step {i}: {error_type} in {module.value}",
                        ))
        return errors

    def _check_error_pattern(self, step: dict, error_type: str) -> bool:
        result = step.get("result", "").lower()
        action = step.get("action", "").lower()
        patterns = {
            "retrieval_failure": ["not found", "no results", "empty response"],
            "stale_memory": ["outdated", "old data", "stale"],
            "context_overflow": ["context length", "token limit", "truncated"],
            "wrong_tool": ["tool not found", "unknown tool", "invalid tool"],
            "incorrect_args": ["invalid argument", "missing argument", "type error"],
            "timeout": ["timeout", "timed out", "deadline exceeded"],
            "goal_drift": ["tangent", "unrelated", "off topic"],
            "api_failure": ["500", "502", "503", "rate limit"],
        }
        keywords = patterns.get(error_type, [])
        return any(kw in result or kw in action for kw in keywords)

    def find_root_cause(self, errors: list[StepError]) -> StepError | None:
        if not errors:
            return None
        for i in range(len(errors) - 1, -1, -1):
            if self._is_root_cause(errors[i], errors[i + 1:]):
                return errors[i]
        return errors[0]

    def _is_root_cause(self, candidate: StepError, later: list[StepError]) -> bool:
        if candidate.module == ErrorModule.SYSTEM:
            return True
        if candidate.module == ErrorModule.PLANNING:
            return any(e.module in (ErrorModule.ACTION, ErrorModule.MEMORY) for e in later)
        if candidate.module == ErrorModule.MEMORY:
            return any(e.module == ErrorModule.ACTION for e in later)
        return False
