"""Component Health Checker — Dimension 4.

Validates critical system components at runtime:
- LM Studio lifecycle management (actual execution, not no-ops)
- KV cache quantization effectiveness
- TurboQuant integration status
- Phase 10 completion (PageIndex + Hybrid RAG)
- WebSocket endpoint health
- Route completeness
"""

import asyncio
import importlib
import inspect
import logging
import os
import re
from pathlib import Path
from typing import Optional

from app.validation.baselines import CheckCategory, Severity, ValidationReport, ValidationResult

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_APP_DIR = _BACKEND_ROOT / "app"


def validate_health(report: ValidationReport) -> None:
    """Run all component health checks (static analysis, no live backend needed)."""
    _check_lm_studio_lifecycle(report)
    _check_turboquant_integration(report)
    _check_phase10_completeness(report)
    _check_route_completeness(report)
    _check_websocket_endpoints(report)
    _check_xss_vulnerabilities(report)
    _check_race_conditions(report)
    _check_truncated_functions(report)


def _check_lm_studio_lifecycle(report: ValidationReport) -> None:
    """Verify load_model/unload_model have real implementations, not no-ops.

    The audit flagged these as effectively no-ops that log but don't verify state.
    """
    client_path = _APP_DIR / "services" / "lm_studio_client.py"
    if not client_path.exists():
        report.add(
            ValidationResult(
                check_id="HLT-001",
                category=CheckCategory.HEALTH,
                severity=Severity.CRITICAL,
                passed=False,
                message="lm_studio_client.py not found",
                module="app.services.lm_studio_client",
            )
        )
        return

    source = client_path.read_text(encoding="utf-8")

    # Check if load_model has verification logic (not just logging)
    load_fn_match = re.search(
        r"async def load_model\(.*?\n(.*?)(?=\n    async def |\nclass |\Z)", source, re.DOTALL
    )
    if load_fn_match:
        body = load_fn_match.group(1)
        has_verification = any(
            kw in body
            for kw in [
                "verify",
                "confirm",
                "status",
                "assert",
                "raise",
                "loaded_models",
                "poll",
                "check",
            ]
        )
        has_only_logging = "logger." in body and "return" in body and not has_verification
        report.add(
            ValidationResult(
                check_id="HLT-001",
                category=CheckCategory.HEALTH,
                severity=Severity.HIGH,
                passed=has_verification,
                message=(
                    "load_model has state verification logic"
                    if has_verification
                    else "load_model lacks verification — audit flagged as no-op"
                ),
                module="app.services.lm_studio_client",
                remediation=(
                    "Add post-load verification: poll LM Studio /v1/models "
                    "to confirm model appears in loaded list"
                ),
            )
        )

    # Same check for unload_model
    unload_fn_match = re.search(
        r"async def unload_model\(.*?\n(.*?)(?=\n    async def |\nclass |\Z)", source, re.DOTALL
    )
    if unload_fn_match:
        body = unload_fn_match.group(1)
        has_vram_check = any(
            kw in body for kw in ["nvml", "vram", "free", "pynvml", "memory", "verify"]
        )
        report.add(
            ValidationResult(
                check_id="HLT-002",
                category=CheckCategory.HEALTH,
                severity=Severity.HIGH,
                passed=has_vram_check,
                message=(
                    "unload_model verifies VRAM is freed"
                    if has_vram_check
                    else "unload_model does not verify VRAM reclamation"
                ),
                module="app.services.lm_studio_client",
                remediation=(
                    "After unload, poll pynvml to confirm VRAM usage "
                    "decreased by expected amount"
                ),
            )
        )


