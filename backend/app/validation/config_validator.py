"""Configuration Validator — Dimension 5.

Scans config.py and .env patterns for security misconfigurations,
empty defaults, and deviation from environment-based configuration.

Runs without requiring a live backend — pure static analysis.
"""

import ast
import os
import re
from pathlib import Path

from app.validation.baselines import CheckCategory, Severity, ValidationReport, ValidationResult

# Path to the backend app directory (resolve relative to this file)
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_APP_DIR = _BACKEND_ROOT / "app"
_PROJECT_ROOT = _BACKEND_ROOT.parent


# ── Required environment variables (from PRD Appendix A) ──────────────────

REQUIRED_ENV_VARS = {
    "LLM_HOST": {
        "severity": Severity.CRITICAL,
        "remediation": "Set LLM_HOST to your LM Studio URL, e.g., http://localhost:1234",
    },
    "EMBEDDING_HOST": {
        "severity": Severity.HIGH,
        "remediation": "Set EMBEDDING_HOST to the embedding API endpoint",
    },
}

# Patterns that indicate insecure credential handling
INSECURE_PATTERNS = [
    {
        "pattern": r'(?:api_key|password|secret)\s*[:=]\s*["\'](?!lm-studio)[^"\']{3,}["\']',
        "message": "Hardcoded credential detected",
        "severity": Severity.CRITICAL,
        "remediation": "Move credentials to environment variables or .env file",
    },
    {
        "pattern": r'host\s*[:=]\s*["\'](?:http://(?!localhost|127\.0\.0\.1))',
        "message": "Non-localhost host hardcoded — possible external dependency",
        "severity": Severity.MEDIUM,
        "remediation": "Use environment variable for host configuration",
    },
]


def validate_config(report: ValidationReport) -> None:
    """Run all configuration validation checks."""
    _check_env_example_exists(report)
    _check_config_defaults(report)
    _check_hardcoded_credentials(report)
    _check_cors_configuration(report)
    _check_frontend_api_consistency(report)


def _check_env_example_exists(report: ValidationReport) -> None:
    """Verify .env.example template exists for onboarding."""
    env_example = _PROJECT_ROOT / ".env.example"
    env_file = _PROJECT_ROOT / ".env"
    backend_env = _BACKEND_ROOT / ".env"

    has_template = env_example.exists() or (_BACKEND_ROOT / ".env.example").exists()

    report.add(
        ValidationResult(
            check_id="CFG-001",
            category=CheckCategory.CONFIG,
            severity=Severity.HIGH,
            passed=has_template,
            message=(
                ".env.example template exists"
                if has_template
                else "No .env.example found — new developers cannot onboard"
            ),
            remediation="Create .env.example with all required variables from PRD Appendix A",
        )
    )

    has_env = env_file.exists() or backend_env.exists()
    report.add(
        ValidationResult(
            check_id="CFG-002",
            category=CheckCategory.CONFIG,
            severity=Severity.INFO,
            passed=has_env,
            message=(
                ".env file detected" if has_env else "No .env file found — using hardcoded defaults"
            ),
        )
    )


def _check_config_defaults(report: ValidationReport) -> None:
    """Parse config.py AST to find empty/dangerous defaults."""
    config_path = _APP_DIR / "config.py"
    if not config_path.exists():
        report.add(
            ValidationResult(
                check_id="CFG-010",
                category=CheckCategory.CONFIG,
                severity=Severity.CRITICAL,
                passed=False,
                message="config.py not found at expected path",
                module="app.config",
            )
        )
        return

    source = config_path.read_text(encoding="utf-8")

    # Check for empty string defaults on critical fields
    empty_defaults = re.findall(r'(\w+)\s*:\s*str\s*=\s*["\'][\s]*["\']', source)
    for field_name in empty_defaults:
        is_critical = field_name.lower() in ("llm_host", "llm_model", "embedding_host")
        report.add(
            ValidationResult(
                check_id=f"CFG-011-{field_name}",
                category=CheckCategory.CONFIG,
                severity=Severity.CRITICAL if is_critical else Severity.MEDIUM,
                passed=not is_critical,
                message=f"config.py: '{field_name}' has empty string default",
                module="app.config",
                remediation=f"Set a sensible default for '{field_name}' or require via env var",
            )
        )

    # Check that pydantic-settings is used (env var loading)
    uses_settings = "BaseSettings" in source or "pydantic_settings" in source
    report.add(
        ValidationResult(
            check_id="CFG-012",
            category=CheckCategory.CONFIG,
            severity=Severity.MEDIUM,
            passed=uses_settings,
            message=(
                "config.py uses pydantic-settings for env loading"
                if uses_settings
                else "config.py does not use pydantic-settings"
            ),
            remediation="Migrate to pydantic_settings.BaseSettings for .env auto-loading",
        )
    )


