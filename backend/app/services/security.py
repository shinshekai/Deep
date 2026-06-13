"""Security utilities — path sanitization, URL validation, constant-time comparison."""

import hmac
import ipaddress
import logging
import re
import secrets
import socket
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ── Path sanitization ────────────────────────────────────────────────

# Whitelist for kb_name / session_id: letters, digits, underscore, hyphen, dot
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]")
# Doc ids allow dots (file extensions are part of the original name).
# A leading dot is still rejected to avoid ``.hidden`` traversal tricks.
_SAFE_DOC_RE = re.compile(r"[^A-Za-z0-9._-]")
# Reserved names we never allow (Windows + Unix)
_RESERVED_NAMES = frozenset(
    {
        "",
        ".",
        "..",
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)


def safe_name(value: str, default: str = "default", max_len: int = 128) -> str:
    """Sanitize a name (KB name, session id) to safe path characters.

    - Strips directory separators, null bytes, control chars
    - Rejects reserved names that could escape the data directory
    - Truncates to ``max_len`` to prevent path-length attacks
    """
    if not isinstance(value, str):
        return default
    # Reject anything that contains a path separator or null byte up
    # front — these can never be sanitized into a safe value.
    if "/" in value or "\\" in value or "\x00" in value:
        return default
    cleaned = _SAFE_NAME_RE.sub("_", value).strip("._-")
    if not cleaned or cleaned in _RESERVED_NAMES:
        return default
    if cleaned.startswith("."):
        return default
    return cleaned[:max_len]


def safe_doc_id(value: str, default: str = "doc", max_len: int = 200) -> str:
    """Sanitize a document id (more restrictive than kb_name).

    Returns just the basename — no path components — and rejects empty,
    reserved, or path-traversal values.
    """
    if not isinstance(value, str):
        return default
    # Reject path separators and null bytes up front, before
    # normalization, so an attacker cannot smuggle in traversal via
    # characters the regex would otherwise strip.
    if "/" in value or "\\" in value or "\x00" in value:
        return default
    # Pull only the basename to drop any path components
    basename = Path(value).name
    if basename.startswith("."):
        return default
    cleaned = _SAFE_DOC_RE.sub("_", basename).strip("._-")
    if not cleaned or cleaned in _RESERVED_NAMES or cleaned.startswith("."):
        return default
    return cleaned[:max_len]


def resolve_within(base: Path, target: Path) -> Path:
    """Resolve ``target`` and ensure it lives inside ``base``.

    Raises ``ValueError`` on path traversal. Returns the resolved path.
    """
    base_resolved = base.resolve()
    target_resolved = target.resolve()
    try:
        target_resolved.relative_to(base_resolved)
    except ValueError as e:
        raise ValueError(f"Path escapes base directory: {target}") from e
    return target_resolved


# ── Constant-time token comparison ───────────────────────────────────


def safe_compare(provided: str | None, expected: str | None) -> bool:
    """Constant-time string comparison to prevent timing attacks.

    Returns ``False`` for missing, empty, or mismatched values without
    leaking length information. Always runs compare_digest even when
    ``provided`` is None to avoid a distinguishable early-return timing
    difference between "no token" and "wrong token".
    """
    if not expected:
        return False
    return hmac.compare_digest(provided or "", expected)


# ── Token generation ────────────────────────────────────────────────


def generate_auth_token(nbytes: int = 32) -> str:
    """Generate a cryptographically random auth token (URL-safe)."""
    return secrets.token_urlsafe(nbytes)


# ── SSRF protection on URLs ─────────────────────────────────────────


def is_safe_base_url(url: str) -> bool:
    """Validate that a URL is safe to use as an LLM/embedding base URL.

    Blocks:
    - Non-HTTP(S) schemes
    - Loopback addresses (127.0.0.0/8, ::1) — only via opt-in flag
    - Private / link-local / cloud metadata ranges
    - AWS / GCP metadata endpoints

    Loopback is allowed by default since LM Studio and Ollama run locally;
    external attackers must not be able to redirect LLM traffic off-box.
    """
    if not isinstance(url, str) or not url:
        return False
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.hostname:
        return False

    hostname = parsed.hostname.lower()

    # Explicit block list — these are never safe regardless of resolution
    blocked_hosts = {
        "169.254.169.254",  # AWS / GCP / Azure instance metadata
        "metadata.google.internal",
        "metadata.azure.com",
        "0.0.0.0",
    }
    if hostname in blocked_hosts:
        return False

    # Resolve hostname and check the resolved IP — defeats DNS rebinding
    # to private ranges when the attacker controls DNS for a public host.
    try:
        infos = socket.getaddrinfo(hostname, parsed.port or 80)
    except socket.gaierror:
        return False

    for info in infos:
        sockaddr = info[4]
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False

        # Private, loopback, link-local, multicast, reserved, and
        # unspecified addresses are all blocked unless the operator has
        # opted in to local inference via ``UDIP_ALLOW_LOCAL_LLM=1``.
        # Note: in Python's ipaddress module, ``::1`` reports both
        # ``is_loopback`` and ``is_reserved`` as True, so the reserved
        # check must also be gated on ``allow_local`` to permit IPv6
        # loopback.
        import os

        allow_local = os.environ.get("UDIP_ALLOW_LOCAL_LLM", "").lower() in ("1", "true", "yes")
        if not allow_local:
            if (
                ip.is_loopback
                or ip.is_private
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                return False
        else:
            # Even with local-allow set, block cloud metadata endpoints
            # by checking for link-local/unspecified on their own.
            if ip.is_link_local or ip.is_multicast or ip.is_unspecified:
                return False

    return True


def is_safe_path_segment(segment: str) -> bool:
    """Quick check whether a path segment is safe (no traversal)."""
    if not segment or segment in _RESERVED_NAMES:
        return False
    if "/" in segment or "\\" in segment:
        return False
    if segment.startswith("."):
        return False
    return "\x00" not in segment


# ── Device id validation ─────────────────────────────────────────
#
# Device ids are client-generated UUID v4 values (``crypto.randomUUID()``
# on the frontend, ``uuid.uuid4()`` on the solve WebSocket). Memory is
# scoped per device id, so accepting arbitrary strings would let a caller
# read or modify another device's data by guessing/enumerating ids, and
# would allow non-UUID values to be used as path/query keys. Validating
# the UUID shape rejects those inputs without changing the device-identity
# model.

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def is_valid_device_id(value: str) -> bool:
    """Return True iff ``value`` is a canonical UUID string."""
    return isinstance(value, str) and bool(_UUID_RE.match(value))