def _check_turboquant_integration(report: ValidationReport) -> None:
    """Check if TurboQuant params are actually sent to LM Studio."""
    client_path = _APP_DIR / "services" / "lm_studio_client.py"
    manager_path = _APP_DIR / "services" / "model_manager.py"

    # Check if KV cache params are passed in API requests
    sources_to_check = [client_path, manager_path]
    kv_params_sent = False
    for path in sources_to_check:
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        if any(
            kw in content for kw in ["cache_type_k", "cache-type-k", "cache_type_v", "cache-type-v"]
        ):
            # Check if it's in a request payload, not just a config
            if re.search(r"(json|body|payload|data)\s*[=\[].*cache.type", content):
                kv_params_sent = True

    report.add(
        ValidationResult(
            check_id="HLT-010",
            category=CheckCategory.HEALTH,
            severity=Severity.MEDIUM,
            passed=kv_params_sent,
            message=(
                "KV cache quantization params sent in LM Studio requests"
                if kv_params_sent
                else "TurboQuant is config-only — KV cache types never sent to LM Studio"
            ),
            remediation=(
                "Pass cache_type_k and cache_type_v from tier config "
                "in model load requests to LM Studio"
            ),
        )
    )


def _check_phase10_completeness(report: ValidationReport) -> None:
    """Verify Phase 10 (Vector KB + Hybrid RAG) components exist and are wired."""
    required_files = {
        "embedding_service.py": "EmbeddingService",
        "text_chunker.py": "TextChunker",
        "vector_kb.py": "VectorKBService",
        "hybrid_rag.py": "HybridRAGSearch",
    }

    for filename, class_name in required_files.items():
        filepath = _APP_DIR / "services" / filename
        exists = filepath.exists()
        has_class = False
        if exists:
            content = filepath.read_text(encoding="utf-8")
            has_class = f"class {class_name}" in content

        report.add(
            ValidationResult(
                check_id=f"HLT-020-{filename}",
                category=CheckCategory.HEALTH,
                severity=Severity.HIGH if not exists else Severity.INFO,
                passed=exists and has_class,
                message=(
                    f"Phase 10: {filename} exists with {class_name}"
                    if (exists and has_class)
                    else f"Phase 10: {filename} missing or incomplete"
                ),
                module=f"app.services.{filename.replace('.py', '')}",
            )
        )

    # Check if embedding service is initialized in lifespan
    main_path = _APP_DIR / "main.py"
    if main_path.exists():
        content = main_path.read_text(encoding="utf-8")
        has_embedding_init = "EmbeddingService" in content or "embedding" in content.lower()
        report.add(
            ValidationResult(
                check_id="HLT-021",
                category=CheckCategory.HEALTH,
                severity=Severity.MEDIUM,
                passed=has_embedding_init,
                message=(
                    "EmbeddingService initialized in main.py lifespan"
                    if has_embedding_init
                    else "EmbeddingService not found in main.py lifespan"
                ),
                remediation="Add EmbeddingService to lifespan initialization in main.py",
            )
        )


def _check_route_completeness(report: ValidationReport) -> None:
    """Verify all PRD-required routes exist in router files."""
    required_routes = [
        ("knowledge.py", "POST", "/knowledge/upload"),
        ("knowledge.py", "GET", "/knowledge/bases"),
        ("system.py", "GET", "/health"),
        ("system.py", "GET", "/vram/status"),
        ("retrieval.py", "POST", "/retrieve"),
        ("agent.py", "POST", "/research"),
        ("agent.py", "POST", "/questions/generate"),
        ("agent.py", "POST", "/learning/start"),
    ]

    routers_dir = _APP_DIR / "routers"
    for filename, method, path_fragment in required_routes:
        filepath = routers_dir / filename
        if not filepath.exists():
            report.add(
                ValidationResult(
                    check_id=f"HLT-030-{path_fragment}",
                    category=CheckCategory.HEALTH,
                    severity=Severity.CRITICAL,
                    passed=False,
                    message=f"Router file {filename} missing — route {path_fragment} unavailable",
                )
            )
            continue

        content = filepath.read_text(encoding="utf-8")
        route_key = path_fragment.split("/")[-1]
        found = route_key in content and f"@router.{method.lower()}" in content.lower()

        report.add(
            ValidationResult(
                check_id=f"HLT-030-{path_fragment}",
                category=CheckCategory.HEALTH,
                severity=Severity.HIGH if not found else Severity.INFO,
                passed=found,
                message=f"Route {method} {path_fragment} {'found' if found else 'MISSING'}",
            )
        )


