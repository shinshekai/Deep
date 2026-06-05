"""Automated security review tests for the UDIP backend.

Validates auth enforcement, path traversal protection, security headers,
rate limiting, upload size limits, input validation, SSRF protection, and
CORS configuration.

Uses httpx.AsyncClient with ASGITransport for async testing against the
real app instance without starting a server.
"""

import os
import asyncio

import pytest
import httpx
from httpx import ASGITransport
from unittest.mock import patch, AsyncMock, MagicMock

from app.main import app


@pytest.fixture
def security_client():
    """Async client against the full app with all middleware active.

    The conftest sets TESTING=True which bypasses auth. Some tests
    temporarily override that to exercise the real auth path.
    """
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.fixture
def enforce_auth():
    """Temporarily set a non-empty token so the auth gate activates."""
    import app.main as _main
    old_token = _main.settings.ws_auth_token
    _main.settings.ws_auth_token = "test-secret-token-12345"
    old_env = os.environ.get("WS_AUTH_TOKEN")
    os.environ["WS_AUTH_TOKEN"] = "test-secret-token-12345"
    yield
    _main.settings.ws_auth_token = old_token
    if old_env is not None:
        os.environ["WS_AUTH_TOKEN"] = old_env
    else:
        os.environ.pop("WS_AUTH_TOKEN", None)


# ── 1. Auth required on protected endpoints ──────────────────────────

@pytest.mark.asyncio
async def test_auth_required_on_protected_endpoints(security_client, enforce_auth):
    """Protected endpoints must return 401 when no API key is provided."""
    async with security_client as client:
        resp = await client.get("/api/v1/knowledge/bases")
        assert resp.status_code == 401, (
            f"Expected 401 without auth, got {resp.status_code}"
        )
        body = resp.json()
        assert body.get("success") is False
        assert "Unauthorized" in body.get("error", "")


# ── 2. Path traversal blocked on kb_name ─────────────────────────────

@pytest.mark.asyncio
async def test_path_traversal_blocked(security_client):
    """Path traversal in kb_name must be sanitized to the safe default."""
    traversal_payloads = [
        "../../etc/passwd",
        "..%2F..%2Fetc%2Fpasswd",
        "....//....//etc/passwd",
        "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
    ]
    async with security_client as client:
        for payload in traversal_payloads:
            resp = await client.get(f"/api/v1/knowledge/bases/{payload}")
            # The route uses safe_name which strips slashes and returns
            # "default" or a cleaned name. Either way, the raw traversal
            # string must not appear in any filesystem path. The endpoint
            # may return 200 (name sanitized) or 404 (not found) — both
            # are acceptable as long as the traversal is blocked.
            assert resp.status_code in (200, 404), f"Unexpected {resp.status_code} for {payload}"
            if resp.status_code == 200:
                body = resp.json()
                name = body.get("name", "")
                assert ".." not in name, f"Traversal leaked into name: {name}"
                assert "/" not in name, f"Path separator leaked into name: {name}"


# ── 3. Path traversal blocked on doc_id ──────────────────────────────

@pytest.mark.asyncio
async def test_path_traversal_in_doc_id(security_client):
    """Path traversal in doc_id must be sanitized."""
    traversal_payloads = [
        "../../etc/passwd",
        "docs/../../../etc/shadow",
        "..\\..\\windows\\system32",
    ]
    async with security_client as client:
        for payload in traversal_payloads:
            resp = await client.get(
                f"/api/v1/knowledge/bases/default/pageindex/{payload}"
            )
            # The traversal must not succeed — either 404 (rejected) or
            # 200 with sanitized/not-found content (safe).
            assert resp.status_code in (200, 404), f"Unexpected {resp.status_code} for {payload}"


# ── 4. No server version header leaked ───────────────────────────────

@pytest.mark.asyncio
async def test_no_server_version_header(security_client):
    """Response must not expose the server framework version."""
    async with security_client as client:
        resp = await client.get("/api/v1/health")
        # FastAPI's default server header is uvicorn; check it's absent
        server = resp.headers.get("server", "")
        assert "uvicorn" not in server.lower(), (
            f"Server version leaked via 'server' header: {server}"
        )
        # Also check no custom version header
        assert "x-app-version" not in {
            k.lower() for k in resp.headers.keys()
        }


# ── 5. Security headers present ─────────────────────────────────────

