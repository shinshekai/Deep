"""OS keyring wrapper for API key storage.

Provider API keys are stored in the platform's native secret store
(Windows Credential Manager, macOS Keychain, libsecret on Linux) rather
than in plaintext ``.env`` files. The keyring backend is selected
automatically by the ``keyring`` package; if no functional backend is
available (e.g. headless CI runner without DBus) we fall back to
``os.environ`` and emit a single warning.

Service name is fixed to ``"udip"``; the *username* is the env-var name
itself (``OPENAI_API_KEY``, ``MISTRAL_API_KEY``, etc.). This keeps the
mapping obvious for operators debugging with their platform's credential
manager.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

KEYRING_SERVICE = "udip"
_FALLBACK_WARNED = False


@lru_cache(maxsize=1)
def is_keyring_available() -> bool:
    """Return True if a working keyring backend can be used.

    A no-op set+get+delete roundtrip is performed against the
    ``keyring`` library's currently configured backend. If any step
    raises, the backend is considered unavailable and we silently
    fall back to ``os.environ``.
    """
    if os.environ.get("CI") or os.environ.get("HEADLESS"):
        return False
    try:
        import keyring  # type: ignore
        from keyring.errors import KeyringError  # type: ignore

        backend = keyring.get_keyring()
        # Fail fast on known no-op backends that the library picks
        # when nothing better is available (e.g. headless Linux).
        if backend.__class__.__name__ in {"Fail", "NullKeyring"}:
            return False
        # Probe with a unique value to confirm the backend actually
        # persists (some headless setups report a backend but throw on use).
        probe_service = f"{KEYRING_SERVICE}__probe"
        probe_user = "__probe__"
        try:
            keyring.set_password(probe_service, probe_user, "ok")
            got = keyring.get_password(probe_service, probe_user)
            try:
                keyring.delete_password(probe_service, probe_user)
            except KeyringError:
                pass
            return got == "ok"
        except (KeyringError, Exception):
            return False
    except Exception:
        return False


def get_secret(env_name: str) -> str:
    """Resolve a secret by its canonical environment-variable name.

    Lookup order:
        1. OS keyring (if available and entry exists)
        2. ``os.environ``

    Returns the empty string when neither source has a value.
    """
    if is_keyring_available():
        try:
            import keyring  # type: ignore
            from keyring.errors import KeyringError  # type: ignore

            value = keyring.get_password(KEYRING_SERVICE, env_name)
            if value:
                return value
        except (KeyringError, Exception) as exc:  # pragma: no cover
            logger.debug("keyring get failed for %s: %s", env_name, exc)
    return os.environ.get(env_name, "")


def set_secret(env_name: str, value: str) -> None:
    """Persist a secret in the OS keyring.

    Raises ``RuntimeError`` if no functional keyring backend is available.
    Callers should either surface a clear error to the operator or fall
    back to environment variables (e.g. for headless deployments).
    """
    if not is_keyring_available():
        raise RuntimeError(
            "OS keyring is not available on this system. "
            "Set the API key via environment variable "
            f"({env_name}=...) or install a keyring backend "
            "(libsecret on Linux, Keychain Access on macOS, "
            "or Windows Credential Manager — usually preinstalled)."
        )
    try:
        import keyring  # type: ignore

        keyring.set_password(KEYRING_SERVICE, env_name, value)
    except Exception as exc:
        raise RuntimeError(f"Failed to write secret to keyring: {exc}") from exc


def delete_secret(env_name: str) -> bool:
    """Remove a secret from the keyring. Idempotent — missing entries are fine.

    Returns True if a value was actually removed, False otherwise.
    """
    if not is_keyring_available():
        return False
    try:
        import keyring  # type: ignore
        from keyring.errors import KeyringError, PasswordDeleteError  # type: ignore

        try:
            keyring.delete_password(KEYRING_SERVICE, env_name)
            return True
        except PasswordDeleteError:
            return False
    except (KeyringError, Exception) as exc:  # pragma: no cover
        logger.debug("keyring delete failed for %s: %s", env_name, exc)
        return False


def warn_fallback_once(reason: str) -> None:
    """Emit a one-time warning when falling back to env-var storage.

    Operators should not see this flood the log; we suppress repeats.
    """
    global _FALLBACK_WARNED
    if _FALLBACK_WARNED:
        return
    _FALLBACK_WARNED = True
    logger.warning(
        "secrets: OS keyring unavailable (%s); provider API keys will be "
        "read from environment variables only. New keys cannot be stored "
        "via the provider config endpoint until a keyring backend is "
        "available. See docs/security.md for setup instructions.",
        reason,
    )
