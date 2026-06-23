import { useEffect, useRef, useState } from 'react';
import { apiGet, apiPost, apiPatch } from '../api/client';
import {
  listStorefronts,
  runStorefront,
  stopStorefront,
  deployStorefront,
  NEEDS_THEME_PASSWORD,
  type StorefrontStatus,
} from '../api/storefrontClient';

interface Store {
  store_id: string;
  name: string;
  shopify_domain: string;
  platform: string;
  niche: string;
  description: string;
  active: boolean;
  created_at: string;
  has_brand: boolean;
  store_name: string;
  installed_theme: string;
  has_payplus: boolean;
  has_theme_password?: boolean; // Theme Access password saved (needed for `shopify theme dev`)
  storefront_slug?: string;
}

/** Derive a slug client-side from a myshopify domain handle. */
function slugFromDomain(domain: string): string {
  return (domain || '').replace(/\.myshopify\.com$/i, '').trim();
}

const EMPTY_FORM = {
  name: '', shopify_domain: '', shopify_access_token: '', niche: '', description: '',
  payplus_api_key: '', payplus_secret: '',
};

export function StoresPage() {
  const [stores, setStores] = useState<Store[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(EMPTY_FORM);
  const [adding, setAdding] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [editingDescId, setEditingDescId] = useState<string | null>(null);
  const [descDraft, setDescDraft] = useState('');
  const [savingDesc, setSavingDesc] = useState(false);

  // ── Storefront runner state ──────────────────────────────────────────────
  const [storefronts, setStorefronts] = useState<Record<string, StorefrontStatus>>({});
  const [runnerOffline, setRunnerOffline] = useState(false);
  const [runningId, setRunningId] = useState<string | null>(null); // provision+run in progress
  const [stoppingId, setStoppingId] = useState<string | null>(null);
  const [deployingId, setDeployingId] = useState<string | null>(null);
  const [tokenInputId, setTokenInputId] = useState<string | null>(null);
  const [tokenDraft, setTokenDraft] = useState('');
  const [savingToken, setSavingToken] = useState(false);
  const [deployResult, setDeployResult] = useState<Record<string, { ok: boolean; output: string; url?: string }>>({});
  const localToken = useRef<Record<string, string>>({}); // token VALUES saved this session

  async function pollStorefronts() {
    try {
      const list = await listStorefronts();
      const map: Record<string, StorefrontStatus> = {};
      for (const s of list) map[s.store_id] = s;
      setStorefronts(map);
      setRunnerOffline(false);
    } catch {
      setRunnerOffline(true);
    }
  }

  useEffect(() => {
    pollStorefronts();
    const id = setInterval(pollStorefronts, 4000);
    return () => clearInterval(id);
  }, []);

  function slugFor(store: Store): string {
    return storefronts[store.store_id]?.slug || store.storefront_slug || slugFromDomain(store.shopify_domain);
  }

  /** Start `shopify theme dev` locally; prompt for a Theme Access password if missing. */
  async function handleRunLocal(store: Store) {
    setRunningId(store.store_id);
    setError('');
    try {
      const result = await runStorefront(store.store_id, slugFor(store));
      window.open(result.url, '_blank', 'noopener,noreferrer');
      await pollStorefronts();
    } catch (err: unknown) {
      if (err instanceof Error && err.message === NEEDS_THEME_PASSWORD) {
        // Reveal the inline input to capture the Theme Access password, then it retries.
        setTokenInputId(store.store_id);
        setTokenDraft('');
      } else {
        setError(err instanceof Error ? err.message : 'Failed to start local theme dev');
      }
    } finally {
      setRunningId(null);
    }
  }

  async function handleStopLocal(store: Store) {
    setStoppingId(store.store_id);
    try {
      await stopStorefront(store.store_id);
      await pollStorefronts();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to stop theme dev');
    } finally {
      setStoppingId(null);
    }
  }

  /** Save the Theme Access password (needed for `theme dev`), then start it. */
  async function handleSaveToken(store: Store) {
    setSavingToken(true);
    setError('');
    try {
      await apiPatch(`/stores/${store.store_id}`, { theme_access_password: tokenDraft });
      localToken.current[store.store_id] = tokenDraft;
      setTokenInputId(null);
      setTokenDraft('');
      await loadStores();
      await handleRunLocal(store);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save Theme Access password');
    } finally {
      setSavingToken(false);
    }
  }

  /** Upload local theme changes to Shopify via `shopify theme push` (admin token — no extra cred). */
  async function handleUploadToShopify(store: Store, publish = false) {
    setDeployingId(store.store_id);
    setError('');
    setDeployResult(prev => ({ ...prev, [store.store_id]: { ok: false, output: 'Pushing to Shopify…' } }));
    try {
      const result = await deployStorefront(store.store_id, slugFor(store), publish);
      setDeployResult(prev => ({ ...prev, [store.store_id]: result }));
      if (result.ok && result.url) {
        window.open(result.url, '_blank', 'noopener,noreferrer');
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Push failed';
      setDeployResult(prev => ({ ...prev, [store.store_id]: { ok: false, output: msg } }));
    } finally {
      setDeployingId(null);
    }
  }

  async function loadStores() {
    setLoading(true);
    try {
      const data = await apiGet('/stores');
      setStores(Array.isArray(data) ? data : []);
    } catch {
      setError('Failed to load stores. Is the API running?');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadStores(); }, []);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name || !form.shopify_domain || !form.shopify_access_token) {
      setError('Name, domain, and access token are required.');
      return;
    }
    setAdding(true);
    setError('');
    try {
      await apiPost('/stores', form);
      setForm(EMPTY_FORM);
      setShowForm(false);
      await loadStores();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to add store');
    } finally {
      setAdding(false);
    }
  }

  async function handleSaveDescription(store_id: string) {
    setSavingDesc(true);
    try {
      await apiPatch(`/stores/${store_id}`, { description: descDraft });
      setEditingDescId(null);
      await loadStores();
    } catch {
      setError('Failed to save description');
    } finally {
      setSavingDesc(false);
    }
  }

  async function handleDelete(store_id: string) {
    setDeleteId(store_id);
    try {
      const res = await fetch(`http://localhost:8000/api/v1/stores/${store_id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Delete failed');
      await loadStores();
    } catch {
      setError('Failed to delete store');
    } finally {
      setDeleteId(null);
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">My Stores</h1>
          <p className="text-gray-400 text-sm mt-1">
            Configure Shopify stores for multi-store agent runs. Each store has its own credentials,
            niche, and brand brief — agents target the selected store automatically.
          </p>
        </div>
        <button
          onClick={() => { setShowForm(!showForm); setError(''); }}
          className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors"
        >
          {showForm ? 'Cancel' : '+ Add Store'}
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mb-4 px-4 py-3 rounded-lg bg-red-900/40 border border-red-700 text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* Storefront runner offline notice */}
      {runnerOffline && (
        <div className="mb-4 px-4 py-2 rounded-lg bg-amber-900/20 border border-amber-800/60 text-amber-400/90 text-xs">
          Local storefront runner offline — run <code className="font-mono bg-gray-800 px-1.5 py-0.5 rounded">make storefront</code>
        </div>
      )}

      {/* Add store form */}
      {showForm && (
        <form
          onSubmit={handleAdd}
          className="mb-6 p-5 rounded-xl bg-gray-900 border border-gray-700 space-y-4"
        >
          <h2 className="text-white font-semibold text-base">Add a new store</h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Display name *</label>
              <input
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                placeholder="My Jewelry Store"
                value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Shopify domain *</label>
              <input
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                placeholder="mystore.myshopify.com"
                value={form.shopify_domain}
                onChange={e => setForm({ ...form, shopify_domain: e.target.value })}
              />
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Shopify access token *</label>
            <input
              type="password"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 font-mono"
              placeholder="shpat_..."
              value={form.shopify_access_token}
              onChange={e => setForm({ ...form, shopify_access_token: e.target.value })}
            />
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Niche / product category
              <span className="ml-2 text-gray-500">(optional — agents will discover it if blank)</span>
            </label>
            <input
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
              placeholder="silver women rings"
              value={form.niche}
              onChange={e => setForm({ ...form, niche: e.target.value })}
            />
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Store description
              <span className="ml-2 text-gray-500">(what it contains today + what it should become — embedded for agentic RAG)</span>
            </label>
            <textarea
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 min-h-[90px]"
              placeholder="e.g. Currently carries 4 generic baby romper styles. Should expand into separate Boys and Girls collections, each with onesies, sleepwear, and outerwear. Target: organic-certified fabrics only, premium D2C positioning."
              value={form.description}
              onChange={e => setForm({ ...form, description: e.target.value })}
            />
          </div>

          <div className="border-t border-gray-700 pt-3">
            <div className="text-xs text-gray-400 font-medium mb-2">
              PayPlus — תשלום ישראלי (Apple Pay / Google Pay / כרטיס)
              <a href="https://www.payplus.co.il/shopify" target="_blank" rel="noopener noreferrer"
                className="ml-2 text-teal-400 hover:underline">הגדרת PayPlus ↗</a>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">PayPlus API Key</label>
                <input
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-teal-500 font-mono"
                  placeholder="Optional — add after setup"
                  value={form.payplus_api_key}
                  onChange={e => setForm({ ...form, payplus_api_key: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">PayPlus Secret Key</label>
                <input
                  type="password"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-teal-500 font-mono"
                  placeholder="Optional — add after setup"
                  value={form.payplus_secret}
                  onChange={e => setForm({ ...form, payplus_secret: e.target.value })}
                />
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-1">
            <button
              type="button"
              onClick={() => { setShowForm(false); setError(''); }}
              className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-gray-200 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={adding}
              className="px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium transition-colors"
            >
              {adding ? 'Adding...' : 'Add Store'}
            </button>
          </div>
        </form>
      )}

      {/* Store list */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading stores...</div>
      ) : stores.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <div className="text-4xl mb-3">🏪</div>
          <div className="text-base font-medium text-gray-400">No stores configured yet</div>
          <div className="text-sm mt-1">Add a store above to enable multi-store agent runs</div>
        </div>
      ) : (
        <div className="space-y-3">
          {stores.map(store => (
            <div
              key={store.store_id}
              className="p-5 rounded-xl bg-gray-900 border border-gray-800 hover:border-gray-700 transition-colors"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-1">
                    <span className="font-semibold text-white">{store.name}</span>
                    <span className="px-2 py-0.5 rounded text-xs bg-teal-900/40 text-teal-400 border border-teal-800 font-mono">
                      {store.platform}
                    </span>
                    {store.has_brand && (
                      <span className="px-2 py-0.5 rounded text-xs bg-indigo-900/60 text-indigo-300 border border-indigo-800">
                        Brand ready
                      </span>
                    )}
                    {store.active ? (
                      <span className="px-2 py-0.5 rounded text-xs bg-emerald-900/40 text-emerald-400 border border-emerald-800">
                        Active
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded text-xs bg-gray-800 text-gray-500">
                        Inactive
                      </span>
                    )}
                  </div>
                  <div className="text-sm text-gray-400 font-mono">{store.shopify_domain}</div>
                  {store.niche && (
                    <div className="text-xs text-gray-500 mt-1">Niche: {store.niche}</div>
                  )}
                  {store.store_name && (
                    <div className="text-xs text-gray-500">Brand: {store.store_name}</div>
                  )}
                  <div className="flex items-center gap-2 mt-2 flex-wrap">
                    {store.installed_theme ? (
                      <span className="px-2 py-0.5 rounded text-xs bg-violet-900/40 text-violet-300 border border-violet-800">
                        Theme: {store.installed_theme}
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded text-xs text-gray-600 border border-gray-800">
                        No theme installed
                      </span>
                    )}
                    {store.has_payplus ? (
                      <span className="px-2 py-0.5 rounded text-xs bg-teal-900/40 text-teal-300 border border-teal-800">
                        PayPlus ✓
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded text-xs text-gray-600 border border-gray-800">
                        No PayPlus
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex flex-col items-end gap-2 ml-4 shrink-0">
                  <div className="flex items-center gap-2">
                    {storefronts[store.store_id]?.running && storefronts[store.store_id]?.port && (
                      <span className="px-2 py-0.5 rounded text-xs bg-emerald-900/50 text-emerald-300 border border-emerald-700 font-mono">
                        Running :{storefronts[store.store_id]?.port}
                      </span>
                    )}
                    <a
                      href={`https://${store.shopify_domain}/admin`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-3 py-1.5 rounded-lg text-xs text-teal-400 border border-teal-800 hover:bg-teal-900/30 transition-colors"
                    >
                      Admin ↗
                    </a>
                    <button
                      onClick={() => handleDelete(store.store_id)}
                      disabled={deleteId === store.store_id}
                      className="px-3 py-1.5 rounded-lg text-xs text-red-400 border border-red-900 hover:bg-red-900/30 disabled:opacity-50 transition-colors"
                    >
                      {deleteId === store.store_id ? 'Deleting...' : 'Remove'}
                    </button>
                  </div>

                  <div className="flex items-center gap-2">
                    {storefronts[store.store_id]?.running ? (
                      <button
                        onClick={() => handleStopLocal(store)}
                        disabled={stoppingId === store.store_id}
                        className="px-3 py-1.5 rounded-lg text-xs text-amber-300 border border-amber-800 hover:bg-amber-900/30 disabled:opacity-50 transition-colors"
                      >
                        {stoppingId === store.store_id ? 'Stopping…' : '■ Stop'}
                      </button>
                    ) : (
                      <button
                        onClick={() => handleRunLocal(store)}
                        disabled={runningId === store.store_id || runnerOffline}
                        title={runnerOffline ? 'Storefront runner offline' : 'Pull the live theme + run `shopify theme dev` locally'}
                        className="px-3 py-1.5 rounded-lg text-xs text-indigo-300 border border-indigo-700 bg-indigo-900/30 hover:bg-indigo-900/50 disabled:opacity-50 transition-colors"
                      >
                        {runningId === store.store_id ? '⏳ Starting…' : '▶ Run in localhost'}
                      </button>
                    )}
                    <button
                      onClick={() => handleUploadToShopify(store)}
                      disabled={deployingId === store.store_id}
                      title="Push local theme changes to Shopify (`shopify theme push` → unpublished theme)"
                      className="px-3 py-1.5 rounded-lg text-xs text-emerald-300 border border-emerald-800 hover:bg-emerald-900/30 disabled:opacity-50 transition-colors"
                    >
                      {deployingId === store.store_id ? '⏳ Uploading…' : '☁ Upload to Shopify'}
                    </button>
                  </div>
                </div>
              </div>

              {/* Theme Access password input (revealed when "Run in localhost" needs it) */}
              {tokenInputId === store.store_id && (
                <div className="mt-3 p-3 rounded-lg bg-gray-800/60 border border-indigo-900/60 space-y-2">
                  <div className="text-xs text-gray-400">
                    <code>shopify theme dev</code> needs a <strong className="text-gray-200">Theme Access password</strong> to preview locally.
                    <span className="block text-gray-500 mt-0.5">
                      Install the{' '}
                      <a href="https://shopify.dev/docs/storefronts/themes/tools/theme-access" target="_blank" rel="noopener noreferrer" className="text-indigo-400 hover:underline">Theme Access app</a>
                      {' '}in your store admin, generate a password (shptka_…), and paste it here.
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="password"
                      autoFocus
                      className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-indigo-500 font-mono"
                      placeholder="shptka_…"
                      value={tokenDraft}
                      onChange={e => setTokenDraft(e.target.value)}
                    />
                    <button
                      onClick={() => { setTokenInputId(null); setTokenDraft(''); }}
                      className="px-3 py-1.5 rounded-lg text-xs text-gray-400 hover:text-gray-200"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => handleSaveToken(store)}
                      disabled={savingToken || !tokenDraft}
                      className="px-3 py-1.5 rounded-lg bg-indigo-700 hover:bg-indigo-600 disabled:opacity-50 text-white text-xs font-medium"
                    >
                      {savingToken ? 'Saving…' : 'Save & Run'}
                    </button>
                  </div>
                </div>
              )}

              {/* Deploy result */}
              {deployResult[store.store_id] && (
                <div
                  className={`mt-3 p-3 rounded-lg border text-xs font-mono whitespace-pre-wrap break-words ${
                    deployResult[store.store_id].ok
                      ? 'bg-emerald-900/20 border-emerald-800 text-emerald-300'
                      : 'bg-gray-800/60 border-gray-700 text-gray-300'
                  }`}
                >
                  {deployResult[store.store_id].url && (
                    <a
                      href={deployResult[store.store_id].url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-emerald-400 underline block mb-1"
                    >
                      {deployResult[store.store_id].url} ↗
                    </a>
                  )}
                  {deployResult[store.store_id].output}
                </div>
              )}

              {/* Paths / URLs block */}
              <div className="mt-3 pt-3 border-t border-gray-800 grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
                <div>
                  <div className="text-gray-600 mb-0.5">Folder</div>
                  <div className="flex items-center gap-1.5">
                    <code className="text-gray-400 font-mono bg-gray-800 px-1.5 py-0.5 rounded truncate">
                      stores/shopify/{slugFor(store)}
                    </code>
                    <button
                      onClick={() => navigator.clipboard.writeText(`stores/shopify/${slugFor(store)}`)}
                      className="text-gray-600 hover:text-gray-400 transition-colors shrink-0"
                    >
                      copy
                    </button>
                  </div>
                </div>
                <div>
                  <div className="text-gray-600 mb-0.5">Localhost dev URL</div>
                  {storefronts[store.store_id]?.running && storefronts[store.store_id]?.port ? (
                    <a
                      href={`http://localhost:${storefronts[store.store_id]?.port}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-indigo-400 hover:underline font-mono"
                    >
                      http://localhost:{storefronts[store.store_id]?.port} ↗
                    </a>
                  ) : (
                    <span className="text-gray-600 italic">not running</span>
                  )}
                </div>
                <div>
                  <div className="text-gray-600 mb-0.5">Admin URL</div>
                  <a
                    href={`https://${store.shopify_domain}/admin`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-teal-400 hover:underline font-mono truncate block"
                  >
                    https://{store.shopify_domain}/admin ↗
                  </a>
                </div>
              </div>

              {/* Description — embedded for agentic RAG */}
              <div className="mt-3 pt-3 border-t border-gray-800">
                {editingDescId === store.store_id ? (
                  <div className="space-y-2">
                    <textarea
                      autoFocus
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 min-h-[80px]"
                      value={descDraft}
                      onChange={e => setDescDraft(e.target.value)}
                    />
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => setEditingDescId(null)}
                        className="px-3 py-1 rounded text-xs text-gray-400 hover:text-gray-200"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handleSaveDescription(store.store_id)}
                        disabled={savingDesc}
                        className="px-3 py-1 rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-medium"
                      >
                        {savingDesc ? 'Saving...' : 'Save'}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div
                    onClick={() => { setEditingDescId(store.store_id); setDescDraft(store.description || ''); }}
                    className="text-xs text-gray-400 hover:text-gray-300 cursor-pointer leading-relaxed"
                    title="Click to edit"
                  >
                    {store.description ? (
                      <>📝 {store.description}</>
                    ) : (
                      <span className="text-gray-600 italic">+ Add a description (what it contains + what it should become) for agentic RAG</span>
                    )}
                  </div>
                )}
              </div>

              {/* Store ID for API use */}
              <div className="mt-3 flex items-center gap-2">
                <span className="text-xs text-gray-600 font-mono">ID:</span>
                <code className="text-xs text-gray-500 font-mono bg-gray-800 px-2 py-0.5 rounded select-all">
                  {store.store_id}
                </code>
                <button
                  onClick={() => navigator.clipboard.writeText(store.store_id)}
                  className="text-xs text-gray-600 hover:text-gray-400 transition-colors"
                >
                  copy
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Info block */}
      <div className="mt-8 p-4 rounded-xl bg-gray-900/50 border border-gray-800 text-sm text-gray-400 space-y-2">
        <div className="font-medium text-gray-300">How multi-store works</div>
        <ul className="space-y-1 list-disc list-inside text-xs">
          <li>Each store has its own Shopify credentials — agents never mix up stores</li>
          <li>When you start a run in <strong className="text-gray-300">Live Runs</strong>, select which store to target</li>
          <li>Run multiple stores in parallel by starting separate runs</li>
          <li>The Director daemon monitors all active stores — checks revenue every interval and routes agents automatically</li>
          <li>Brand briefs are cached per-store — "Setup Only" runs save the brand so future "Products Only" runs don't rebuild it</li>
        </ul>
      </div>
    </div>
  );
}
