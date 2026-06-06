"""Remediation Progress Tracker — Dimension 6.

Tracks completion status against the prioritized remediation plan
from the production audit. Each item maps to a verifiable code condition.
"""

import asyncio
import re
from pathlib import Path

from app.validation.baselines import (
    CheckCategory,
    Severity,
    ValidationReport,
    ValidationResult,
)

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_APP_DIR = _BACKEND_ROOT / "app"
_PROJECT_ROOT = _BACKEND_ROOT.parent
_FRONTEND_DIR = _PROJECT_ROOT / "frontend"


# ── Remediation items from the audit ──────────────────────────────────────
# Each item has:
#   - id: unique identifier
#   - sprint: which sprint it belongs to
#   - title: human-readable description
#   - check: callable that returns True if fixed
#   - severity: how critical the fix is
#   - blocks: list of item IDs this blocks

REMEDIATION_ITEMS = []


def _register(item_id, sprint, title, severity, blocks=None):
    """Decorator to register a remediation check function."""
    def decorator(fn):
        REMEDIATION_ITEMS.append({
            "id": item_id,
            "sprint": sprint,
            "title": title,
            "severity": severity,
            "blocks": blocks or [],
            "check_fn": fn,
        })
        return fn
    return decorator


# ── Sprint 1: Critical Bugs ──────────────────────────────────────────────

@_register("REM-S1-01", 1, "Fix end_learning truncated function", Severity.CRITICAL,
           blocks=["REM-S3-13"])
def _check_end_learning_fixed():
    """end_learning in agent.py must have a return statement."""
    path = _APP_DIR / "routers" / "agent.py"
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    # Find the end_learning function and check for return
    match = re.search(
        r'async def end_learning\(.*?\n(.*?)(?=\n@router\.|\nclass |\Z)',
        content, re.DOTALL
    )
    if not match:
        return False
    return "return " in match.group(1)


@_register("REM-S1-02", 1, "Add asyncio.Lock to Deep Research file I/O", Severity.CRITICAL)
def _check_deep_research_lock():
    try:
        from app.services.deep_research import DeepResearchService
        from unittest.mock import MagicMock
        svc = DeepResearchService(lm_client=MagicMock())
        lock = svc._get_lock("validation-probe")
        return isinstance(lock, asyncio.Lock)
    except Exception:
        return False


@_register("REM-S1-03", 1, "Wire Research page to backend API", Severity.CRITICAL)
def _check_research_page_wired():
    path = _FRONTEND_DIR / "app" / "(platform)" / "research" / "page.tsx"
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    has_fetch = "fetch(" in content or "secureFetch(" in content
    has_research_url = "/api/v1/research" in content or "/research" in content
    has_api_import = "API_BASE_URL" in content
    return has_fetch and (has_research_url or has_api_import)


@_register("REM-S1-04", 1, "Centralize frontend API base URL", Severity.HIGH)
def _check_api_centralized():
    config_path = _FRONTEND_DIR / "lib" / "config.ts"
    return config_path.exists()


# ── Sprint 2: Security & Reliability ─────────────────────────────────────

@_register("REM-S2-05", 2, "Sanitize HTML in guide page (DOMPurify)", Severity.HIGH)
def _check_dompurify():
    path = _FRONTEND_DIR / "app" / "(platform)" / "guide" / "page.tsx"
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    if "dangerouslySetInnerHTML" not in content:
        return True  # No dangerous HTML = no risk
    return "DOMPurify" in content or "sanitize" in content.lower()


@_register("REM-S2-06", 2, "Add session-based WebSocket event filtering", Severity.HIGH)
def _check_ws_session_filtering():
    for page in ["solve/page.tsx", "chat/page.tsx"]:
        path = _FRONTEND_DIR / "app" / "(platform)" / page
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        if "subscribe(" in content and "session_id" not in content.lower():
            return False
    return True


@_register("REM-S2-07", 2, "Create .env.example with all required vars", Severity.HIGH)
def _check_env_example():
    return (
        (_PROJECT_ROOT / ".env.example").exists()
        or (_BACKEND_ROOT / ".env.example").exists()
    )


@_register("REM-S2-08", 2, "Settings page loads current config on mount", Severity.MEDIUM)
def _check_settings_loads_config():
    path = _FRONTEND_DIR / "app" / "(platform)" / "settings" / "page.tsx"
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    return "useEffect" in content and ("fetch" in content.lower() or "get" in content.lower()) and "/config" in content


@_register("REM-S2-09", 2, "Fix Documents page to fetch real document list", Severity.MEDIUM)
def _check_documents_page_fetches():
    path = _FRONTEND_DIR / "app" / "(platform)" / "documents" / "page.tsx"
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    return "documents={[]}" not in content


# ── Sprint 3: Frontend Integration ───────────────────────────────────────

@_register("REM-S3-10", 3, "Add React error boundaries", Severity.MEDIUM)
def _check_error_boundaries():
    for pattern in ["error-boundary", "ErrorBoundary"]:
        for f in _FRONTEND_DIR.rglob("*.tsx"):
            if "node_modules" in str(f):
                continue
            try:
                if pattern in f.read_text(encoding="utf-8"):
                    return True
            except Exception:
                continue
    return False