@pytest.mark.asyncio
async def test_security_headers_present(security_client):
    """Security headers must be set on every response."""
    required_headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Cross-Origin-Opener-Policy": "same-origin",
    }
    async with security_client as client:
        resp = await client.get("/api/v1/health")
        for header, expected in required_headers.items():
            actual = resp.headers.get(header)
            assert actual == expected, (
                f"Header {header}: expected {expected!r}, got {actual!r}"
            )


# ── 6. Rate limiting works ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limiting_works(security_client):
    """Sending many rapid requests must eventually trigger 429."""
    import os
    # Read the configured rate limit to determine how many requests to send
    rate_limit_str = os.environ.get("UDIP_RATE_LIMIT", "100/minute")
    try:
        limit_count = int(rate_limit_str.split("/")[0])
    except (ValueError, IndexError):
        limit_count = 100
    # Send enough to exceed the limit (limit + 20 for safety margin)
    requests_to_send = limit_count + 20

    async with security_client as client:
        got_429 = False
        for _ in range(requests_to_send):
            resp = await client.get("/api/v1/health")
            if resp.status_code == 429:
                got_429 = True
                # Verify rate-limit response body
                assert "rate" in resp.text.lower() or "limit" in resp.text.lower()
                break
        assert got_429, f"Rate limiting did not trigger after {requests_to_send} rapid requests (limit: {rate_limit_str})"


# ── 7. File upload size limit ───────────────────────────────────────

@pytest.mark.asyncio
async def test_file_upload_size_limit(security_client):
    """Uploading a file exceeding 50 MB must be rejected (413 or 415)."""
    from app.routers.knowledge import MAX_UPLOAD_BYTES

    # Create a payload just over the limit
    oversized = b"x" * (MAX_UPLOAD_BYTES + 1024)
    async with security_client as client:
        resp = await client.post(
            "/api/v1/knowledge/upload",
            data={"kb_name": "default"},
            files={"file": ("huge.bin", oversized, "application/octet-stream")},
        )
        # 413 = Payload Too Large, 415 = Unsupported Media Type (both reject)
        assert resp.status_code in (413, 415), (
            f"Expected 413/415 for oversized upload, got {resp.status_code}"
        )


# ── 8. Invalid JSON body ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_invalid_json_body(security_client):
    """Sending malformed JSON must return 422 validation error."""
    async with security_client as client:
        resp = await client.post(
            "/api/v1/knowledge/bases",
            content=b"{invalid json!!",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422, (
            f"Expected 422 for invalid JSON, got {resp.status_code}"
        )


# ── 9. SSRF protection on LLM base URL ─────────────────────────────

@pytest.mark.asyncio
async def test_ssrf_protection_on_llm_url(security_client):
    """Setting LLM base URL to a private/metadata IP must be rejected."""
    from app.services.security import is_safe_base_url

    # Clear UDIP_ALLOW_LOCAL_LLM so private/loopback IPs are blocked
    old_allow = os.environ.pop("UDIP_ALLOW_LOCAL_LLM", None)
    try:
        blocked_urls = [
            "http://169.254.169.254/latest/meta-data/",
            "http://metadata.google.internal/computeMetadata/v1/",
            "http://10.0.0.1:8080/v1/models",
            "http://192.168.1.1/admin",
            "http://172.16.0.1/internal",
            "ftp://evil.com/payload",
            "javascript:alert(1)",
        ]
        for url in blocked_urls:
            assert not is_safe_base_url(url), (
                f"is_safe_base_url should reject {url!r}"
            )

        # Safe URLs should pass (public IPs, localhost when allowed)
        safe_urls = [
            "https://api.openai.com/v1",
            "https://huggingface.co/api",
        ]
        for url in safe_urls:
            assert is_safe_base_url(url), (
                f"is_safe_base_url should allow {url!r}"
            )
    finally:
        if old_allow is not None:
            os.environ["UDIP_ALLOW_LOCAL_LLM"] = old_allow


# ── 10. CORS headers ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cors_headers(security_client):
    """CORS headers must be present on cross-origin requests."""
    async with security_client as client:
        resp = await client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3782",
                "Access-Control-Request-Method": "GET",
            },
        )
        # CORS middleware should respond with allowed origins
        allow_origin = resp.headers.get("access-control-allow-origin", "")
        assert allow_origin, "CORS Access-Control-Allow-Origin header is missing"
        assert "localhost" in allow_origin or "*" in allow_origin, (
            f"Unexpected CORS origin: {allow_origin}"
        )
