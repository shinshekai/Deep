"""Validation API Routes — exposes pipeline as REST endpoints.

Endpoints:
  GET  /api/v1/validation/run          — Run full validation (fast mode)
  GET  /api/v1/validation/report       — Get latest cached report
  GET  /api/v1/validation/remediation  — Get remediation progress only
  GET  /api/v1/validation/coverage     — Get coverage status only
  GET  /api/v1/validation/health       — Get component health only
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter

from app.validation.baselines import ValidationReport
from app.validation.config_validator import validate_config
from app.validation.health_checker import validate_health
from app.validation.remediation_tracker import REMEDIATION_ITEMS, validate_remediation

router = APIRouter(prefix="/api/v1/validation", tags=["validation"])

# Cache the last report to avoid re-running on every request
_last_report: Optional[dict] = None


@router.get("/run")
async def run_validation(fast: bool = True):
    """Run the validation pipeline and return results.

    Args:
        fast: If true, skip pytest coverage (default: true for API calls).
    """
    global _last_report

    report = ValidationReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    validate_config(report)
    validate_health(report)
    validate_remediation(report)

    if not fast:
        try:
            from app.validation.coverage_tracker import validate_coverage

            validate_coverage(report, run_pytest=False)
        except Exception:
            pass

    _last_report = report.to_dict()
    return _last_report


@router.get("/report")
async def get_latest_report():
    """Return the most recently cached validation report."""
    if _last_report is None:
        return {"error": "No report available. Run GET /api/v1/validation/run first."}
    return _last_report


@router.get("/remediation")
async def get_remediation_progress():
    """Get remediation progress with sprint breakdown."""
    report = ValidationReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    validate_remediation(report)

    # Group by sprint
    sprints: dict[int, dict] = {}
    for result in report.results:
        if result.check_id == "REM-SUMMARY":
            continue
        # Parse sprint from message
        sprint_num = 0
        for item in REMEDIATION_ITEMS:
            if item["id"] == result.check_id:
                sprint_num = item["sprint"]
                break

        if sprint_num not in sprints:
            sprints[sprint_num] = {"sprint": sprint_num, "items": [], "done": 0, "total": 0}
        sprints[sprint_num]["items"].append(result.to_dict())
        sprints[sprint_num]["total"] += 1
        if result.passed:
            sprints[sprint_num]["done"] += 1

    total_done = sum(s["done"] for s in sprints.values())
    total_items = sum(s["total"] for s in sprints.values())

    return {
        "timestamp": report.timestamp,
        "overall_progress": f"{total_done}/{total_items}",
        "overall_pct": round(total_done / total_items * 100, 1) if total_items else 0,
        "sprints": dict(sorted(sprints.items())),
    }


@router.get("/health")
async def get_health_status():
    """Get component health check results only."""
    report = ValidationReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    validate_health(report)
    return report.to_dict()
