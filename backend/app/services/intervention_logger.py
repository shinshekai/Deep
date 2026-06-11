"""Intervention logger — track human assists as diagnostic signals.

Patterns validated against:
- Grizzly Peak HITL patterns (Feb 2026) — approval gating, confidence routing
- Serval workflow design (May 2026) — 4 escalation points, progressive autonomy
- Agent guardrails template (TheArchitectit) — audit log fields, escalation format
- Temporal durable HITL — crash-safe human interaction via signals

Tracks:
- Human interventions (corrections, hints, overrides, approvals, clarifications)
- Avoidability stats and harness gap analysis
- Approval gating with confidence-based routing
- Progressive autonomy based on track record
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum

from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)

AUTO_APPROVE_THRESHOLD = 0.95
AUTO_REJECT_THRESHOLD = 0.2
AUTONOMY_FLOOR = 0.7
AUTONOMY_CEILING = 0.98
MIN_SAMPLE_SIZE = 50


class InterventionType(Enum):
    CORRECTION = "correction"
    HINT = "hint"
    OVERRIDE = "override"
    APPROVAL = "approval"
    CLARIFICATION = "clarification"


class Avoidability(Enum):
    AVOIDABLE = "avoidable"
    UNAVOIDABLE = "unavoidable"
    UNCLEAR = "unclear"


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"


class EscalationTier(Enum):
    AUTO = "auto"
    TIER1 = "tier1"
    TIER2 = "tier2"
    TIER3 = "tier3"


@dataclass
class Intervention:
    intervention_id: str
    episode_id: str
    intervention_type: InterventionType
    description: str
    avoidability: Avoidability
    harness_gap: str
    device_id: str
    timestamp: float = 0.0


@dataclass
class ApprovalRequest:
    request_id: str
    action_type: str
    parameters: dict = field(default_factory=dict)
    reasoning: dict = field(default_factory=dict)
    confidence: float = 0.5
    timestamp: float = 0.0
    status: ApprovalStatus = ApprovalStatus.PENDING
    reviewed_by: str = ""
    reviewed_at: float = 0.0
    feedback: str = ""


@dataclass
class AuditLogEntry:
    timestamp: float
    session_id: str
    agent_id: str
    action_type: str
    action_parameters: dict = field(default_factory=dict)
    decision: str = "auto_approved"
    reason: str = ""
    confidence: float = 0.0
    reviewed_by: str = ""
    metadata: dict = field(default_factory=dict)


class InterventionLogger:
    def __init__(self, memory_service: MemoryService):
        self.memory = memory_service
        self._interventions: list[Intervention] = []
        self._approval_requests: dict[str, ApprovalRequest] = {}
        self._audit_log: list[AuditLogEntry] = []
        self._approval_stats: dict[str, dict[str, int]] = {}
        self._auto_approve_threshold = AUTO_APPROVE_THRESHOLD
        self._escalation_chains: dict[str, list[dict]] = {
            "default": [
                {"name": "auto", "reviewers": [], "max_risk": 2},
                {"name": "tier1", "reviewers": ["user"], "max_risk": 5},
                {"name": "tier2", "reviewers": ["user"], "max_risk": 8},
                {"name": "tier3", "reviewers": ["user"], "max_risk": 10},
            ]
        }

    async def log_intervention(
        self,
        episode_id: str,
        intervention_type: InterventionType,
        description: str,
        avoidability: Avoidability,
        harness_gap: str,
        device_id: str = "",
    ) -> Intervention:
        intervention = Intervention(
            intervention_id=f"int_{int(time.time() * 1000)}",
            episode_id=episode_id,
            intervention_type=intervention_type,
            description=description,
            avoidability=avoidability,
            harness_gap=harness_gap,
            device_id=device_id,
            timestamp=time.time(),
        )
        self._interventions.append(intervention)

        logger.info(
            "Intervention logged: type=%s episode=%s avoidability=%s",
            intervention_type.value,
            episode_id,
            avoidability.value,
        )

        return intervention

    async def get_interventions(
        self,
        episode_id: str | None = None,
        intervention_type: InterventionType | None = None,
        limit: int = 100,
    ) -> list[Intervention]:
        results = self._interventions
        if episode_id:
            results = [i for i in results if i.episode_id == episode_id]
        if intervention_type:
            results = [i for i in results if i.intervention_type == intervention_type]
        return results[-limit:]

    async def get_avoidability_stats(self) -> dict[str, int]:
        stats = {"avoidable": 0, "unavoidable": 0, "unclear": 0}
        for i in self._interventions:
            stats[i.avoidability.value] += 1
        return stats

    async def get_harness_gaps(self) -> list[str]:
        gaps = []
        for i in self._interventions:
            if i.avoidability == Avoidability.AVOIDABLE and i.harness_gap:
                gaps.append(i.harness_gap)
        return list(set(gaps))

    async def request_approval(
        self,
        action_type: str,
        parameters: dict,
        reasoning: dict,
        confidence: float,
        session_id: str = "",
        agent_id: str = "",
    ) -> ApprovalRequest:
        request_id = f"apr_{int(time.time() * 1000)}"
        request = ApprovalRequest(
            request_id=request_id,
            action_type=action_type,
            parameters=parameters,
            reasoning=reasoning,
            confidence=confidence,
            timestamp=time.time(),
        )
        self._approval_requests[request_id] = request

        decision = self._route_by_confidence(confidence, action_type)
        if decision != "human_review":
            request.status = (
                ApprovalStatus.APPROVED if decision == "auto_approved"
                else ApprovalStatus.REJECTED
            )
            self._log_audit_entry(
                session_id=session_id,
                agent_id=agent_id,
                action_type=action_type,
                action_parameters=parameters,
                decision=decision,
                reason=f"Confidence {confidence:.2f} -> {decision}",
                confidence=confidence,
            )
        else:
            risk_score = self._compute_risk_score(action_type)
            tier = self._get_escalation_tier(risk_score)
            request.reviewed_by = tier

        return request

    def _route_by_confidence(self, confidence: float, action_type: str) -> str:
        if confidence >= self._auto_approve_threshold:
            return "auto_approved"
        if confidence <= AUTO_REJECT_THRESHOLD:
            return "auto_rejected"
        return "human_review"

    def _compute_risk_score(self, action_type: str) -> int:
        risk_map = {
            "read_data": 1,
            "send_notification": 3,
            "update_record": 5,
            "delete_record": 8,
            "financial_transaction": 9,
            "modify_production": 10,
        }
        return risk_map.get(action_type, 5)

    def _get_escalation_tier(self, risk_score: int) -> str:
        chain = self._escalation_chains["default"]
        for tier in chain:
            if risk_score <= tier["max_risk"]:
                return tier["name"]
        return chain[-1]["name"]

    def _log_audit_entry(
        self,
        session_id: str,
        agent_id: str,
        action_type: str,
        action_parameters: dict,
        decision: str,
        reason: str,
        confidence: float,
        reviewed_by: str = "",
        metadata: dict | None = None,
    ):
        entry = AuditLogEntry(
            timestamp=time.time(),
            session_id=session_id,
            agent_id=agent_id,
            action_type=action_type,
            action_parameters=action_parameters,
            decision=decision,
            reason=reason,
            confidence=confidence,
            reviewed_by=reviewed_by,
            metadata=metadata or {},
        )
        self._audit_log.append(entry)
        if len(self._audit_log) > 10000:
            self._audit_log = self._audit_log[-10000:]

    async def get_audit_log(
        self,
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditLogEntry]:
        results = self._audit_log
        if session_id:
            results = [e for e in results if e.session_id == session_id]
        return results[-limit:]

    async def record_approval_decision(
        self,
        request_id: str,
        approved: bool,
        reviewer: str = "",
        feedback: str = "",
    ) -> ApprovalRequest | None:
        request = self._approval_requests.get(request_id)
        if not request:
            return None

        request.status = (
            ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        )
        request.reviewed_by = reviewer
        request.reviewed_at = time.time()
        request.feedback = feedback

        action_type = request.action_type
        if action_type not in self._approval_stats:
            self._approval_stats[action_type] = {"approved": 0, "rejected": 0}
        if approved:
            self._approval_stats[action_type]["approved"] += 1
        else:
            self._approval_stats[action_type]["rejected"] += 1

        return request

    async def evaluate_and_adjust_autonomy(self, action_type: str) -> float | None:
        if action_type not in self._approval_stats:
            return None
        stats = self._approval_stats[action_type]
        total = stats["approved"] + stats["rejected"]
        if total < MIN_SAMPLE_SIZE:
            return None

        approval_rate = stats["approved"] / total
        if approval_rate >= 0.97:
            new_threshold = max(self._auto_approve_threshold - 0.02, AUTONOMY_FLOOR)
            self._auto_approve_threshold = new_threshold
            return new_threshold
        if approval_rate < 0.85:
            new_threshold = min(self._auto_approve_threshold + 0.02, AUTONOMY_CEILING)
            self._auto_approve_threshold = new_threshold
            return new_threshold
        return None

    def format_escalation_message(
        self,
        context: str,
        urgency: str,
        concern: str,
        questions: list[str],
        options: list[dict],
        status: str,
        recommendation: str,
    ) -> str:
        lines = [
            "I need human review before proceeding.",
            "",
            f"CONTEXT: {context}",
            f"URGENCY: {urgency}",
            f"CONCERN: {concern}",
            "",
            "SPECIFIC QUESTIONS:",
        ]
        for i, q in enumerate(questions, 1):
            lines.append(f"{i}. {q}")
        lines.append("")
        lines.append("OPTIONS CONSIDERED:")
        for i, opt in enumerate(options, 1):
            pros = opt.get("pros", "")
            cons = opt.get("cons", "")
            lines.append(
                f"Option {i}: {opt.get('description', '')} "
                f"- Pros: {pros} / Cons: {cons}"
            )
        lines.extend([
            "",
            f"CURRENT STATUS: {status}",
            f"RECOMMENDED ACTION: {recommendation}",
            "",
            "Waiting for user guidance...",
        ])
        return "\n".join(lines)
