/**
 * Storefront Runner client.
 * Talks to the host "Storefront Runner" service (separate from the main API at :8000),
 * which manages each store's Shopify CLI Liquid theme in stores/shopify/*:
 *   pull (live theme) · run (`shopify theme dev`) · deploy (`shopify theme push`).
 * The runner fetches per-store Shopify credentials server-to-server from the API,
 * so the browser never handles the admin token.
 */

const RUNNER = 'http://localhost:8788';

export interface StorefrontStatus {
  store_id: string;
  slug: string;
  scaffolded: boolean; // true once the theme has been pulled locally
  running: boolean;
  port: number | null;
  url: string | null;
}

export interface RunResult {
  url: string;
  port: number;
  running: boolean;
  editor_url?: string;
}

export interface DeployResult {
  ok: boolean;
  output: string;
  url?: string;
  theme_id?: number | null;
  published?: boolean;
}

const OFFLINE = 'Storefront runner not running — start it with: make storefront';

/** Thrown by runStorefront() when the store has no Theme Access password yet (needed for `theme dev`). */
export const NEEDS_THEME_PASSWORD = 'NEEDS_THEME_PASSWORD';

async function runnerFetch(path: string, options: RequestInit = {}): Promise<Response> {
  try {
    return await fetch(`${RUNNER}${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...options.headers },
    });
  } catch {
    throw new Error(OFFLINE);
  }
}

export async function listStorefronts(): Promise<StorefrontStatus[]> {
  const res = await runnerFetch('/storefronts');
  if (!res.ok) throw new Error(`GET /storefronts → ${res.status}`);
  return res.json() as Promise<StorefrontStatus[]>;
}

/** Start `shopify theme dev` for a store (pulls the live theme first if needed). */
export async function runStorefront(
  store_id: string,
  slug: string,
  forcePull = false,
): Promise<RunResult> {
  const res = await runnerFetch(`/storefronts/${store_id}/run`, {
    method: 'POST',
    body: JSON.stringify({ slug, force_pull: forcePull }),
  });
  if (!res.ok) {
    const detail = await res.text();
    if (res.status === 400 && /Theme Access password/i.test(detail)) {
      throw new Error(NEEDS_THEME_PASSWORD);
    }
    throw new Error(`Run failed → ${res.status}: ${detail}`);
  }
  return res.json() as Promise<RunResult>;
}

export async function stopStorefront(store_id: string): Promise<{ running: boolean }> {
  const res = await runnerFetch(`/storefronts/${store_id}/stop`, { method: 'POST' });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Stop failed → ${res.status}: ${detail}`);
  }
  return res.json() as Promise<{ running: boolean }>;
}

/** Upload local theme changes to Shopify via `shopify theme push`.
 *  publish=false → new unpublished theme (safe); publish=true → push to the live theme. */
export async function deployStorefront(
  store_id: string,
  slug: string,
  publish = false,
): Promise<DeployResult> {
  const res = await runnerFetch(`/storefronts/${store_id}/deploy`, {
    method: 'POST',
    body: JSON.stringify({ slug, publish }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Deploy failed → ${res.status}: ${detail}`);
  }
  return res.json() as Promise<DeployResult>;
}
