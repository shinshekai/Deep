export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1";
export const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8001";

/**
 * Frontend auth token — sourced at runtime from a server-side ticket endpoint.
 *
 * The token is never inlined into the client bundle. The client calls
 * ``/api/auth/ws-ticket`` (a Next.js Route Handler) which reads the
 * server-only ``WS_AUTH_TOKEN`` env var and returns it as a one-time
 * value. The response is cached in memory for the lifetime of the page.
 *
 * Environment variable:
 *   - ``WS_AUTH_TOKEN`` (server-side only — no ``NEXT_PUBLIC_`` prefix)
 */
let _cachedToken: string | null = null;
let _tokenFetchPromise: Promise<string> | null = null;

export async function getWsAuthToken(): Promise<string> {
  if (_cachedToken) return _cachedToken;
  if (_tokenFetchPromise) return _tokenFetchPromise;
  _tokenFetchPromise = (async () => {
    try {
      const res = await fetch("/api/auth/ws-ticket", { cache: "no-store" });
      if (!res.ok) return "";
      const data = (await res.json()) as { token?: string };
      _cachedToken = data.token || "";
      return _cachedToken;
    } catch {
      return "";
    } finally {
      _tokenFetchPromise = null;
    }
  })();
  return _tokenFetchPromise;
}

/**
 * A secure wrapper around fetch that automatically appends the local API secret key
 * in the X-DEEP-API-KEY header to authorize requests against the backend.
 *
 * A request is considered "to the backend" (and therefore gets the auth
 * header) when it is either a relative URL or its origin matches the
 * configured API/WS origin. This replaces a previous hardcoded
 * ``localhost:8001`` check that silently dropped the auth header on any
 * non-localhost deployment, causing 401s.
 */
function _backendOrigins(): string[] {
  const origins = new Set<string>();
  // localhost defaults remain trusted for local dev even when the env
  // points elsewhere.
  origins.add("http://localhost:8001");
  origins.add("http://127.0.0.1:8001");
  for (const base of [API_BASE_URL, WS_BASE_URL]) {
    try {
      // new URL() accepts ws:// and wss:// too; normalize to the origin.
      const u = new URL(base);
      origins.add(`${u.protocol}//${u.host}`);
      // Also add the http(s) equivalent of ws(s) origins so an API call
      // over http to the same host:port is recognized.
      if (u.protocol === "ws:") origins.add(`http://${u.host}`);
      if (u.protocol === "wss:") origins.add(`https://${u.host}`);
    } catch {
      // Ignore unparseable base URLs.
    }
  }
  return Array.from(origins);
}

function _isBackendRequest(urlString: string): boolean {
  // Relative URLs (no scheme) are same-origin requests to the app/back end.
  if (!urlString.startsWith("http")) return true;
  try {
    const reqOrigin = new URL(urlString).origin;
    return _backendOrigins().includes(reqOrigin);
  } catch {
    return false;
  }
}

export async function secureFetch(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Response> {
  const urlString = typeof input === "string" ? input : (input instanceof URL ? input.toString() : input.url);

  if (_isBackendRequest(urlString)) {
    const headers = new Headers(init?.headers);
    if (!headers.has("X-DEEP-API-KEY")) {
      const token = await getWsAuthToken();
      if (token) {
        headers.set("X-DEEP-API-KEY", token);
      }
    }
    return fetch(input, {
      ...init,
      headers,
    });
  }

  return fetch(input, init);
}
