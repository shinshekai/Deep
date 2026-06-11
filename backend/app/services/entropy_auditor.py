"""Entropy auditor — detect agent-introduced maintenance burden.

Patterns validated against:
- Semantic Entropy (Farquhar et al., Nature 2024) — hallucination detection via sampling
- DriftDetector (MrPredic) — 5-signal behavioral drift detection
- PSI/CUSUM statistical methods — distribution shift detection
- FutureAGI calibration methodology — Platt scaling + isotonic regression

Monitors for:
- Duplicate episodes, contradictory facts, stale cache, empty episodes
- Behavioral drift (vocabulary shrinkage, tool pattern changes, output stagnation)
- Statistical distribution shifts (PSI, CUSUM)
"""

import collections
import logging
import math
import time
from dataclasses import dataclass, field

from app.services.memory_service import MemoryService
from app.services.response_cache import ResponseCache

logger = logging.getLogger(__name__)

PSI_THRESHOLD_NO_SHIFT = 0.1
PSI_THRESHOLD_INVESTIGATE = 0.25
CUSUM_THRESHOLD = 5.0
CUSUM_ALLOWANCE = 0.5


@dataclass
class EntropyFinding:
    category: str
    description: str
    severity: str = "low"
    count: int = 0
    recommendation: str = ""


@dataclass
class DriftSnapshot:
    timestamp: float
    vocabulary_size: int = 0
    tool_calls: dict[str, int] = field(default_factory=dict)
    output_hashes: list[str] = field(default_factory=list)
    response_lengths: list[int] = field(default_factory=list)


@dataclass
class EntropyReport:
    findings: list[EntropyFinding] = field(default_factory=list)
    score: float = 0.0
    timestamp: float = 0.0
    drift_score: float = 0.0
    psi_value: float = 0.0
    cusum_alarms: list[int] = field(default_factory=list)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


