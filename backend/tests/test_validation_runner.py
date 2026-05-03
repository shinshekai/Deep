"""Tests for the Validation Pipeline Runner."""

import pytest
import sys
import argparse
from unittest.mock import patch, MagicMock
from app.validation.runner import (
    run_full_validation,
    run_ci_validation,
    run_fast_validation,
    main,
)
from app.validation.baselines import ValidationReport


def test_run_full_validation_success():
    """Test full validation without skipping any dimensions."""
    with patch("app.validation.runner.validate_config") as mock_cfg:
        with patch("app.validation.runner.validate_health") as mock_health:
            with patch("app.validation.coverage_tracker.validate_coverage") as mock_cov:
                with patch("app.validation.runner.validate_remediation") as mock_rem:
                    report = run_full_validation()

    assert isinstance(report, ValidationReport)
    mock_cfg.assert_called_once()
    mock_health.assert_called_once()
    mock_cov.assert_called_once_with(report, run_pytest=True)
    mock_rem.assert_called_once()


def test_run_full_validation_coverage_failure():
    """Test full validation handles coverage tracker exceptions."""
    with patch("app.validation.runner.validate_config"):
        with patch("app.validation.runner.validate_health"):
            with patch("app.validation.runner.validate_remediation"):
                # Make coverage tracker raise an error
                with patch("app.validation.coverage_tracker.validate_coverage", side_effect=Exception("Pytest failed")):
                    report = run_full_validation(skip_coverage=False)

    assert isinstance(report, ValidationReport)
    # The error should be logged as a result in the report
    assert any("Coverage collection failed" in res.message for res in report.results)


def test_run_full_validation_skip_coverage():
    """Test full validation with skip_coverage=True."""
    with patch("app.validation.runner.validate_config"):
        with patch("app.validation.runner.validate_health"):
            with patch("app.validation.runner.validate_remediation"):
                with patch("app.validation.coverage_tracker.validate_coverage") as mock_cov:
                    report = run_full_validation(skip_coverage=True)

    # It still tries to run coverage but with run_pytest=False
    mock_cov.assert_called_once_with(report, run_pytest=False)


def test_run_full_validation_skip_coverage_failure():
    """Test full validation with skip_coverage=True ignores existing report failures."""
    with patch("app.validation.runner.validate_config"):
        with patch("app.validation.runner.validate_health"):
            with patch("app.validation.runner.validate_remediation"):
                with patch("app.validation.coverage_tracker.validate_coverage", side_effect=Exception("Missing XML")):
                    report = run_full_validation(skip_coverage=True)

    assert isinstance(report, ValidationReport)
    # Shouldn't add error to results
    assert not any("Coverage collection failed" in res.message for res in report.results)


def test_run_ci_validation():
    """Test CI wrapper calls full validation."""
    with patch("app.validation.runner.run_full_validation") as mock_full:
        run_ci_validation()
    mock_full.assert_called_once_with(skip_coverage=False, skip_remediation=False)


def test_run_fast_validation():
    """Test fast wrapper calls full validation with skips."""
    with patch("app.validation.runner.run_full_validation") as mock_full:
        run_fast_validation()
    mock_full.assert_called_once_with(skip_coverage=True, skip_remediation=False)


def test_main_fast_mode(capsys):
    """Test CLI main() with --fast."""
    test_args = ["runner.py", "--fast"]
    with patch.object(sys, "argv", test_args):
        with patch("app.validation.runner.run_fast_validation") as mock_fast:
            mock_report = MagicMock()
            mock_report.is_green = True
            mock_report.total_checks = 10
            mock_report.passed = 10
            mock_report.failed = 0
            mock_report.critical_failures = 0
            mock_report.pass_rate = 100
            mock_report.summary_markdown.return_value = "Test Report"
            mock_fast.return_value = mock_report

            main()

    mock_fast.assert_called_once()
    captured = capsys.readouterr()
    assert "Test Report" in captured.out
    assert "✅ GREEN" in captured.out


def test_main_ci_mode_failure(capsys):
    """Test CLI main() with --ci exits with code 1 if not green."""
    test_args = ["runner.py", "--ci"]
    with patch.object(sys, "argv", test_args):
        with patch("app.validation.runner.run_ci_validation") as mock_ci:
            mock_report = MagicMock()
            mock_report.is_green = False
            mock_report.critical_failures = 2
            mock_report.summary_markdown.return_value = "Test Report"
            mock_ci.return_value = mock_report

            with pytest.raises(SystemExit) as excinfo:
                main()

            assert excinfo.value.code == 1

    captured = capsys.readouterr()
    assert "❌ CI FAILED" in captured.err


def test_main_json_output(capsys):
    """Test CLI main() with --json."""
    test_args = ["runner.py", "--json"]
    with patch.object(sys, "argv", test_args):
        with patch("app.validation.runner.run_ci_validation") as mock_ci:
            mock_report = MagicMock()
            mock_report.is_green = True
            mock_report.total_checks = 10
            mock_report.passed = 10
            mock_report.failed = 0
            mock_report.critical_failures = 0
            mock_report.pass_rate = 100
            mock_report.to_dict.return_value = {"status": "ok"}
            mock_ci.return_value = mock_report

            main()

    captured = capsys.readouterr()
    assert '"status": "ok"' in captured.out


def test_main_file_output(tmp_path, capsys):
    """Test CLI main() with --output."""
    out_file = tmp_path / "report.md"
    test_args = ["runner.py", "--output", str(out_file)]
    
    with patch.object(sys, "argv", test_args):
        with patch("app.validation.runner.run_ci_validation") as mock_ci:
            mock_report = MagicMock()
            mock_report.is_green = True
            mock_report.total_checks = 10
            mock_report.passed = 10
            mock_report.failed = 0
            mock_report.critical_failures = 0
            mock_report.pass_rate = 100
            mock_report.summary_markdown.return_value = "# Markdown Report"
            mock_ci.return_value = mock_report

            main()

    assert out_file.exists()
    assert out_file.read_text() == "# Markdown Report"
    captured = capsys.readouterr()
    assert f"Report written to {out_file}" in captured.out