def _check_hardcoded_credentials(report: ValidationReport) -> None:
    """Scan Python files for hardcoded secrets."""
    py_files = list(_APP_DIR.rglob("*.py"))
    found_issues = []

    for py_file in py_files:
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        rel_path = py_file.relative_to(_BACKEND_ROOT)
        for spec in INSECURE_PATTERNS:
            matches = re.finditer(spec["pattern"], content, re.IGNORECASE)
            for match in matches:
                # Exclude test files
                if "test" in str(rel_path).lower():
                    continue
                found_issues.append(
                    {
                        "file": str(rel_path),
                        "match": match.group()[:60],
                        **spec,
                    }
                )

    if found_issues:
        for i, issue in enumerate(found_issues[:5]):  # Cap at 5
            report.add(
                ValidationResult(
                    check_id=f"CFG-020-{i}",
                    category=CheckCategory.CONFIG,
                    severity=issue["severity"],
                    passed=False,
                    message=f"{issue['message']} in {issue['file']}: {issue['match']}",
                    remediation=issue["remediation"],
                )
            )
    else:
        report.add(
            ValidationResult(
                check_id="CFG-020",
                category=CheckCategory.CONFIG,
                severity=Severity.INFO,
                passed=True,
                message="No hardcoded credentials detected in source files",
            )
        )


def _check_cors_configuration(report: ValidationReport) -> None:
    """Verify CORS is configured correctly for local-first app."""
    main_path = _APP_DIR / "main.py"
    cors_path = _APP_DIR / "middleware" / "cors.py"
    if not main_path.exists():
        return

    content = main_path.read_text(encoding="utf-8")
    cors_content = cors_path.read_text(encoding="utf-8") if cors_path.exists() else ""

    has_cors = "CORSMiddleware" in content or "CORSMiddleware" in cors_content
    has_wildcard = (
        'allow_origins=["*"]' in content
        or "allow_origins=['*']" in content
        or 'allow_origins=["*"]' in cors_content
        or "allow_origins=['*']" in cors_content
    )

    report.add(
        ValidationResult(
            check_id="CFG-030",
            category=CheckCategory.CONFIG,
            severity=Severity.INFO if has_cors else Severity.MEDIUM,
            passed=has_cors,
            message=(
                "CORS middleware configured"
                if has_cors
                else "No CORS middleware found — frontend will be blocked"
            ),
            remediation="Add CORSMiddleware to main.py" if not has_cors else None,
        )
    )

    if has_wildcard:
        report.add(
            ValidationResult(
                check_id="CFG-031",
                category=CheckCategory.CONFIG,
                severity=Severity.LOW,
                passed=True,  # Acceptable for local-first
                message="CORS allows all origins (acceptable for local-first architecture)",
            )
        )


def _check_frontend_api_consistency(report: ValidationReport) -> None:
    """Check that frontend files use consistent API base URLs."""
    frontend_dir = _PROJECT_ROOT / "frontend"
    if not frontend_dir.exists():
        return

    absolute_pattern = re.compile(r"http://localhost:\d+")
    relative_pattern = re.compile(r'["\']\/api\/v1\/')

    absolute_files: list[str] = []
    relative_files: list[str] = []

    for tsx_file in frontend_dir.rglob("*.tsx"):
        try:
            content = tsx_file.read_text(encoding="utf-8")
        except Exception:
            continue
        rel = str(tsx_file.relative_to(frontend_dir))

        if absolute_pattern.search(content):
            absolute_files.append(rel)
        if relative_pattern.search(content):
            relative_files.append(rel)

    has_both = bool(absolute_files) and bool(relative_files)

    report.add(
        ValidationResult(
            check_id="CFG-040",
            category=CheckCategory.CONFIG,
            severity=Severity.HIGH if has_both else Severity.INFO,
            passed=not has_both,
            message=(
                (
                    f"Inconsistent API URLs: {len(absolute_files)} file(s) use absolute "
                    f"URLs, {len(relative_files)} use relative paths"
                )
                if has_both
                else "Frontend API URLs are consistent"
            ),
            remediation=(
                (
                    "Centralize API base URL in lib/config.ts and import everywhere. "
                    f"Absolute: {', '.join(absolute_files[:3])}. "
                    f"Relative: {', '.join(relative_files[:3])}"
                )
                if has_both
                else None
            ),
        )
    )
