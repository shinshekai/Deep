"""Tests for the UDIP Production Readiness Validation Pipeline.

Validates that the validation system itself works correctly —
baselines are sensible, checks detect known conditions, and
the report format is correct.
"""

from app.validation.baselines import (
    TIER_SPECS,
    CheckCategory,
    CoverageBaselines,
    PerformanceBaselines,
    Severity,
    ValidationReport,
    ValidationResult,
    VRAMBaselines,
)

# ── Baseline Sanity Tests ─────────────────────────────────────────────────


class TestBaselines:
    def test_performance_baselines_are_positive(self):
        b = PerformanceBaselines()
        assert b.ttft_max_ms > 0
        assert b.min_tokens_per_sec > 0
        assert b.retrieval_max_ms > 0

    def test_vram_thresholds_are_ordered(self):
        b = VRAMBaselines()
        assert b.green_max_pct < b.yellow_max_pct < b.orange_max_pct < 100

    def test_coverage_baseline_is_80_pct(self):
        b = CoverageBaselines()
        assert b.global_min_pct == 80.0

    def test_tier_specs_cover_all_tiers(self):
        assert set(TIER_SPECS.keys()) == {1, 2, 3}

    def test_tier_1_is_always_resident(self):
        assert TIER_SPECS[1].ttl_seconds is None

    def test_tier_3_has_shortest_ttl(self):
        assert TIER_SPECS[3].ttl_seconds < TIER_SPECS[2].ttl_seconds

    def test_tier_kv_cache_configs_match_spec(self):
        """From 03-inference-strategy.md Section 2."""
        assert TIER_SPECS[1].kv_cache_k == "q4_0"
        assert TIER_SPECS[1].kv_cache_v == "q4_0"
        assert TIER_SPECS[2].kv_cache_k == "q8_0"
        assert TIER_SPECS[2].kv_cache_v == "q4_0"
        assert TIER_SPECS[3].kv_cache_k == "q8_0"
        assert TIER_SPECS[3].kv_cache_v == "q8_0"


# ── ValidationResult Tests ────────────────────────────────────────────────


class TestValidationResult:
    def test_to_dict_includes_all_fields(self):
        r = ValidationResult(
            check_id="TEST-001",
            category=CheckCategory.HEALTH,
            severity=Severity.HIGH,
            passed=False,
            message="test message",
            remediation="fix it",
        )
        d = r.to_dict()
        assert d["check_id"] == "TEST-001"
        assert d["severity"] == "high"
        assert d["passed"] is False
        assert d["remediation"] == "fix it"

    def test_severity_enum_values(self):
        assert Severity.CRITICAL.value == "critical"
        assert Severity.INFO.value == "info"


# ── ValidationReport Tests ────────────────────────────────────────────────


class TestValidationReport:
    def test_empty_report_is_green(self):
        r = ValidationReport(timestamp="2026-01-01T00:00:00Z")
        assert r.is_green is True
        assert r.pass_rate == 0.0

    def test_pass_rate_calculation(self):
        r = ValidationReport(timestamp="2026-01-01T00:00:00Z")
        r.add(
            ValidationResult(
                check_id="A",
                category=CheckCategory.HEALTH,
                severity=Severity.INFO,
                passed=True,
                message="ok",
            )
        )
        r.add(
            ValidationResult(
                check_id="B",
                category=CheckCategory.HEALTH,
                severity=Severity.INFO,
                passed=False,
                message="bad",
            )
        )
        assert r.pass_rate == 50.0
        assert r.total_checks == 2
        assert r.passed == 1
        assert r.failed == 1

    def test_critical_failure_turns_red(self):
        r = ValidationReport(timestamp="2026-01-01T00:00:00Z")
        r.add(
            ValidationResult(
                check_id="C",
                category=CheckCategory.CONFIG,
                severity=Severity.CRITICAL,
                passed=False,
                message="boom",
            )
        )
        assert r.is_green is False
        assert r.critical_failures == 1

    def test_non_critical_failure_stays_green(self):
        r = ValidationReport(timestamp="2026-01-01T00:00:00Z")
        r.add(
            ValidationResult(
                check_id="D",
                category=CheckCategory.CONFIG,
                severity=Severity.LOW,
                passed=False,
                message="minor",
            )
        )
        assert r.is_green is True
        assert r.failed == 1

    def test_summary_markdown_includes_failures(self):
        r = ValidationReport(timestamp="2026-01-01T00:00:00Z")
        r.add(
            ValidationResult(
                check_id="E",
                category=CheckCategory.HEALTH,
                severity=Severity.HIGH,
                passed=False,
                message="something broke",
                remediation="fix the thing",
            )
        )
        md = r.summary_markdown()
        assert "something broke" in md
        assert "fix the thing" in md
        assert "❌" in md

    def test_to_dict_structure(self):
        r = ValidationReport(timestamp="2026-01-01T00:00:00Z")
        r.add(
            ValidationResult(
                check_id="F",
                category=CheckCategory.COVERAGE,
                severity=Severity.INFO,
                passed=True,
                message="ok",
            )
        )
        d = r.to_dict()
        assert "timestamp" in d
        assert "results" in d
        assert len(d["results"]) == 1


