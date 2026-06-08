"""Tests for the Validation API Routes."""

from unittest.mock import patch

from fastapi.testclient import TestClient


def create_test_app():
    """Create a minimal FastAPI app with validation routes."""
    from fastapi import FastAPI

    from app.validation.validation_routes import router

    app = FastAPI()
    app.include_router(router)
    return app


def test_run_validation():
    """Test GET /api/v1/validation/run."""
    app = create_test_app()
    client = TestClient(app)

    with patch("app.validation.validation_routes.validate_config") as mock_cfg:
        with patch("app.validation.validation_routes.validate_health") as mock_health:
            with patch("app.validation.validation_routes.validate_remediation") as mock_rem:
                # Test fast mode (default)
                response = client.get("/api/v1/validation/run?fast=true")

                assert response.status_code == 200
                data = response.json()
                assert "timestamp" in data

                mock_cfg.assert_called_once()
                mock_health.assert_called_once()
                mock_rem.assert_called_once()


def test_run_validation_not_fast():
    """Test GET /api/v1/validation/run with fast=false."""
    app = create_test_app()
    client = TestClient(app)

    with patch("app.validation.validation_routes.validate_config"):
        with patch("app.validation.validation_routes.validate_health"):
            with patch("app.validation.validation_routes.validate_remediation"):
                with patch("app.validation.coverage_tracker.validate_coverage") as mock_cov:
                    response = client.get("/api/v1/validation/run?fast=false")

                    assert response.status_code == 200
                    mock_cov.assert_called_once()


def test_get_latest_report():
    """Test GET /api/v1/validation/report."""
    app = create_test_app()
    client = TestClient(app)

    # Initially empty
    with patch("app.validation.validation_routes._last_report", None):
        response = client.get("/api/v1/validation/report")
        assert response.status_code == 200
        assert "error" in response.json()

    # After run
    with patch("app.validation.validation_routes._last_report", {"status": "ok"}):
        response = client.get("/api/v1/validation/report")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_get_remediation_progress():
    """Test GET /api/v1/validation/remediation."""
    app = create_test_app()
    client = TestClient(app)

    # Mock the REMEDIATION_ITEMS list inside the router module
    mock_items = [
        {"id": "TEST-1", "sprint": 1, "description": "test"},
        {"id": "TEST-2", "sprint": 2, "description": "test 2"},
    ]

    # Mock validate_remediation to populate report with some results
    def mock_validate(report):
        from app.validation.baselines import CheckCategory, Severity, ValidationResult

        report.add(
            ValidationResult(
                check_id="TEST-1",
                category=CheckCategory.REMEDIATION,
                severity=Severity.MEDIUM,
                passed=True,
                message="Test 1 passed",
            )
        )
        report.add(
            ValidationResult(
                check_id="TEST-2",
                category=CheckCategory.REMEDIATION,
                severity=Severity.MEDIUM,
                passed=False,
                message="Test 2 failed",
            )
        )
        report.add(
            ValidationResult(
                check_id="REM-SUMMARY",
                category=CheckCategory.REMEDIATION,
                severity=Severity.LOW,
                passed=True,
                message="Summary",
            )
        )

    with patch("app.validation.validation_routes.REMEDIATION_ITEMS", mock_items):
        with patch(
            "app.validation.validation_routes.validate_remediation", side_effect=mock_validate
        ):
            response = client.get("/api/v1/validation/remediation")

            assert response.status_code == 200
            data = response.json()
            assert "overall_progress" in data
            assert data["overall_progress"] == "1/2"
            assert data["overall_pct"] == 50.0
            assert "sprints" in data
            assert "1" in data["sprints"]
            assert "2" in data["sprints"]
            assert data["sprints"]["1"]["done"] == 1
            assert data["sprints"]["2"]["done"] == 0


def test_get_health_status():
    """Test GET /api/v1/validation/health."""
    app = create_test_app()
    client = TestClient(app)

    def mock_validate(report):
        from app.validation.baselines import CheckCategory, Severity, ValidationResult

        report.add(
            ValidationResult(
                check_id="HEALTH-1",
                category=CheckCategory.HEALTH,
                severity=Severity.CRITICAL,
                passed=True,
                message="Health OK",
            )
        )

    with patch("app.validation.validation_routes.validate_health", side_effect=mock_validate):
        response = client.get("/api/v1/validation/health")

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["check_id"] == "HEALTH-1"
