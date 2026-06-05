"""Lightweight alerting for UDIP — Day 16.

Checks VRAM usage, LLM availability, and error rate on a configurable
interval. Alerts are logged at WARNING/CRITICAL level and exposed via
a Prometheus gauge (``udip_alert_active``) so operators can wire them
to external systems (PagerDuty, Slack, etc.).

Thresholds are configurable via environment variables:

    UDIP_VRAM_WARN_PCT   — VRAM warning threshold (default: 85)
    UDIP_VRAM_CRIT_PCT   — VRAM critical threshold (default: 95)
    UDIP_ERROR_RATE_WARN — error-rate warning threshold (default: 0.1)
    UDIP_ALERT_INTERVAL  — seconds between checks (default: 60)
"""

import os
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

from prometheus_client import Gauge, Info

logger = logging.getLogger("app.alerting")

# ── Prometheus gauges ────────────────────────────────────────────────

ALERT_ACTIVE = Gauge(
    "udip_alert_active",
    "1 if an alert is currently firing, 0 otherwise",
    ["severity", "type"],
)

ALERT_INFO = Info(
    "udip_alert",
    "Details of the most recent alert",
    ["type"],
)

# ── Thresholds ───────────────────────────────────────────────────────

VRAM_WARN_PCT = float(os.environ.get("UDIP_VRAM_WARN_PCT", "85"))
VRAM_CRIT_PCT = float(os.environ.get("UDIP_VRAM_CRIT_PCT", "95"))
ERROR_RATE_WARN = float(os.environ.get("UDIP_ERROR_RATE_WARN", "0.1"))
ALERT_INTERVAL = float(os.environ.get("UDIP_ALERT_INTERVAL", "60"))


@dataclass
class AlertState:
    """Tracks which alerts are currently firing."""
    vram_warning: bool = False
    vram_critical: bool = False
    llm_down: bool = False
    high_error_rate: bool = False
    last_check: float = 0.0
    _error_counts: dict = field(default_factory=lambda: {"total": 0, "errors": 0})

    def record_request(self, status_code: int) -> None:
        """Record a request for error-rate tracking."""
        self._error_counts["total"] += 1
        if status_code >= 500:
            self._error_counts["errors"] += 1

    @property
    def error_rate(self) -> float:
        total = self._error_counts["total"]
        if total == 0:
            return 0.0
        return self._error_counts["errors"] / total


_alert_state = AlertState()


def get_alert_state() -> AlertState:
    """Return the global alert state (for testing)."""
    return _alert_state


async def check_alerts() -> None:
    """Run all alert checks. Called periodically from the TTL loop.

    Each check is isolated — a failure in one doesn't prevent others
    from running.
    """
    global _alert_state
    now = time.time()
    if now - _alert_state.last_check < ALERT_INTERVAL:
        return
    _alert_state.last_check = now

    await _check_vram()
    await _check_llm()
    _check_error_rate()


async def _check_vram() -> None:
    """Check VRAM usage and fire/clear alerts."""
    try:
        from app import state
        vram_data = await state.vram_monitor.get_vram_usage()
        used_pct = vram_data.get("vram_used_pct", 0) * 100  # normalize to 0-100

        was_warn = _alert_state.vram_warning
        was_crit = _alert_state.vram_critical

        _alert_state.vram_critical = used_pct >= VRAM_CRIT_PCT
        _alert_state.vram_warning = used_pct >= VRAM_WARN_PCT and not _alert_state.vram_critical

        # Fire
        if _alert_state.vram_critical and not was_crit:
            logger.critical(
                f"ALERT VRAM_CRITICAL: {used_pct:.1f}% used "
                f"(threshold: {VRAM_CRIT_PCT}%)"
            )
            ALERT_ACTIVE.labels(severity="critical", type="vram").set(1)
            ALERT_INFO.labels(type="vram").info({"usage": f"{used_pct:.1f}%", "severity": "critical"})
        elif _alert_state.vram_warning and not was_warn:
            logger.warning(
                f"ALERT VRAM_WARNING: {used_pct:.1f}% used "
                f"(threshold: {VRAM_WARN_PCT}%)"
            )
            ALERT_ACTIVE.labels(severity="warning", type="vram").set(1)
            ALERT_INFO.labels(type="vram").info({"usage": f"{used_pct:.1f}%", "severity": "warning"})

        # Clear
        if not _alert_state.vram_warning and not _alert_state.vram_critical:
            if was_warn or was_crit:
                logger.info(f"ALERT CLEAR VRAM: {used_pct:.1f}% used — back below threshold")
            ALERT_ACTIVE.labels(severity="warning", type="vram").set(0)
            ALERT_ACTIVE.labels(severity="critical", type="vram").set(0)
    except Exception as e:
        logger.debug(f"VRAM alert check failed (non-fatal): {e}")


async def _check_llm() -> None:
    """Check if LM Studio is reachable and fire/clear alerts."""
    try:
        from app import state
        lm_ok = await state.lm_client.check_health()

        was_down = _alert_state.llm_down
        _alert_state.llm_down = not lm_ok

        if _alert_state.llm_down and not was_down:
            logger.warning("ALERT LLM_DOWN: LM Studio is not reachable")
            ALERT_ACTIVE.labels(severity="warning", type="llm_down").set(1)
            ALERT_INFO.labels(type="llm_down").info({"status": "unreachable"})
        elif not _alert_state.llm_down and was_down:
            logger.info("ALERT CLEAR LLM: LM Studio is reachable again")
            ALERT_ACTIVE.labels(severity="warning", type="llm_down").set(0)
    except Exception as e:
        logger.debug(f"LLM alert check failed (non-fatal): {e}")


def _check_error_rate() -> None:
    """Check error rate and fire/clear alerts."""
    rate = _alert_state.error_rate
    was_high = _alert_state.high_error_rate
    _alert_state.high_error_rate = rate >= ERROR_RATE_WARN and _alert_state._error_counts["total"] >= 10

    if _alert_state.high_error_rate and not was_high:
        logger.warning(
            f"ALERT HIGH_ERROR_RATE: {rate:.1%} of requests are errors "
            f"(threshold: {ERROR_RATE_WARN:.1%})"
        )
        ALERT_ACTIVE.labels(severity="warning", type="error_rate").set(1)
        ALERT_INFO.labels(type="error_rate").info({"rate": f"{rate:.1%}"})
    elif not _alert_state.high_error_rate and was_high:
        logger.info(f"ALERT CLEAR ERROR_RATE: {rate:.1%} — back below threshold")
        ALERT_ACTIVE.labels(severity="warning", type="error_rate").set(0)