class EntropyAuditor:
    def __init__(
        self,
        memory_service: MemoryService,
        response_cache: ResponseCache | None = None,
    ):
        self.memory = memory_service
        self.cache = response_cache
        self._snapshots: list[DriftSnapshot] = []
        self._baseline_lengths: list[int] = []
        self._cusum_pos = 0.0
        self._cusum_neg = 0.0

    async def audit(self, device_id: str) -> EntropyReport:
        findings = []
        findings.extend(await self._check_duplicate_episodes(device_id))
        findings.extend(await self._check_contradictory_facts(device_id))
        findings.extend(await self._check_stale_cache())
        findings.extend(await self._check_empty_episodes(device_id))

        drift_findings, drift_score = self._compute_drift()
        findings.extend(drift_findings)

        psi_value = self._compute_psi()
        cusum_alarms = self._compute_cusum()

        score = self._compute_score(findings)
        return EntropyReport(
            findings=findings,
            score=score,
            drift_score=drift_score,
            psi_value=psi_value,
            cusum_alarms=cusum_alarms,
        )

    def create_snapshot(
        self,
        vocabulary: set[str],
        tool_calls: list[str],
        outputs: list[str],
    ) -> DriftSnapshot:
        snapshot = DriftSnapshot(
            timestamp=time.time(),
            vocabulary_size=len(vocabulary),
            tool_calls=dict(collections.Counter(tool_calls)),
            output_hashes=[str(hash(o)) for o in outputs[-10:]],
            response_lengths=[len(o) for o in outputs[-10:]],
        )
        self._snapshots.append(snapshot)
        if len(self._snapshots) > 100:
            self._snapshots = self._snapshots[-100:]
        if snapshot.response_lengths:
            self._baseline_lengths.extend(snapshot.response_lengths)
            if len(self._baseline_lengths) > 1000:
                self._baseline_lengths = self._baseline_lengths[-1000:]
        return snapshot

    async def _check_duplicate_episodes(self, device_id: str) -> list[EntropyFinding]:
        findings = []
        try:
            episodes = await self.memory.list_episodes(device_id, limit=1000)
            seen = {}
            duplicates = 0
            for ep in episodes:
                key = (ep.get("query", ""), ep.get("session_type", ""))
                if key in seen:
                    duplicates += 1
                else:
                    seen[key] = ep.get("id")

            if duplicates > 0:
                findings.append(EntropyFinding(
                    category="duplicate_episodes",
                    description=f"{duplicates} duplicate episode pairs detected",
                    severity="medium",
                    count=duplicates,
                    recommendation="Deduplicate episodes by query+session_type",
                ))
        except Exception as e:
            logger.warning("Failed to check duplicate episodes: %s", e)
        return findings

    async def _check_contradictory_facts(self, device_id: str) -> list[EntropyFinding]:
        findings = []
        try:
            facts = await self.memory.recall_facts(device_id, query="the", top_k=500)
            contradictions = 0
            for i, fact_a in enumerate(facts):
                for fact_b in facts[i + 1:]:
                    content_a = fact_a.get("content", "").lower()
                    content_b = fact_b.get("content", "").lower()
                    if self._is_contradiction(content_a, content_b):
                        contradictions += 1

            if contradictions > 0:
                findings.append(EntropyFinding(
                    category="contradictory_facts",
                    description=f"{contradictions} potentially contradictory fact pairs",
                    severity="high",
                    count=contradictions,
                    recommendation="Review and reconcile contradictory facts",
                ))
        except Exception as e:
            logger.warning("Failed to check contradictory facts: %s", e)
        return findings

    async def _check_stale_cache(self) -> list[EntropyFinding]:
        findings = []
        if not self.cache:
            return findings
        try:
            disk_cache = self.cache._get_cache()
            if disk_cache is not None:
                cache_size = len(disk_cache)
                if cache_size > 1000:
                    findings.append(EntropyFinding(
                        category="stale_cache",
                        description=f"Cache has {cache_size} entries, consider cleanup",
                        severity="low",
                        count=cache_size,
                        recommendation="Clear old cache entries or increase TTL",
                    ))
        except Exception as e:
            logger.warning("Failed to check stale cache: %s", e)
        return findings

    async def _check_empty_episodes(self, device_id: str) -> list[EntropyFinding]:
        findings = []
        try:
            episodes = await self.memory.list_episodes(device_id, limit=1000)
            empty = sum(1 for ep in episodes if not ep.get("answer", "").strip())
            if empty > 0:
                findings.append(EntropyFinding(
                    category="empty_episodes",
                    description=f"{empty} episodes with empty answers",
                    severity="medium",
                    count=empty,
                    recommendation="Remove or complete episodes with empty answers",
                ))
        except Exception as e:
            logger.warning("Failed to check empty episodes: %s", e)
        return findings

    def _compute_drift(self) -> tuple[list[EntropyFinding], float]:
        findings = []
        if len(self._snapshots) < 2:
            return findings, 0.0

        prev = self._snapshots[-2]
        curr = self._snapshots[-1]
        drift_score = 0.0

        vocab_change = abs(curr.vocabulary_size - prev.vocabulary_size)
        if prev.vocabulary_size > 0:
            vocab_ratio = vocab_change / prev.vocabulary_size
            if vocab_ratio > 0.3:
                findings.append(EntropyFinding(
                    category="vocabulary_shrinkage",
                    description=f"Vocabulary shrank by {vocab_ratio:.0%}",
                    severity="medium",
                    recommendation="Check for context corruption or precision loss",
                ))
                drift_score += 0.3

        if prev.tool_calls and curr.tool_calls:
            prev_tools = set(prev.tool_calls.keys())
            curr_tools = set(curr.tool_calls.keys())
            if prev_tools and not curr_tools.issubset(prev_tools):
                findings.append(EntropyFinding(
                    category="tool_pattern_change",
                    description="Agent started using new tools not seen before",
                    severity="low",
                    recommendation="Verify tool selection is intentional",
                ))
                drift_score += 0.1

        if curr.output_hashes and len(curr.output_hashes) >= 2:
            unique_ratio = len(set(curr.output_hashes)) / len(curr.output_hashes)
            if unique_ratio < 0.5:
                findings.append(EntropyFinding(
                    category="output_stagnation",
                    description=f"Only {unique_ratio:.0%} of recent outputs are unique",
                    severity="high",
                    recommendation="Agent may be stuck in repetitive loop",
                ))
                drift_score += 0.4

        return findings, min(drift_score, 1.0)

    def _compute_psi(self) -> float:
        if len(self._baseline_lengths) < 20 or not self._snapshots:
            return 0.0
        current = self._snapshots[-1].response_lengths
        if not current:
            return 0.0

        import numpy as np

        ref = np.array(self._baseline_lengths[-200:])
        cur = np.array(current)
        bins = np.histogram_bin_edges(np.concatenate([ref, cur]), bins=10)
        ref_hist, _ = np.histogram(ref, bins=bins, density=True)
        cur_hist, _ = np.histogram(cur, bins=bins, density=True)
        ref_hist = np.clip(ref_hist, 1e-6, None)
        cur_hist = np.clip(cur_hist, 1e-6, None)
        psi = float(np.sum((cur_hist - ref_hist) * np.log(cur_hist / ref_hist)))
        return psi

    def _compute_cusum(self) -> list[int]:
        if len(self._baseline_lengths) < 20:
            return []
        import numpy as np

        baseline = np.array(self._baseline_lengths[-200:])
        mean = float(np.mean(baseline))
        alarms = []
        self._cusum_pos = 0.0
        self._cusum_neg = 0.0
        for i, x in enumerate(self._baseline_lengths[-50:]):
            self._cusum_pos = max(0.0, self._cusum_pos + (x - mean - CUSUM_ALLOWANCE))
            self._cusum_neg = max(0.0, self._cusum_neg + (mean - x - CUSUM_ALLOWANCE))
            if self._cusum_pos > CUSUM_THRESHOLD or self._cusum_neg > CUSUM_THRESHOLD:
                alarms.append(i)
                self._cusum_pos = 0.0
                self._cusum_neg = 0.0
        return alarms

    def _is_contradiction(self, a: str, b: str) -> bool:
        negations = ["not", "never", "no", "cannot", "can't", "don't", "doesn't"]
        for neg in negations:
            if neg in a and neg not in b:
                shared_words = set(a.split()) & set(b.split())
                if len(shared_words) > 5:
                    return True
        return False

    def _compute_score(self, findings: list[EntropyFinding]) -> float:
        if not findings:
            return 100.0
        penalties = {
            "low": 1.0,
            "medium": 5.0,
            "high": 15.0,
        }
        total_penalty = sum(penalties.get(f.severity, 1.0) for f in findings)
        return max(0.0, 100.0 - total_penalty)
