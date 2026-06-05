export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1";
export const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8001";

/**
 * Frontend auth token — sourced from a build-time env var.
 *
 * The previous default (``"udip-secret-token"``) was hardcoded into every
 * client bundle and was equivalent to publishing credentials publicly.
 * We now require ``NEXT_PUBLIC_WS_AUTH_TOKEN`` to be set in
 * ``frontend/.env.local`` before ``next build`` / ``next dev``. If the
 * env var is missing we send no token at all; the backend will respond
 * 401 and the UI will surface a real error to the operator instead of
 * silently using a known public credential.
 */
export const WS_AUTH_TOKEN = process.env.NEXT_PUBLIC_WS_AUTH_TOKEN || "";

/**
 * A secure wrapper around fetch that automatically appends the local API secret key
 * in the X-DEEP-API-KEY header to authorize requests against the backend.
 */
export async function secureFetch(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Response> {
  const urlString = typeof input === "string" ? input : (input instanceof URL ? input.toString() : input.url);

  // Only inject authentication headers for calls targeted at the local UDIP backend
  if (urlString.includes("localhost:8001") || urlString.includes("127.0.0.1:8001") || !urlString.startsWith("http")) {
    const headers = new Headers(init?.headers);
    if (WS_AUTH_TOKEN && !headers.has("X-DEEP-API-KEY")) {
      headers.set("X-DEEP-API-KEY", WS_AUTH_TOKEN);
    }
    return fetch(input, {
      ...init,
      headers,
    });
  }

  return fetch(input, init);
}