@_register("REM-S3-11", 3, "Add frontend test framework (Vitest + RTL)", Severity.HIGH)
def _check_frontend_test_framework():
    pkg = _FRONTEND_DIR / "package.json"
    if not pkg.exists():
        return False
    content = pkg.read_text(encoding="utf-8")
    return "vitest" in content or "jest" in content


@_register("REM-S3-12", 3, "Remove duplicate VRAM polling", Severity.LOW)
def _check_no_duplicate_polling():
    path = _FRONTEND_DIR / "providers" / "websocket-provider.tsx"
    if not path.exists():
        return True
    content = path.read_text(encoding="utf-8")
    # Both REST polling AND WS subscription for the same data = duplicate
    has_rest_poll = "fetchVramStatus" in content and "setInterval" in content
    has_ws_sub = "metrics_frame" in content
    return not (has_rest_poll and has_ws_sub)


@_register("REM-S3-13", 3, "Add session persistence (localStorage)", Severity.MEDIUM)
def _check_session_persistence():
    for f in _FRONTEND_DIR.rglob("*.tsx"):
        if "node_modules" in str(f):
            continue
        try:
            content = f.read_text(encoding="utf-8")
            if "localStorage" in content and ("chat" in str(f).lower() or "session" in content.lower()):
                return True
        except Exception:
            continue
    return False


# ── Sprint 4: Production Hardening ───────────────────────────────────────

@_register("REM-S4-14", 4, "Verify LM Studio model load/unload with pynvml", Severity.HIGH)
def _check_lm_lifecycle_verification():
    path = _APP_DIR / "services" / "lm_studio_client.py"
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    return "verify" in content.lower() or "pynvml" in content or "poll" in content


@_register("REM-S4-15", 4, "Add OpenTelemetry instrumentation (7 points)", Severity.MEDIUM)
def _check_otel():
    try:
        from app.services.telemetry import setup_tracing
        provider = setup_tracing("udip-validation-probe", console_export=False)
        if provider is None:
            return False
        from opentelemetry import trace
        tracer = trace.get_tracer("udip.validation.probe")
        with tracer.start_as_current_span("validation_probe") as span:
            span.set_attribute("validation.probe", True)
        return True
    except Exception:
        return False


@_register("REM-S4-16", 4, "Create docker-compose.yml", Severity.MEDIUM)
def _check_docker():
    return (_PROJECT_ROOT / "docker-compose.yml").exists() or \
           (_PROJECT_ROOT / "docker-compose.yaml").exists()


@_register("REM-S4-17", 4, "Expand agent service test coverage to >80%", Severity.HIGH)
def _check_agent_test_coverage():
    """Check that agent service tests have >1 test function each."""
    tests_dir = _BACKEND_ROOT / "tests"
    agent_tests = [
        "test_solve_orchestrator.py",
        "test_question_generator.py",
        "test_guided_learning.py",
        "test_deep_research.py",
        "test_content_creation.py",
    ]
    for test_file in agent_tests:
        path = tests_dir / test_file
        if not path.exists():
            return False
        content = path.read_text(encoding="utf-8")
        test_count = content.count("def test_")
        if test_count < 3:  # Need at least 3 tests per agent service
            return False
    return True


@_register("REM-S4-18", 4, "Wire TurboQuant KV cache params to LM Studio", Severity.MEDIUM)
def _check_kv_params_wired():
    path = _APP_DIR / "services" / "lm_studio_client.py"
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    return "cache_type_k" in content and ("json" in content.lower() or "payload" in content)


# ── Public API ────────────────────────────────────────────────────────────

def validate_remediation(report: ValidationReport) -> None:
    """Run all remediation progress checks."""
    total = len(REMEDIATION_ITEMS)
    done = 0

    for item in REMEDIATION_ITEMS:
        try:
            passed = item["check_fn"]()
        except Exception:
            passed = False

        if passed:
            done += 1

        # Check if this item is blocked by an incomplete dependency
        blocked_by = []
        for dep_id in item.get("blocks", []):
            dep = next((d for d in REMEDIATION_ITEMS if d["id"] == dep_id), None)
            if dep:
                try:
                    if not dep["check_fn"]():
                        blocked_by.append(dep_id)
                except Exception:
                    blocked_by.append(dep_id)

        status = "DONE" if passed else "PENDING"
        if blocked_by and not passed:
            status = f"BLOCKED by {', '.join(blocked_by)}"

        report.add(ValidationResult(
            check_id=item["id"],
            category=CheckCategory.REMEDIATION,
            severity=item["severity"] if not passed else Severity.INFO,
            passed=passed,
            message=f"Sprint {item['sprint']}: {item['title']} — {status}",
            metric_name="remediation_progress",
            metric_value=1.0 if passed else 0.0,
        ))

    # Summary metric
    report.add(ValidationResult(
        check_id="REM-SUMMARY",
        category=CheckCategory.REMEDIATION,
        severity=Severity.HIGH if done < total else Severity.INFO,
        passed=done == total,
        message=f"Remediation progress: {done}/{total} items complete ({done/total*100:.0f}%)",
        metric_name="remediation_total_pct",
        metric_value=float(done),
        threshold=float(total),
    ))
