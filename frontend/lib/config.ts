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
 * Environment variable naming:
 *   - ``WS_AUTH_TOKEN`` (preferred, server-side only — no ``NEXT_PUBLIC_`` prefix)
 *   - ``NEXT_PUBLIC_WS_AUTH_TOKEN`` (legacy fallback, still honored for
 *     backward compatibility with existing deployments — but exposes
 *     the token in the build output, so migrate to ``WS_AUTH_TOKEN``)
 *
 * Migrate existing deployments by setting ``WS_AUTH_TOKEN`` in
 * ``frontend/.env.local`` (no rebuild of the client bundle required
 * since the value is read at request time).
 */
let _cachedToken: string | null = null;
let _tokenFetchPromise: Promise<string | null> | null = null;

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
 */
export async function secureFetch(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Response> {
  const urlString = typeof input === "string" ? input : (input instanceof URL ? input.toString() : input.url);

  if (urlString.includes("localhost:8001") || urlString.includes("127.0.0.1:8001") || !urlString.startsWith("http")) {
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
