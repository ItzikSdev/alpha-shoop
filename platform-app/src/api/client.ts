/**
 * Alpha Shoop API client.
 * Automatically fetches and caches a JWT token from POST /api/v1/auth/token,
 * then injects it as Authorization: Bearer <token> on every request.
 */

const BASE = 'http://localhost:8000/api/v1';
const TOKEN_KEY = 'alpha_shoop_token';
const TOKEN_EXP_KEY = 'alpha_shoop_token_exp';

// ── Token management ──────────────────────────────────────────────────────────

async function fetchFreshToken(operator = 'dev-operator'): Promise<string> {
  const res = await fetch(`${BASE}/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator }),
  });
  if (!res.ok) throw new Error(`Auth failed: ${res.status}`);
  const data = await res.json();
  const token: string = data.access_token;
  const expiresAt = Date.now() + data.expires_in * 1000 - 30_000; // 30s early refresh
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(TOKEN_EXP_KEY, String(expiresAt));
  return token;
}

export async function getToken(operator = 'dev-operator'): Promise<string> {
  const stored = localStorage.getItem(TOKEN_KEY);
  const exp = Number(localStorage.getItem(TOKEN_EXP_KEY) ?? 0);
  if (stored && exp > Date.now()) return stored;
  return fetchFreshToken(operator);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(TOKEN_EXP_KEY);
}

// ── Authenticated fetch ───────────────────────────────────────────────────────

export async function apiFetch(
  path: string,
  options: RequestInit = {},
  operator = 'dev-operator',
): Promise<Response> {
  const token = await getToken(operator);
  return fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
      Authorization: `Bearer ${token}`,
    },
  });
}

// ── Convenience helpers ───────────────────────────────────────────────────────

export async function apiGet<T>(path: string): Promise<T> {
  const res = await apiFetch(path);
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await apiFetch(path, { method: 'POST', body: JSON.stringify(body) });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`POST ${path} → ${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const res = await apiFetch(path, { method: 'PATCH', body: JSON.stringify(body) });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`PATCH ${path} → ${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}
