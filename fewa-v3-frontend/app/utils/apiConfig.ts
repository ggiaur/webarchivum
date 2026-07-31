export const getApiBaseUrl = (): string => {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname || 'localhost';
    return `http://${hostname}:8000`;
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