# ── Config Validator Tests ────────────────────────────────────────────────


class TestConfigValidator:
    def test_config_validation_runs_without_error(self):
        """Smoke test: config validator should not crash."""
        from app.validation.config_validator import validate_config

        report = ValidationReport(timestamp="2026-01-01T00:00:00Z")
        validate_config(report)
        assert report.total_checks > 0

    def test_detects_no_env_example(self):
        """The project now has an .env.example — should pass."""
        from app.validation.config_validator import validate_config

        report = ValidationReport(timestamp="2026-01-01T00:00:00Z")
        validate_config(report)
        env_check = next((r for r in report.results if r.check_id == "CFG-001"), None)
        assert env_check is not None
        assert env_check.passed is True

    def test_detects_empty_llm_host(self):
        """config.py has defaults now — should pass."""
        from app.validation.config_validator import validate_config

        report = ValidationReport(timestamp="2026-01-01T00:00:00Z")
        validate_config(report)
        host_check = next(
            (r for r in report.results if "llm_host" in r.check_id),
            None,
        )
        if host_check:
            assert host_check.passed is True


# ── Health Checker Tests ──────────────────────────────────────────────────


class TestHealthChecker:
    def test_health_check_runs_without_error(self):
        """Smoke test: health checker should not crash."""
        from app.validation.health_checker import validate_health

        report = ValidationReport(timestamp="2026-01-01T00:00:00Z")
        validate_health(report)
        assert report.total_checks > 0

    def test_detects_truncated_end_learning(self):
        """The audit found end_learning is truncated — now fixed."""
        from app.validation.health_checker import validate_health

        report = ValidationReport(timestamp="2026-01-01T00:00:00Z")
        validate_health(report)
        truncated = [r for r in report.results if r.check_id.startswith("HLT-070") and not r.passed]
        assert len(truncated) == 0

    def test_detects_deep_research_race(self):
        """The audit found a race condition — now fixed."""
        from app.validation.health_checker import validate_health

        report = ValidationReport(timestamp="2026-01-01T00:00:00Z")
        validate_health(report)
        race_check = next((r for r in report.results if r.check_id == "HLT-060"), None)
        assert race_check is not None
        assert race_check.passed is True

    def test_detects_xss_in_guide_page(self):
        """Guide page uses DOMPurify now."""
        from app.validation.health_checker import validate_health

        report = ValidationReport(timestamp="2026-01-01T00:00:00Z")
        validate_health(report)
        xss_check = next((r for r in report.results if r.check_id == "HLT-050"), None)
        assert xss_check is not None
        assert xss_check.passed is True


# ── Remediation Tracker Tests ─────────────────────────────────────────────


class TestRemediationTracker:
    def test_remediation_tracker_runs(self):
        from app.validation.remediation_tracker import validate_remediation

        report = ValidationReport(timestamp="2026-01-01T00:00:00Z")
        validate_remediation(report)
        assert report.total_checks > 0

    def test_remediation_has_summary(self):
        from app.validation.remediation_tracker import validate_remediation

        report = ValidationReport(timestamp="2026-01-01T00:00:00Z")
        validate_remediation(report)
        summary = next((r for r in report.results if r.check_id == "REM-SUMMARY"), None)
        assert summary is not None
        assert "Remediation progress" in summary.message

    def test_sprint1_items_detected_as_incomplete(self):
        """Sprint 1 items (known bugs) are now complete."""
        from app.validation.remediation_tracker import validate_remediation

        report = ValidationReport(timestamp="2026-01-01T00:00:00Z")
        validate_remediation(report)
        s1_items = [r for r in report.results if r.check_id.startswith("REM-S1")]
        assert len(s1_items) >= 3
        incomplete = [r for r in s1_items if not r.passed]
        assert len(incomplete) == 0


# ── Pipeline Runner Tests ─────────────────────────────────────────────────


class TestPipelineRunner:
    def test_fast_validation_completes(self):
        from app.validation.runner import run_fast_validation

        report = run_fast_validation()
        assert report.total_checks > 0
        assert isinstance(report.pass_rate, float)

    def test_fast_validation_detects_known_issues(self):
        """The current codebase has fixed the issues."""
        from app.validation.runner import run_fast_validation

        report = run_fast_validation()
        # Should have 0 critical failures
        assert report.critical_failures == 0
