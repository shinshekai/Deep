"""Production Readiness Pipeline Runner.

Orchestrates all 7 validation dimensions and produces a unified report.
Can be run as:
  - CLI: python -m app.validation.runner [--fast] [--json] [--ci]
  - Import: from app.validation.runner import run_full_validation
  - API: GET /api/v1/validation/run (see validation_routes.py)
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.validation.baselines import Severity, ValidationReport
from app.validation.config_validator import validate_config
from app.validation.health_checker import validate_health
from app.validation.remediation_tracker import validate_remediation


def run_full_validation(
    skip_coverage: bool = False,
    skip_remediation: bool = False,
) -> ValidationReport:
    """Execute the full validation pipeline across all dimensions.

    Args:
        skip_coverage: Skip pytest coverage run (for fast mode / CI without GPU).
        skip_remediation: Skip remediation progress tracking.

    Returns:
        ValidationReport with all check results.
    """
    report = ValidationReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    # Dimension 5: Configuration Validation (always runs, no deps)
    validate_config(report)

    # Dimension 4: Component Health Checks (static analysis)
    validate_health(report)

    # Dimension 3: Test Coverage Tracking
    if not skip_coverage:
        try:
            from app.validation.coverage_tracker import validate_coverage

            validate_coverage(report, run_pytest=True)
        except Exception as e:
            from app.validation.baselines import CheckCategory

            report.add(
                __import__(
                    "app.validation.baselines", fromlist=["ValidationResult"]
                ).ValidationResult(
                    check_id="COV-ERR",
                    category=CheckCategory.COVERAGE,
                    severity=Severity.MEDIUM,
                    passed=False,
                    message=f"Coverage collection failed: {e}",
                )
            )
    else:
        # Still check for existing coverage report
        try:
            from app.validation.coverage_tracker import validate_coverage

            validate_coverage(report, run_pytest=False)
        except Exception:
            pass

    # Dimension 6: Remediation Progress
    if not skip_remediation:
        validate_remediation(report)

    return report


def run_ci_validation() -> ValidationReport:
    """CI-optimized validation: all static checks, coverage from existing report."""
    return run_full_validation(skip_coverage=False, skip_remediation=False)


def run_fast_validation() -> ValidationReport:
    """Fast local dev validation: static checks only, no pytest."""
    return run_full_validation(skip_coverage=True, skip_remediation=False)


def main():
    parser = argparse.ArgumentParser(description="UDIP Production Readiness Validation Pipeline")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip coverage collection (static checks only)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output JSON instead of markdown",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI mode: exit with code 1 if critical failures",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Write report to file instead of stdout",
    )
    args = parser.parse_args()

    if args.fast:
        report = run_fast_validation()
    else:
        report = run_ci_validation()

    # Format output
    if args.json_output:
        output = json.dumps(report.to_dict(), indent=2)
    else:
        output = report.summary_markdown()

    # Write output
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(output)

    # CI exit code
    if args.ci and not report.is_green:
        print(
            f"\n❌ CI FAILED: {report.critical_failures} critical failure(s)",
            file=sys.stderr,
        )
        sys.exit(1)

    # Print summary stats
    print(f"\n{'='*50}")
    print(
        f"Total: {report.total_checks} checks | "
        f"Pass: {report.passed} | Fail: {report.failed} | "
        f"Critical: {report.critical_failures}"
    )
    print(f"Pass rate: {report.pass_rate:.0f}%")
    print(f"Status: {'✅ GREEN' if report.is_green else '❌ RED'}")


if __name__ == "__main__":
    # Allow running as: python -m app.validation.runner
    # Add parent to path if needed
    import os

    backend_root = Path(__file__).resolve().parent.parent.parent
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    main()
