"""Test Coverage Tracker — Dimension 3.

Measures backend test coverage and validates against the 80% target.
Provides per-module granularity for critical modules.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

from app.validation.baselines import (
    CRITICAL_MODULES,
    CheckCategory,
    CoverageBaselines,
    Severity,
    ValidationReport,
    ValidationResult,
)

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_BASELINES = CoverageBaselines()


def validate_coverage(report: ValidationReport, run_pytest: bool = True) -> None:
    """Run coverage analysis and validate against thresholds.

    Args:
        report: ValidationReport to append results to.
        run_pytest: If True, run pytest with coverage. If False, read existing report.
    """
    coverage_data = _get_coverage_data(run_pytest)
    if coverage_data is None:
        report.add(
            ValidationResult(
                check_id="COV-001",
                category=CheckCategory.COVERAGE,
                severity=Severity.HIGH,
                passed=False,
                message="Failed to collect coverage data — pytest-cov may not be installed",
                remediation="pip install pytest-cov and run: pytest --cov=app --cov-report=json",
            )
        )
        return

    _check_global_coverage(report, coverage_data)
    _check_critical_modules(report, coverage_data)
    _check_test_count(report)
    _check_frontend_tests(report)


def _get_coverage_data(run_pytest: bool) -> Optional[dict]:
    """Collect coverage data, either by running pytest or reading existing report."""
    coverage_json = _BACKEND_ROOT / "coverage.json"

    if run_pytest:
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "--cov=app",
                    "--cov-report=json",
                    "--cov-report=term-missing",
                    "-q",
                    "--tb=no",
                ],
                cwd=str(_BACKEND_ROOT),
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    if coverage_json.exists():
        try:
            return json.loads(coverage_json.read_text())
        except (json.JSONDecodeError, IOError):
            return None

    return None


def _check_global_coverage(report: ValidationReport, data: dict) -> None:
    """Check overall backend coverage against 80% target."""
    totals = data.get("totals", {})
    pct = totals.get("percent_covered", 0.0)

    report.add(
        ValidationResult(
            check_id="COV-010",
            category=CheckCategory.COVERAGE,
            severity=Severity.HIGH if pct < _BASELINES.global_min_pct else Severity.INFO,
            passed=pct >= _BASELINES.global_min_pct,
            message=f"Backend coverage: {pct:.1f}% (target: {_BASELINES.global_min_pct}%)",
            metric_name="backend_coverage_pct",
            metric_value=pct,
            threshold=_BASELINES.global_min_pct,
            remediation=(
                f"Add tests to increase coverage from {pct:.1f}% to {_BASELINES.global_min_pct}%"
                if pct < _BASELINES.global_min_pct
                else None
            ),
        )
    )


def _check_critical_modules(report: ValidationReport, data: dict) -> None:
    """Check per-module coverage for critical services."""
    files_data = data.get("files", {})

    for module_path in CRITICAL_MODULES:
        # Convert module path to file path pattern
        file_key_fwd = module_path.replace(".", "/") + ".py"
        file_key_bwd = module_path.replace(".", "\\") + ".py"

        # Find matching file in coverage data
        pct = None
        for covered_file, file_info in files_data.items():
            if file_key_fwd in covered_file or file_key_bwd in covered_file:
                pct = file_info.get("summary", {}).get("percent_covered", 0.0)
                break

        if pct is None:
            report.add(
                ValidationResult(
                    check_id=f"COV-020-{module_path}",
                    category=CheckCategory.COVERAGE,
                    severity=Severity.MEDIUM,
                    passed=False,
                    message=f"No coverage data for critical module: {module_path}",
                    module=module_path,
                    remediation=f"Ensure tests import and exercise {module_path}",
                )
            )
            continue

        threshold = _BASELINES.critical_module_min_pct
        report.add(
            ValidationResult(
                check_id=f"COV-020-{module_path}",
                category=CheckCategory.COVERAGE,
                severity=Severity.HIGH if pct < threshold else Severity.INFO,
                passed=pct >= threshold,
                message=f"{module_path}: {pct:.1f}% coverage (target: {threshold}%)",
                metric_name=f"coverage_{module_path}",
                metric_value=pct,
                threshold=threshold,
                module=module_path,
                remediation=(
                    f"Add tests for {module_path} — current: {pct:.1f}%, need: {threshold}%"
                    if pct < threshold
                    else None
                ),
            )
        )


def _check_test_count(report: ValidationReport) -> None:
    """Count test files and test functions."""
    tests_dir = _BACKEND_ROOT / "tests"
    if not tests_dir.exists():
        report.add(
            ValidationResult(
                check_id="COV-030",
                category=CheckCategory.COVERAGE,
                severity=Severity.CRITICAL,
                passed=False,
                message="No tests/ directory found",
            )
        )
        return

    test_files = list(tests_dir.glob("test_*.py"))
    total_tests = 0
    for tf in test_files:
        content = tf.read_text(encoding="utf-8")
        total_tests += len(
            [
                line
                for line in content.split("\n")
                if line.strip().startswith("def test_")
                or line.strip().startswith("async def test_")
            ]
        )

    report.add(
        ValidationResult(
            check_id="COV-030",
            category=CheckCategory.COVERAGE,
            severity=Severity.INFO,
            passed=True,
            message=f"Backend: {len(test_files)} test files, ~{total_tests} test functions",
            metric_name="backend_test_count",
            metric_value=float(total_tests),
        )
    )


def _check_frontend_tests(report: ValidationReport) -> None:
    """Verify frontend test infrastructure exists."""
    frontend_dir = _BACKEND_ROOT.parent / "frontend"

    # Check for test framework
    pkg_json = frontend_dir / "package.json"
    has_test_framework = False
    if pkg_json.exists():
        content = pkg_json.read_text(encoding="utf-8")
        has_test_framework = any(fw in content for fw in ["vitest", "jest", "@testing-library"])

    # Check for test files
    test_files = (
        list(frontend_dir.rglob("*.test.tsx"))
        + list(frontend_dir.rglob("*.test.ts"))
        + list(frontend_dir.rglob("*.spec.tsx"))
        + list(frontend_dir.rglob("*.spec.ts"))
    )
    # Exclude node_modules
    test_files = [f for f in test_files if "node_modules" not in str(f)]

    report.add(
        ValidationResult(
            check_id="COV-040",
            category=CheckCategory.COVERAGE,
            severity=Severity.HIGH if not has_test_framework else Severity.INFO,
            passed=has_test_framework,
            message=(
                f"Frontend: test framework installed, {len(test_files)} test file(s)"
                if has_test_framework
                else "Frontend: NO test framework installed (NFR-5.5 requires component tests)"
            ),
            metric_name="frontend_test_files",
            metric_value=float(len(test_files)),
            remediation=(
                (
                    "Install Vitest + React Testing Library: "
                    "npm i -D vitest @testing-library/react @testing-library/jest-dom"
                )
                if not has_test_framework
                else None
            ),
        )
    )
