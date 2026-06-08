"""Tests for the OS keyring wrapper used to store provider API keys."""

import os

import pytest

from app.services import secrets as secrets_mod
from app.services.secrets import delete_secret, get_secret, is_keyring_available, set_secret


@pytest.fixture(autouse=True)
def _clean_keyring():
    """Remove the test-only entries we create so other tests aren't affected."""
    yield
    # Best-effort cleanup; the keyring module is best-effort itself.
    try:
        delete_secret("UDIP_TEST_KEY")
        delete_secret("UDIP_TEST_KEY_2")
    except Exception:
        pass


def test_is_keyring_available_returns_bool():
    result = is_keyring_available()
    assert isinstance(result, bool)


def test_roundtrip_set_get_delete():
    if not is_keyring_available():
        pytest.skip("OS keyring backend not functional on this host (CI/headless).")
    set_secret("UDIP_TEST_KEY", "sk-test-12345")
    assert get_secret("UDIP_TEST_KEY") == "sk-test-12345"
    assert delete_secret("UDIP_TEST_KEY") is True
    # After deletion, env fallback returns "" (not the value).
    os.environ.pop("UDIP_TEST_KEY", None)
    assert get_secret("UDIP_TEST_KEY") == ""


def test_get_secret_falls_back_to_environ():
    if not is_keyring_available():
        pytest.skip("OS keyring backend not functional on this host (CI/headless).")
    # Delete any prior value first
    delete_secret("UDIP_TEST_KEY_2")
    os.environ["UDIP_TEST_KEY_2"] = "from-env"
    try:
        # No value in keyring → should return the env value
        assert get_secret("UDIP_TEST_KEY_2") == "from-env"
    finally:
        os.environ.pop("UDIP_TEST_KEY_2", None)


def test_set_secret_raises_when_keyring_unavailable(monkeypatch):
    """When the keyring backend is not available, set_secret must raise."""
    monkeypatch.setattr(secrets_mod, "is_keyring_available", lambda: False)
    with pytest.raises(RuntimeError) as exc:
        set_secret("UDIP_TEST_KEY", "x")
    assert "keyring" in str(exc.value).lower() or "OS keyring" in str(exc.value)


def test_get_secret_returns_empty_when_neither_source_has_value(monkeypatch):
    monkeypatch.setattr(secrets_mod, "is_keyring_available", lambda: False)
    monkeypatch.delenv("UDIP_NOT_SET_ANYWHERE", raising=False)
    assert get_secret("UDIP_NOT_SET_ANYWHERE") == ""


def test_delete_secret_is_idempotent():
    if not is_keyring_available():
        pytest.skip("OS keyring backend not functional on this host (CI/headless).")
    # Deleting a key that doesn't exist must not raise.
    assert delete_secret("UDIP_TEST_KEY_NEVER_SET") is False
