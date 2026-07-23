import { useEffect, useState } from 'react';
import { apiGet } from '../api/client';

interface RagEntry {
  id: string;
  text: string;
  pid?: string;
  verdict?: string;
  reason?: string;
  category?: string;
  images?: string;
  source_path?: string;
  doc_title?: string;
  section?: string;
}
interface RagResp { corpus: string; count: number; entries: RagEntry[] }

interface DbTable { name: string; count: number }
interface DbTablesResp { tables: DbTable[] }
interface DbRowsResp { table: string; columns: string[]; rows: Record<string, string | null>[]; count: number; error?: string }

interface RedisKeyInfo { key: string; type: string; ttl: number }
interface RedisKeysResp { pattern: string; count: number; keys: RedisKeyInfo[] }
interface RedisValueResp { key: string; type: string; ttl: number; value: unknown }

const CORPORA: { id: string; label: string; icon: string }[] = [
  { id: 'cj_catalog', label: 'CJ Catalog', icon: '📦' },
  { id: 'playbook', label: 'Playbook', icon: '📖' },
];

const VIEWS: { id: 'rag' | 'sqlite' | 'redis'; label: string; icon: string }[] = [
  { id: 'rag', label: 'RAG Corpora', icon: '🧠' },
  { id: 'sqlite', label: 'SQLite (traces.db)', icon: '🗄️' },
  { id: 'redis', label: 'Redis Keys', icon: '🔑' },
];

function verdictColor(verdict?: string): string {
  if (verdict === 'accepted') return 'border-emerald-800/50 bg-emerald-900/10 text-emerald-300';
  if (verdict === 'rejected') return 'border-rose-800/50 bg-rose-900/10 text-rose-300';
  return 'border-gray-700 bg-gray-900/40 text-gray-400';
}

