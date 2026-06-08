"""Tests for alerting service — Day 16."""

import pytest

from app.services.alerting import AlertState, _check_error_rate


def _fresh_state():
    """Return a fresh AlertState and patch it into the module global."""
    from app.services import alerting

    old = alerting._alert_state
    alerting._alert_state = AlertState()
    return alerting._alert_state, old


def test_alert_state_initial_values():
    """Fresh AlertState has no alerts firing."""
    state = AlertState()
    assert not state.vram_warning
    assert not state.vram_critical
    assert not state.llm_down
    assert not state.high_error_rate
    assert state.error_rate == 0.0


def test_error_rate_tracking():
    """record_request increments totals; error_rate is correct."""
    state = AlertState()
    for _ in range(8):
        state.record_request(200)
    for _ in range(2):
        state.record_request(500)
    assert state.error_rate == pytest.approx(0.2)
    assert state._error_counts["total"] == 10
    assert state._error_counts["errors"] == 2


def test_error_rate_zero_when_no_requests():
    """error_rate is 0 when no requests have been recorded."""
    state = AlertState()
    assert state.error_rate == 0.0


def test_check_error_rate_fires_on_threshold():
    """_check_error_rate fires when error rate >= threshold with enough requests."""
    state, old = _fresh_state()
    try:
        for _ in range(5):
            state.record_request(200)
        for _ in range(6):
            state.record_request(500)
        # error_rate = 6/11 = 0.545 >= 0.1 threshold, total >= 10
        _check_error_rate()
        assert state.high_error_rate
    finally:
        from app.services import alerting

        alerting._alert_state = old


def test_check_error_rate_not_fired_below_minimum_requests():
    """_check_error_rate does not fire with fewer than 10 requests."""
    state, old = _fresh_state()
    try:
        for _ in range(3):
            state.record_request(500)
        # error_rate = 1.0 but total = 3 < 10
        _check_error_rate()
        assert not state.high_error_rate
    finally:
        from app.services import alerting

        alerting._alert_state = old


def test_check_error_rate_clears_when_rate_drops():
    """_check_error_rate clears when rate drops below threshold."""
    state, old = _fresh_state()
    try:
        # Fire the alert
        for _ in range(5):
            state.record_request(200)
        for _ in range(6):
            state.record_request(500)
        _check_error_rate()
        assert state.high_error_rate
        # Reset counters and record mostly successes
        state._error_counts = {"total": 20, "errors": 1}
        _check_error_rate()
        assert not state.high_error_rate
    finally:
        from app.services import alerting

        alerting._alert_state = old


def test_alert_state_thresholds_are_configurable():
    """Thresholds come from environment variables with sane defaults."""
    from app.services import alerting

    assert isinstance(alerting.VRAM_WARN_PCT, float)
    assert isinstance(alerting.VRAM_CRIT_PCT, float)
    assert isinstance(alerting.ERROR_RATE_WARN, float)
    assert alerting.VRAM_WARN_PCT < alerting.VRAM_CRIT_PCT