def _check_websocket_endpoints(report: ValidationReport) -> None:
    """Verify WebSocket endpoints are defined in main.py."""
    main_path = _APP_DIR / "main.py"
    if not main_path.exists():
        return

    content = main_path.read_text(encoding="utf-8")

    for ws_path in ["/api/v1/solve", "/ws/metrics"]:
        found = ws_path in content and "websocket" in content.lower()
        report.add(
            ValidationResult(
                check_id=f"HLT-040-{ws_path}",
                category=CheckCategory.HEALTH,
                severity=Severity.HIGH if not found else Severity.INFO,
                passed=found,
                message=f"WebSocket endpoint {ws_path} {'defined' if found else 'MISSING'}",
            )
        )


def _check_xss_vulnerabilities(report: ValidationReport) -> None:
    """Scan frontend for dangerouslySetInnerHTML without sanitization."""
    frontend_dir = _BACKEND_ROOT.parent / "frontend"
    if not frontend_dir.exists():
        return

    dangerous_files: list[str] = []
    for tsx_file in frontend_dir.rglob("*.tsx"):
        try:
            content = tsx_file.read_text(encoding="utf-8")
        except Exception:
            continue
        if "dangerouslySetInnerHTML" in content:
            has_sanitize = "DOMPurify" in content or "sanitize" in content.lower()
            if not has_sanitize:
                rel = str(tsx_file.relative_to(frontend_dir))
                dangerous_files.append(rel)

    report.add(
        ValidationResult(
            check_id="HLT-050",
            category=CheckCategory.HEALTH,
            severity=Severity.HIGH if dangerous_files else Severity.INFO,
            passed=not dangerous_files,
            message=(
                f"XSS risk: dangerouslySetInnerHTML without sanitization in: "
                f"{', '.join(dangerous_files)}"
                if dangerous_files
                else "No unsanitized HTML injection found"
            ),
            remediation="Add DOMPurify: dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(html) }}",
        )
    )


def _check_race_conditions(report: ValidationReport) -> None:
    """Detect known race-condition pattern in deep_research.py."""
    dr_path = _APP_DIR / "services" / "deep_research.py"
    if not dr_path.exists():
        return

    content = dr_path.read_text(encoding="utf-8")

    # Check for file-based state + parallel execution without locking
    has_parallel = "asyncio.gather" in content or "Semaphore" in content
    has_file_io = "_save_session" in content and "_load_session" in content
    has_lock = "asyncio.Lock" in content or "threading.Lock" in content

    is_vulnerable = has_parallel and has_file_io and not has_lock

    report.add(
        ValidationResult(
            check_id="HLT-060",
            category=CheckCategory.HEALTH,
            severity=Severity.CRITICAL if is_vulnerable else Severity.INFO,
            passed=not is_vulnerable,
            message=(
                "Deep Research: parallel file I/O without locking — race condition"
                if is_vulnerable
                else "Deep Research: no file-based race condition detected"
            ),
            module="app.services.deep_research",
            remediation="Add asyncio.Lock per session_id to serialize file reads/writes",
        )
    )


def _check_truncated_functions(report: ValidationReport) -> None:
    """Detect functions that end without a return statement (truncated code)."""
    agent_path = _APP_DIR / "routers" / "agent.py"
    if not agent_path.exists():
        return

    content = agent_path.read_text(encoding="utf-8")

    # Look for async def that's immediately followed by a decorator or class
    # without a return statement — indicates truncated function
    pattern = re.compile(
        r"(async def \w+\([^)]*\).*?)\n(@router\.|# ---)",
        re.DOTALL,
    )

    for match in pattern.finditer(content):
        func_body = match.group(1)
        func_name_match = re.search(r"async def (\w+)", func_body)
        func_name = func_name_match.group(1) if func_name_match else "unknown"

        has_return = "return " in func_body
        if not has_return:
            report.add(
                ValidationResult(
                    check_id=f"HLT-070-{func_name}",
                    category=CheckCategory.HEALTH,
                    severity=Severity.CRITICAL,
                    passed=False,
                    message=(
                        f"Truncated function: '{func_name}' has no return statement — "
                        "will return None and likely cause 500 errors"
                    ),
                    module="app.routers.agent",
                    remediation=f"Complete the implementation of '{func_name}' in agent.py",
                )
            )
