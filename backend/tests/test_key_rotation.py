import os

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import system as system_mod
from app.services import secrets as secrets_mod

client = TestClient(app)


def _clear_history():
    system_mod._rotation_history.clear()


@pytest.fixture(autouse=True)
def _clean_state():
    _clear_history()
    yield
    _clear_history()


def test_rotate_key_stores_new_value(monkeypatch):
    monkeypatch.setattr(secrets_mod, "is_keyring_available", lambda: True)
    monkeypatch.setattr(system_mod, "secrets_available", lambda: True)

    response = client.post(
        "/api/v1/secrets/rotate",
        json={"key_name": "TEST_ROTATE_KEY", "new_value": "new-secret-123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["key_name"] == "TEST_ROTATE_KEY"
    assert data["new_value_masked"] != "new-secret-123"


def test_rotate_key_returns_old_value_masked(monkeypatch):
    monkeypatch.setattr(secrets_mod, "is_keyring_available", lambda: True)
    monkeypatch.setattr(system_mod, "secrets_available", lambda: True)

    secrets_mod.set_secret("OLD_KEY_TEST", "old-secret-value")
    try:
        response = client.post(
            "/api/v1/secrets/rotate",
            json={"key_name": "OLD_KEY_TEST", "new_value": "new-secret-value"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["old_value_masked"] == "old-********alue"
        assert data["new_value_masked"] == "new-********alue"
    finally:
        secrets_mod.delete_secret("OLD_KEY_TEST")


def test_rotate_key_empty_name_returns_400():
    response = client.post(
        "/api/v1/secrets/rotate",
        json={"key_name": "", "new_value": "val"},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "InvalidKey"


def test_rotate_key_whitespace_name_returns_400():
    response = client.post(
        "/api/v1/secrets/rotate",
        json={"key_name": "   ", "new_value": "val"},
    )
    assert response.status_code == 400


def test_rotate_key_records_in_history(monkeypatch):
    monkeypatch.setattr(secrets_mod, "is_keyring_available", lambda: True)
    monkeypatch.setattr(system_mod, "secrets_available", lambda: True)

    client.post(
        "/api/v1/secrets/rotate",
        json={"key_name": "HISTORY_KEY", "new_value": "hist-val"},
    )

    response = client.get("/api/v1/secrets/rotation-history")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["history"][0]["key_name"] == "HISTORY_KEY"


def test_rotation_history_capped_at_50(monkeypatch):
    monkeypatch.setattr(secrets_mod, "is_keyring_available", lambda: True)
    monkeypatch.setattr(system_mod, "secrets_available", lambda: True)

    for i in range(55):
        client.post(
            "/api/v1/secrets/rotate",
            json={"key_name": f"CAP_KEY_{i}", "new_value": f"val-{i}"},
        )

    response = client.get("/api/v1/secrets/rotation-history")
    data = response.json()
    assert data["count"] == 50
    assert data["history"][0]["key_name"] == "CAP_KEY_5"
    assert data["history"][-1]["key_name"] == "CAP_KEY_54"


def test_rotation_history_empty_by_default():
    response = client.get("/api/v1/secrets/rotation-history")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0
    assert data["history"] == []


def test_rotate_key_sets_os_environ(monkeypatch):
    monkeypatch.setattr(secrets_mod, "is_keyring_available", lambda: True)
    monkeypatch.setattr(system_mod, "secrets_available", lambda: True)

    client.post(
        "/api/v1/secrets/rotate",
        json={"key_name": "ENV_ROTATE_TEST", "new_value": "env-val-999"},
    )
    assert os.environ.get("ENV_ROTATE_TEST") == "env-val-999"


def test_rotate_key_returns_503_on_keyring_failure(monkeypatch):
    def fail_set(name, value):
        raise RuntimeError("keyring write failed")

    monkeypatch.setattr(secrets_mod, "is_keyring_available", lambda: True)
    monkeypatch.setattr(system_mod, "secrets_available", lambda: True)
    monkeypatch.setattr(system_mod, "secrets_set", fail_set)

    response = client.post(
        "/api/v1/secrets/rotate",
        json={"key_name": "FAIL_KEY", "new_value": "should-not-save"},
    )
    assert response.status_code == 503
    assert response.json()["error"] == "KeyringWriteFailed"


def test_rotate_key_mask_short_value():
    assert system_mod._mask_value("abc") == "****"
    assert system_mod._mask_value("12345678") == "****"
    assert system_mod._mask_value("123456789") == "1234*6789"


def test_rotate_key_mask_long_value():
    result = system_mod._mask_value("sk-abcdefghij1234567890")
    assert result.startswith("sk-a")
    assert result.endswith("7890")
    assert "*" in result
