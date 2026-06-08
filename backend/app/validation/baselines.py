"""Production readiness baseline thresholds and validation constants.

All values sourced from:
- 01-product-requirements.md (NFR section)
- 03-inference-strategy.md (Section 1-5)
- Previous audit findings
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    CRITICAL = "critical"  # Build-breaking, blocks deployment
    HIGH = "high"  # Must fix before next release
    MEDIUM = "medium"  # Should fix within sprint
    LOW = "low"  # Track and address when convenient
    INFO = "info"  # Informational only


class CheckCategory(str, Enum):
    PERFORMANCE = "performance"
    VRAM = "vram"
    COVERAGE = "coverage"
    HEALTH = "health"
    CONFIG = "config"
    REMEDIATION = "remediation"


@dataclass(frozen=True)
class PerformanceBaselines:
    """From NFR-1.x in 01-product-requirements.md and Section 1 of 03-inference-strategy.md."""

    # NFR-1.3: Query-to-first-token latency (Smart Solver)
    ttft_max_ms: float = 3000.0
    # NFR-1.5: Token generation throughput with TurboQuant
    min_tokens_per_sec: float = 15.0
    # NFR-1.4: PageIndex tree search latency
    retrieval_max_ms: float = 5000.0
    # NFR-1.1: PageIndex tree generation time (100-page doc)
    tree_gen_max_sec: float = 60.0
    # NFR-1.2: Vector KB creation (300-page doc)
    vector_kb_max_sec: float = 120.0
    # NFR-1.6: WebSocket streaming latency
    ws_latency_max_ms: float = 100.0
    # Section 1 tier latency targets
    t1_latency_max_ms: float = 50.0
    t2_latency_max_ms: float = 500.0
    t3_latency_max_ms: float = 5000.0


@dataclass(frozen=True)
class VRAMBaselines:
    """From Section 2 of 03-inference-strategy.md."""

    # Pressure thresholds (percentage of total VRAM)
    green_max_pct: float = 70.0
    yellow_max_pct: float = 85.0
    orange_max_pct: float = 93.0
    # Target KV cache reduction with K:q8_0/V:q4_0
    kv_reduction_target_pct: float = 59.0
    # Safety margin for VRAM (from config.py default)
    safety_margin_pct: float = 15.0
    # NFR-2.1: KV cache memory reduction target
    kv_4bit_reduction_min: float = 4.0  # 4x minimum vs FP16
    # NFR-2.3: Backend process memory footprint
    backend_ram_max_mb: float = 2048.0


@dataclass(frozen=True)
class CoverageBaselines:
    """From NFR-5.x in 01-product-requirements.md."""

    # NFR-5.1: Minimum 80% line coverage on backend Python code
    global_min_pct: float = 80.0
    # Critical module minimum (higher bar for core services)
    critical_module_min_pct: float = 85.0


# Modules that must meet the higher coverage bar
CRITICAL_MODULES = [
    "app.services.model_manager",
    "app.services.vram_monitor",
    "app.services.pageindex_generator",
    "app.services.lm_studio_client",
    "app.services.vector_kb",
    "app.services.solve_orchestrator",
    "app.services.complexity_scorer",
    "app.services.embedding_service",
    "app.services.text_chunker",
]


@dataclass(frozen=True)
class ModelTierSpec:
    """Per-tier specifications from Section 1 of 03-inference-strategy.md."""

    tier: int
    name: str
    model_patterns: tuple[str, ...]
    vram_range_gb: tuple[float, float]
    kv_cache_k: str
    kv_cache_v: str
    max_concurrent: int
    ttl_seconds: Optional[int]  # None = always resident
    context_length: int


TIER_SPECS = {
    1: ModelTierSpec(
        tier=1,
        name="Lightweight",
        model_patterns=("qwen3-0.6b", "qwen3-1.7b"),
        vram_range_gb=(0.5, 1.2),
        kv_cache_k="q4_0",
        kv_cache_v="q4_0",
        max_concurrent=4,
        ttl_seconds=None,
        context_length=4096,
    ),
    2: ModelTierSpec(
        tier=2,
        name="Medium",
        model_patterns=("qwen3-4b", "qwen3-8b"),
        vram_range_gb=(2.5, 5.5),
        kv_cache_k="q8_0",
        kv_cache_v="q4_0",
        max_concurrent=2,
        ttl_seconds=600,
        context_length=8192,
    ),
    3: ModelTierSpec(
        tier=3,
        name="Heavy",
        model_patterns=("qwen3-14b", "qwen3-30b"),
        vram_range_gb=(8.5, 18.0),
        kv_cache_k="q8_0",
        kv_cache_v="q8_0",
        max_concurrent=1,
        ttl_seconds=300,
        context_length=16384,
    ),
}


@dataclass
class ValidationResult:
    """Single validation check result."""

    check_id: str
    category: CheckCategory
    severity: Severity
    passed: bool
    message: str
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    remediation: Optional[str] = None
    module: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "passed": self.passed,
            "message": self.message,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "remediation": self.remediation,
            "module": self.module,
        }


@dataclass
class ValidationReport:
    """Aggregate report from a full validation run."""

    timestamp: str
    results: list[ValidationResult] = field(default_factory=list)
    total_checks: int = 0
    passed: int = 0
    failed: int = 0
    critical_failures: int = 0

    def add(self, result: ValidationResult):
        self.results.append(result)
        self.total_checks += 1
        if result.passed:
            self.passed += 1
        else:
            self.failed += 1
            if result.severity == Severity.CRITICAL:
                self.critical_failures += 1

    @property
    def pass_rate(self) -> float:
        return (self.passed / self.total_checks * 100) if self.total_checks else 0.0

    @property
    def is_green(self) -> bool:
        return self.critical_failures == 0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "total_checks": self.total_checks,
            "passed": self.passed,
            "failed": self.failed,
            "critical_failures": self.critical_failures,
            "pass_rate": round(self.pass_rate, 1),
            "is_green": self.is_green,
            "results": [r.to_dict() for r in self.results],
        }

    def summary_markdown(self) -> str:
        status = "✅ PASS" if self.is_green else "❌ FAIL"
        lines = [
            f"# Validation Report — {status}",
            f"**Time:** {self.timestamp}",
            f"**Checks:** {self.passed}/{self.total_checks} passed " f"({self.pass_rate:.0f}%)",
            "",
        ]
        if self.critical_failures:
            lines.append(f"**🚨 {self.critical_failures} CRITICAL failure(s)**\n")

        for cat in CheckCategory:
            cat_results = [r for r in self.results if r.category == cat]
            if not cat_results:
                continue
            failures = [r for r in cat_results if not r.passed]
            icon = "❌" if failures else "✅"
            lines.append(
                f"## {icon} {cat.value.title()} "
                f"({len(cat_results) - len(failures)}/{len(cat_results)})"
            )
            for r in failures:
                lines.append(f"- **[{r.severity.value.upper()}]** {r.message}")
                if r.remediation:
                    lines.append(f"  → Fix: {r.remediation}")
            lines.append("")
        return "\n".join(lines)
