/**
 * Resolves once an ACTIVATED Service Worker registration exists for the
 * /replay/ scope — checked explicitly by scope, not inferred from the
 * current page's own relationship to any worker.
 *
 * Regression history (2026-08-02 → 2026-08-03), three attempts before this
 * one:
 *   1. Waited for 'controllerchange' with a 4s fallback. Wrong on two
 *      counts: a page loaded before the SW existed never gets a controller
 *      unless the SW calls clients.claim() (RWP's sw.js doesn't), so the
 *      fallback did all the work; and 4s was a guess — sw.js is 1.2MB and
 *      sometimes takes longer, so the race just got rarer, not gone.
 *   2. Switched to `navigator.serviceWorker.ready`. Looked right (it
 *      resolves once an active worker exists "for the page"), but that
 *      guarantee is SCOPE-RELATIVE: it's about a worker covering the
 *      CURRENT document's own URL. Every page that needs this check
 *      (/documents/[id]/, /admin/documents/[id]/, /replay-loading/) lives
 *      OUTSIDE the /replay/ scope the worker actually registers for, so
 *      `ready` had no real registration to resolve against and either hung
 *      or resolved on unrelated grounds — in practice, the visible "fix"
 *      was really just the 15s fallback timer again, which is why the
 *      original embedded-box 404 could still recur (confirmed directly:
 *      reported again by a real user after this "fix" shipped).
 *   3. A server-side fallback page for unmatched /replay/* requests, which
 *      made things worse by intercepting ReplayWeb.page's own internal
 *      /replay/w/... API calls (meant to be answered entirely inside the
 *      SW, never reaching a server).
 *
 * This is what actually closed the gap for the "open full page" link (5/5
 * clean runs in a fresh browser session): poll `getRegistration()` for the
 * EXACT /replay/ scope — registration state is per-origin, so this works
 * from any page regardless of that page's own scope relationship — until
 * `.active.state === 'activated'`. Used both here (gating the embedded
 * <replay-web-page> element) and by /replay-loading (gating the redirect
 * after "open full page" is clicked), so both call sites share the one
 * proven-correct check instead of two independent guesses.
 */
export async function waitForReplayServiceWorkerActive(): Promise<void> {
  if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) return;
  const scopeUrl = new URL('/replay/', window.location.origin).href;
  // eslint-disable-next-line no-constant-condition
  while (true) {
    const reg = await navigator.serviceWorker.getRegistration(scopeUrl);
    if (reg && reg.active && reg.active.state === 'activated') return;
    await new Promise((r) => setTimeout(r, 200));
  }
}

export const getApiBaseUrl = (): string => {
  // Explicit configuration takes precedence for isolated demos and test
  // deployments where the frontend and API intentionally use different
  // ports/origins.  The value is baked into the client bundle by Next.js.
  const configuredApiUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '');
  // A loopback URL is valid only from the machine that runs Next.js.  Never
  // send it to a browser opened through a remote workspace/tunnel: there it
  // points at the visitor's own computer and produces a generic "Failed to
  // fetch" error.  Local development ports below derive the visible hostname.
  const isLoopbackApi = configuredApiUrl && /^https?:\/\/(localhost|127\.0\.0\.1|\[::1\])(?::|\/|$)/i.test(configuredApiUrl);
  if (configuredApiUrl && !isLoopbackApi) return configuredApiUrl;

  if (typeof window !== 'undefined') {
    // Direct dev-server access (e.g. http://host:3000) still talks straight
    // to the backend's own port, same as before. Anything else (e.g.
    // https://host/ through an nginx reverse proxy — see
    // scratchpad/fewa-nginx.conf) is assumed to proxy /api/ to the backend
    // on the SAME origin, so a relative path is used instead: an absolute
    // http://host:8000 URL from an https:// page gets blocked by the
    // browser as mixed content, regardless of CORS (CORS is checked after
    // the browser's own protocol-based mixed-content gate, so allow_origins
    // being wide open doesn't help here).
    if (window.location.port === '3000' || window.location.port === '3001') {
      const hostname = window.location.hostname || 'localhost';
      const backendPort = window.location.port === '3001' ? '8001' : '8000';
      return `${window.location.protocol}//${hostname}:${backendPort}`;
    }
    // window.location.origin, NOT '' — callers do `new URL(...)` on this,
    // and new URL() throws a TypeError on a relative path with no base,
    // which silently turned into "no results" on the search page.
    return window.location.origin;
  }
  return 'http://localhost:8000';
};

let refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem('fewa_refresh_token');
  if (!refreshToken) return null;

  try {
    const res = await fetch(`${getApiBaseUrl()}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    localStorage.setItem('fewa_access_token', data.access_token);
    localStorage.setItem('fewa_refresh_token', data.refresh_token);
    localStorage.setItem('fewa_user', JSON.stringify(data.user));
    return data.access_token;
  } catch {
    return null;
  }
}

/**
 * fetch() wrapper for admin API calls: attaches the stored access token,
 * and on a 401 (expired access token — real JWTs expire after
 * JWT_ACCESS_TOKEN_EXPIRE_MINUTES, currently 60 min) transparently uses the
 * real refresh token to get a new one and retries once, instead of the
 * caller just seeing a failed request and an empty/error UI state.
 */
export async function fetchWithAuth(path: string, options: RequestInit = {}): Promise<Response> {
  const doFetch = (token: string | null) =>
    fetch(`${getApiBaseUrl()}${path}`, {
      ...options,
      headers: {
        ...(options.headers || {}),
        Authorization: `Bearer ${token || ''}`,
      },
    });

  const token = localStorage.getItem('fewa_access_token');
  const res = await doFetch(token);
  if (res.status !== 401) return res;

  if (!refreshInFlight) {
    refreshInFlight = refreshAccessToken().finally(() => {
      refreshInFlight = null;
    });
  }
  const newToken = await refreshInFlight;

  if (!newToken) {
    localStorage.removeItem('fewa_access_token');
    localStorage.removeItem('fewa_refresh_token');
    localStorage.removeItem('fewa_user');
    if (typeof window !== 'undefined') window.location.href = '/admin/login';
    return res;
  }

  return doFetch(newToken);
}