function ViewTabs({ view, setView }: { view: string; setView: (v: 'rag' | 'sqlite' | 'redis') => void }) {
  return (
    <div className="mb-4 flex gap-2 border-b border-gray-800 pb-4">
      {VIEWS.map((v) => (
        <button
          key={v.id}
          onClick={() => setView(v.id)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors border ${
            view === v.id
              ? 'bg-indigo-900/70 text-indigo-200 border-indigo-700'
              : 'bg-gray-800 text-gray-400 border-gray-700 hover:text-gray-200'
          }`}
        >
          {v.icon} {v.label}
        </button>
      ))}
    </div>
  );
}

function RagCorporaView() {
  const [corpus, setCorpus] = useState('cj_catalog');
  const [data, setData] = useState<RagResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError('');
    try {
      const d = await apiGet<RagResp>(`/org/rag?corpus=${corpus}&limit=200`);
      setData(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [corpus]);

  return (
    <>
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-gray-500">
          Live view of what Sol has actually embedded into Redis — no raw vector bytes, just the
          searchable text + metadata. Backed by <code className="text-gray-400">GET /org/rag</code>.
        </p>
        <button
          onClick={load}
          className="px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs border border-gray-700 shrink-0"
        >
          ↻ Refresh
        </button>
      </div>

      <div className="mb-4 flex gap-2">
        {CORPORA.map((c) => (
          <button
            key={c.id}
            onClick={() => setCorpus(c.id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors border ${
              corpus === c.id
                ? 'bg-indigo-900/70 text-indigo-200 border-indigo-700'
                : 'bg-gray-800 text-gray-400 border-gray-700 hover:text-gray-200'
            }`}
          >
            {c.icon} {c.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="p-8 text-center text-gray-500">Loading…</div>
      ) : error ? (
        <div className="p-4 rounded-lg bg-red-900/40 border border-red-700 text-red-300 text-sm">{error}</div>
      ) : !data || data.count === 0 ? (
        <div className="p-8 text-center text-gray-500">
          No entries yet in <code>{corpus}</code> — it fills as Sol sources products (cj_catalog) or
          when <code>refresh_playbook</code> runs (playbook).
        </div>
      ) : (
        <>
          <p className="mb-3 text-xs text-gray-500">{data.count} entries</p>
          <div className="space-y-2">
            {data.entries.map((e) => {
              const isOpen = expanded === e.id;
              return (
                <div
                  key={e.id}
                  className={`rounded-xl border p-3 cursor-pointer ${corpus === 'cj_catalog' ? verdictColor(e.verdict) : 'border-gray-700 bg-gray-900/40'}`}
                  onClick={() => setExpanded(isOpen ? null : e.id)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      {corpus === 'cj_catalog' ? (
                        <>
                          <div className="font-medium text-gray-100 truncate">
                            {(e.text || '').split('\n')[0]}
                          </div>
                          <div className="text-xs text-gray-500 mt-0.5">
                            pid {e.pid} {e.category ? `· ${e.category}` : ''}
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="font-medium text-gray-100 truncate">{e.section || e.id}</div>
                          <div className="text-xs text-gray-500 mt-0.5">{e.source_path}</div>
                        </>
                      )}
                    </div>
                    {corpus === 'cj_catalog' && e.verdict && (
                      <span className="shrink-0 rounded-full px-2 py-0.5 text-xs font-medium border border-current/30">
                        {e.verdict}
                      </span>
                    )}
                  </div>
                  {corpus === 'cj_catalog' && e.reason && (
                    <div className="mt-1 text-xs text-gray-500">{e.reason}</div>
                  )}
                  {isOpen && (
                    <pre className="mt-3 whitespace-pre-wrap break-words text-xs text-gray-400 border-t border-gray-800 pt-2 max-h-96 overflow-y-auto">
                      {e.text}
                    </pre>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </>
  );
}

const PAGE_SIZE = 50;

function SqliteView() {
  const [tables, setTables] = useState<DbTable[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [rows, setRows] = useState<DbRowsResp | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function loadTables() {
    setLoading(true);
    setError('');
    try {
      const d = await apiGet<DbTablesResp>('/org/db/tables');
      setTables(d.tables);
      if (!selected && d.tables.length > 0) setSelected(d.tables[0].name);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }

  async function loadRows() {
    if (!selected) return;
    setLoading(true);
    setError('');
    try {
      const d = await apiGet<DbRowsResp>(`/org/db/tables/${selected}?limit=${PAGE_SIZE}&offset=${offset}`);
      setRows(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadTables(); }, []);
  useEffect(() => { setOffset(0); }, [selected]);
  useEffect(() => { loadRows(); }, [selected, offset]);

  return (
    <>
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-gray-500">
          Live tables from the single shared SQLite DB (<code className="text-gray-400">data/traces.db</code>) —
          org agents, stores, traces, tickets, product mappings. Read-only. Secret-looking columns
          (tokens, passwords, credentials) are redacted.
        </p>
        <button
          onClick={() => { loadTables(); loadRows(); }}
          className="px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs border border-gray-700 shrink-0"
        >
          ↻ Refresh
        </button>
      </div>

      {error && (
        <div className="mb-3 p-4 rounded-lg bg-red-900/40 border border-red-700 text-red-300 text-sm">{error}</div>
      )}

      <div className="flex gap-4">
        <div className="w-56 shrink-0 space-y-1">
          {(tables ?? []).map((t) => (
            <button
              key={t.name}
              onClick={() => setSelected(t.name)}
              className={`w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-sm text-left border ${
                selected === t.name
                  ? 'bg-indigo-900/70 text-indigo-200 border-indigo-700'
                  : 'bg-gray-800 text-gray-400 border-gray-700 hover:text-gray-200'
              }`}
            >
              <span className="truncate">{t.name}</span>
              <span className="text-xs text-gray-500 ml-2 shrink-0">{t.count}</span>
            </button>
          ))}
        </div>

        <div className="flex-1 min-w-0">
          {loading && !rows ? (
            <div className="p-8 text-center text-gray-500">Loading…</div>
          ) : rows && rows.error ? (
            <div className="p-4 rounded-lg bg-red-900/40 border border-red-700 text-red-300 text-sm">{rows.error}</div>
          ) : rows && rows.rows.length === 0 ? (
            <div className="p-8 text-center text-gray-500">No rows in <code>{rows.table}</code>.</div>
          ) : rows ? (
            <>
              <div className="mb-2 flex items-center justify-between text-xs text-gray-500">
                <span>
                  {rows.table} — {offset + 1}–{offset + rows.rows.length} of {rows.count}
                </span>
                <div className="flex gap-2">
                  <button
                    disabled={offset === 0}
                    onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                    className="px-2 py-1 rounded bg-gray-800 border border-gray-700 disabled:opacity-40 hover:text-gray-200"
                  >
                    ← Prev
                  </button>
                  <button
                    disabled={offset + rows.rows.length >= rows.count}
                    onClick={() => setOffset(offset + PAGE_SIZE)}
                    className="px-2 py-1 rounded bg-gray-800 border border-gray-700 disabled:opacity-40 hover:text-gray-200"
                  >
                    Next →
                  </button>
                </div>
              </div>
              <div className="overflow-auto rounded-xl border border-gray-800 max-h-[70vh]">
                <table className="w-full text-xs">
                  <thead className="bg-gray-900 sticky top-0">
                    <tr>
                      {rows.columns.map((c) => (
                        <th key={c} className="text-left px-2 py-1.5 font-medium text-gray-400 border-b border-gray-800 whitespace-nowrap">
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.rows.map((row, i) => (
                      <tr key={i} className="border-b border-gray-900 hover:bg-gray-900/40">
                        {rows.columns.map((c) => (
                          <td key={c} className="px-2 py-1.5 text-gray-300 max-w-xs truncate" title={row[c] ?? ''}>
                            {row[c] ?? <span className="text-gray-600">null</span>}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </>
  );
}

function redisValuePreview(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  return JSON.stringify(value);
}

function RedisView() {
  const [pattern, setPattern] = useState('*');
  const [patternInput, setPatternInput] = useState('*');
  const [keys, setKeys] = useState<RedisKeysResp | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<RedisValueResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState('');

  async function loadKeys() {
    setLoading(true);
    setError('');
    try {
      const d = await apiGet<RedisKeysResp>(`/org/redis/keys?pattern=${encodeURIComponent(pattern)}&limit=300`);
      setKeys(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }

  async function loadDetail(key: string) {
    setSelected(key);
    setDetailLoading(true);
    try {
      const d = await apiGet<RedisValueResp>(`/org/redis/keys/${encodeURIComponent(key)}`);
      setDetail(d);
    } catch (e) {
      setDetail({ key, type: 'error', ttl: -1, value: e instanceof Error ? e.message : 'Failed to load' });
    } finally {
      setDetailLoading(false);
    }
  }

  useEffect(() => { loadKeys(); }, [pattern]);

  return (
    <>
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-gray-500">
          Raw live scan of the Redis keyspace (redis-stack container) — every key, not just the
          curated RAG corpora above. Vector bytes are always redacted.
        </p>
        <button
          onClick={loadKeys}
          className="px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs border border-gray-700 shrink-0"
        >
          ↻ Refresh
        </button>
      </div>

      <form
        onSubmit={(ev) => { ev.preventDefault(); setPattern(patternInput || '*'); }}
        className="mb-4 flex gap-2"
      >
        <input
          value={patternInput}
          onChange={(ev) => setPatternInput(ev.target.value)}
          placeholder="key pattern, e.g. cj_catalog:* or playbook:*"
          className="flex-1 px-3 py-1.5 rounded-lg bg-gray-900 border border-gray-700 text-sm text-gray-200 placeholder-gray-600"
        />
        <button
          type="submit"
          className="px-3 py-1.5 rounded-lg bg-indigo-900/70 hover:bg-indigo-800 text-indigo-200 text-sm border border-indigo-700"
        >
          Scan
        </button>
      </form>

      {error && (
        <div className="mb-3 p-4 rounded-lg bg-red-900/40 border border-red-700 text-red-300 text-sm">{error}</div>
      )}

      <div className="flex gap-4">
        <div className="w-1/2 min-w-0">
          {loading ? (
            <div className="p-8 text-center text-gray-500">Scanning…</div>
          ) : !keys || keys.count === 0 ? (
            <div className="p-8 text-center text-gray-500">No keys match <code>{pattern}</code>.</div>
          ) : (
            <>
              <p className="mb-2 text-xs text-gray-500">{keys.count} keys</p>
              <div className="space-y-1 max-h-[70vh] overflow-y-auto">
                {keys.keys.map((k) => (
                  <button
                    key={k.key}
                    onClick={() => loadDetail(k.key)}
                    className={`w-full text-left px-3 py-1.5 rounded-lg text-xs border flex items-center justify-between gap-2 ${
                      selected === k.key
                        ? 'bg-indigo-900/70 text-indigo-200 border-indigo-700'
                        : 'bg-gray-800 text-gray-300 border-gray-700 hover:text-gray-100'
                    }`}
                  >
                    <span className="truncate font-mono">{k.key}</span>
                    <span className="shrink-0 text-gray-500">
                      {k.type}{k.ttl >= 0 ? ` · ttl ${k.ttl}s` : ''}
                    </span>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        <div className="w-1/2 min-w-0">
          {!selected ? (
            <div className="p-8 text-center text-gray-500 border border-dashed border-gray-800 rounded-xl h-full flex items-center justify-center">
              Select a key to view its live value
            </div>
          ) : detailLoading ? (
            <div className="p-8 text-center text-gray-500">Loading…</div>
          ) : detail ? (
            <div className="rounded-xl border border-gray-700 bg-gray-900/40 p-3">
              <div className="font-mono text-xs text-gray-300 break-all mb-1">{detail.key}</div>
              <div className="text-xs text-gray-500 mb-3">
                type {detail.type}{detail.ttl >= 0 ? ` · ttl ${detail.ttl}s` : ' · no expiry'}
              </div>
              <pre className="whitespace-pre-wrap break-words text-xs text-gray-400 border-t border-gray-800 pt-2 max-h-[60vh] overflow-y-auto">
                {redisValuePreview(detail.value)}
              </pre>
            </div>
          ) : null}
        </div>
      </div>
    </>
  );
}

export function RagPage() {
  const [view, setView] = useState<'rag' | 'sqlite' | 'redis'>('rag');

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-2">
        <h1 className="text-2xl font-bold text-gray-100">🧠 RAG & Live Databases</h1>
      </div>

      <ViewTabs view={view} setView={setView} />

      {view === 'rag' && <RagCorporaView />}
      {view === 'sqlite' && <SqliteView />}
      {view === 'redis' && <RedisView />}
    </div>
  );
}
