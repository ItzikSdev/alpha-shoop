import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { apiGet, apiPost, getToken } from '../api/client';

// ── Types ────────────────────────────────────────────────────────────────────

interface RunSummary {
  thread_id: string;
  task: string;
  operator: string;
  status: 'running' | 'completed' | 'failed' | 'killed' | 'pending';
  started_at: string;
  finished_at: string | null;
  total_llm_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
}

interface LLMCall {
  id: number;
  node: string;
  model: string;
  system_prompt: string;
  user_prompt: string;
  response: string;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  total_tokens: number;
  duration_ms: number;
  timestamp: string;
  error: string | null;
}

interface RunTrace extends RunSummary {
  llm_calls: LLMCall[];
  logs: LogEvent[];
}

interface LogEvent {
  type: 'log' | 'llm_call' | 'done' | 'error';
  ts?: string;
  node?: string;
  msg?: string;
  level?: 'info' | 'action' | 'success' | 'error' | 'warning';
  model?: string;
  tokens?: number;
  duration_ms?: number;
  error?: string | null;
  status?: string;
}

interface DaemonConfig {
  enabled: boolean;
  interval_minutes: number;
  task: string;
  last_started_at: string | null;
  next_run_at: string | null;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const NODE_META: Record<string, { label: string; color: string; icon: string }> = {
  director:          { label: 'Director',       color: '#CC785C', icon: 'D' },
  store_setup:       { label: 'Store Setup',    color: '#F59E0B', icon: 'S' },
  design_agent:      { label: 'Design Agent',   color: '#EC4899', icon: '✦' },
  trend_scraper:     { label: 'Trend Scraper',  color: '#E67E22', icon: 'T' },
  ecommerce_manager: { label: 'E-com Manager',  color: '#5E8E3E', icon: 'E' },
  marketing_agent:   { label: 'Marketing',      color: '#4285F4', icon: 'M' },
  fulfillment_agent: { label: 'Fulfillment',    color: '#7C3AED', icon: 'F' },
  unknown:           { label: 'Unknown',        color: '#666',    icon: '?' },
};

const ALL_NODES = Object.keys(NODE_META).filter(k => k !== 'unknown');

const STATUS_STYLE: Record<string, string> = {
  running:   'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
  completed: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30',
  failed:    'text-red-400 bg-red-400/10 border-red-400/30',
  killed:    'text-orange-400 bg-orange-400/10 border-orange-400/30',
  pending:   'text-gray-400 bg-gray-400/10 border-gray-400/30',
};

const LEVEL_COLOR: Record<string, string> = {
  info:    '#6b7280',
  action:  '#60a5fa',
  success: '#34d399',
  error:   '#f87171',
  warning: '#fbbf24',
};

const LEVEL_ICON: Record<string, string> = {
  info: '·', action: '→', success: '✓', error: '✗', warning: '⚠',
};

const PRESETS = [
  {
    id: 'full',
    label: '🏗️ Full Build',
    color: '#6366f1',
    desc: 'Brand → Design → Products',
    task: 'Build a complete focused niche store. Pick ONE specific product category (e.g. silver women rings, minimalist leather wallet, scented soy candles). Set up the brand identity, apply premium design, then find and publish 5-8 matching products with great copy. TANAOR-quality store.',
  },
  {
    id: 'rebuild',
    label: '🔄 Full Rebuild',
    color: '#f59e0b',
    desc: 'Reset brand + design + products',
    task: '[REBUILD] Completely rebuild this store from scratch. Ignore any previous brand. Generate a fresh brand identity for a baby products store, apply TANAOR-quality premium design (CSS, typography, spacing, buttons, product cards), then find and publish 5-8 baby products with premium copy.',
  },
  {
    id: 'setup',
    label: '🎨 Redesign Only',
    color: '#EC4899',
    desc: 'Reset brand + CSS only',
    task: '[SETUP_ONLY] Rebuild this store\'s brand identity and premium CSS from scratch. Ignore previous brand. Generate a fresh TANAOR-quality design: typography hierarchy, 80px+ breathing room, sharp premium buttons, product card zoom, glass-morphism header, announcement bar. Focus on baby products niche.',
  },
  {
    id: 'products',
    label: '📦 Add Products',
    color: '#5E8E3E',
    desc: 'Find + publish only',
    task: '[PRODUCTS_ONLY] Curate the store: remove any off-niche products, then find and publish up to 8 niche-matching products with premium copy. The store brand is already set.',
  },
  {
    id: 'curate',
    label: '🧹 Curate Store',
    color: '#E67E22',
    desc: 'Delete off-niche products',
    task: '[PRODUCTS_ONLY] Audit and curate the store: delete any products that don\'t match the store\'s niche. Do not add new products, only clean up what\'s there.',
  },
] as const;

const DEFAULT_TASK = PRESETS[0].task;

// ── Helpers ───────────────────────────────────────────────────────────────────

const API_BASE = (import.meta as unknown as { env: Record<string, string> }).env?.VITE_API_URL
  ?? 'http://localhost:8000/api/v1';

function fmt(n: number): string { return n.toLocaleString(); }
function fmtMs(ms: number): string { return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`; }

function fmtTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) +
    '.' + String(d.getMilliseconds()).padStart(3, '0');
}

function elapsed(started: string, finished: string | null): string {
  const end = finished ? new Date(finished) : new Date();
  return fmtMs(end.getTime() - new Date(started).getTime());
}

// ── NodeChip ─────────────────────────────────────────────────────────────────

function NodeChip({ node, small }: { node: string; small?: boolean }) {
  const meta = NODE_META[node] ?? NODE_META.unknown;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded font-mono font-semibold border shrink-0 ${small ? 'px-1 py-0 text-[9px]' : 'px-1.5 py-0.5 text-[10px]'}`}
      style={{ color: meta.color, borderColor: meta.color + '50', backgroundColor: meta.color + '18' }}
    >
      <span>{meta.icon}</span>
      {!small && <span>{meta.label}</span>}
    </span>
  );
}

// ── LLM Calls (trace inspector) ───────────────────────────────────────────────

function TokenBar({ input, output, cacheRead, cacheWrite }: {
  input: number; output: number; cacheRead: number; cacheWrite: number;
}) {
  const total = input + output;
  if (!total) return null;
  return (
    <div className="flex gap-3 items-center text-xs">
      <div className="flex-1 h-1.5 rounded-full bg-gray-800 overflow-hidden flex">
        <div className="h-full bg-blue-500/70" style={{ width: `${(input / total) * 100}%` }} />
        <div className="h-full bg-emerald-500/70" style={{ width: `${(output / total) * 100}%` }} />
      </div>
      <div className="flex gap-3 shrink-0 text-[10px] font-mono">
        <span className="text-blue-400">{fmt(input)} in</span>
        <span className="text-emerald-400">{fmt(output)} out</span>
        {cacheRead > 0 && <span className="text-purple-400">{fmt(cacheRead)} cache-r</span>}
        {cacheWrite > 0 && <span className="text-indigo-400">{fmt(cacheWrite)} cache-w</span>}
      </div>
    </div>
  );
}

function PromptSection({ label, text, defaultOpen = false }: { label: string; text: string; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  if (!text) return null;
  return (
    <div className="border border-gray-800 rounded-lg overflow-hidden">
      <button onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs font-mono text-gray-400 hover:text-gray-200 hover:bg-gray-800/40 transition-colors">
        <span className="font-semibold uppercase tracking-wider text-[10px]">{label}</span>
        <span className="text-gray-600">{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <pre className="px-3 py-2.5 text-[11px] text-gray-300 bg-gray-950/60 font-mono leading-relaxed overflow-x-auto whitespace-pre-wrap break-words border-t border-gray-800">
          {text}
        </pre>
      )}
    </div>
  );
}

function LLMCallCard({ call, index }: { call: LLMCall; index: number }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className={`border rounded-xl overflow-hidden ${call.error ? 'border-red-900/50' : 'border-gray-800'}`}>
      <button onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-800/30 transition-colors text-left">
        <span className="text-gray-700 font-mono text-xs w-5 shrink-0">#{index + 1}</span>
        <NodeChip node={call.node} />
        <span className="text-gray-600 font-mono text-[10px] shrink-0">{call.model}</span>
        <span className="text-gray-500 text-xs truncate flex-1 min-w-0">
          {call.user_prompt.slice(0, 80).replace(/\n/g, ' ')}{call.user_prompt.length > 80 && '…'}
        </span>
        {call.error && <span className="shrink-0 text-[10px] text-red-400 bg-red-400/10 border border-red-400/30 px-1.5 py-0.5 rounded">ERR</span>}
        <span className="shrink-0 font-mono text-xs text-gray-500">{fmt(call.total_tokens)} tok</span>
        <span className="shrink-0 font-mono text-xs text-gray-600">{fmtMs(call.duration_ms)}</span>
        <span className="shrink-0 text-gray-700 ml-1">{expanded ? '▾' : '▸'}</span>
      </button>
      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-gray-800">
          <div className="pt-3">
            <TokenBar input={call.input_tokens} output={call.output_tokens} cacheRead={call.cache_read_tokens} cacheWrite={call.cache_write_tokens} />
          </div>
          <div className="flex gap-4 text-[10px] font-mono text-gray-600">
            <span>Time: <span className="text-gray-400">{fmtTime(call.timestamp)}</span></span>
            <span>Duration: <span className="text-gray-400">{fmtMs(call.duration_ms)}</span></span>
          </div>
          {call.error && <div className="p-3 rounded-lg bg-red-950/30 border border-red-900/50 text-red-300 text-xs font-mono">{call.error}</div>}
          <PromptSection label="System Prompt" text={call.system_prompt} />
          <PromptSection label="User Prompt" text={call.user_prompt} defaultOpen />
          <PromptSection label="Response" text={call.response} defaultOpen />
        </div>
      )}
    </div>
  );
}

// ── Store selector mini-type ──────────────────────────────────────────────────

interface StoreSummary {
  store_id: string;
  name: string;
  shopify_domain: string;
  platform: string;
  niche: string;
  has_brand: boolean;
}

// ── Start Run form ─────────────────────────────────────────────────────────────

function StartRunPanel({ onStarted, apiUp }: { onStarted: (threadId: string) => void; apiUp: boolean }) {
  const [task, setTask] = useState<string>(DEFAULT_TASK);
  const [activePreset, setActivePreset] = useState<string>('full');
  const [budget, setBudget] = useState(100);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [stores, setStores] = useState<StoreSummary[]>([]);
  const [selectedStore, setSelectedStore] = useState<string>('');

  // Load stores on mount
  useEffect(() => {
    apiGet<StoreSummary[]>('/stores')
      .then(data => setStores(Array.isArray(data) ? data : []))
      .catch(() => {});
  }, []);

  const selectPreset = (p: typeof PRESETS[number]) => {
    setActivePreset(p.id);
    setTask(p.task);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!task.trim() || !apiUp) return;
    setLoading(true);
    setErr(null);
    try {
      const body: Record<string, unknown> = { task: task.trim(), max_budget_usd: budget };
      if (selectedStore) body.store_id = selectedStore;
      const data = await apiPost<{ thread_id: string }>('/run', body);
      onStarted(data.thread_id);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const activeStoreInfo = stores.find(s => s.store_id === selectedStore);

  return (
    <form onSubmit={handleSubmit} className="p-3 space-y-2.5 border-b border-gray-800">

      {/* API status */}
      <div className={`flex items-center gap-1.5 text-[10px] px-2 py-1 rounded border ${
        apiUp ? 'border-emerald-900/50 text-emerald-400 bg-emerald-950/20' : 'border-red-900/50 text-red-400 bg-red-950/20'
      }`}>
        <span className={`w-1.5 h-1.5 rounded-full ${apiUp ? 'bg-emerald-400' : 'bg-red-400 animate-pulse'}`} />
        {apiUp ? 'API online — ready to run' : 'API offline — start the server first'}
      </div>

      {/* Store selector */}
      <div>
        <label className="block text-gray-500 text-[10px] uppercase tracking-wider mb-1">Target Store</label>
        <select
          value={selectedStore}
          onChange={e => setSelectedStore(e.target.value)}
          className="w-full bg-gray-900 border border-gray-700 rounded-lg px-2.5 py-1.5 text-xs text-gray-200 focus:outline-none focus:border-indigo-500 transition-colors"
        >
          <option value="">Default (env config)</option>
          {stores.map(s => (
            <option key={s.store_id} value={s.store_id}>
              [{s.platform}] {s.name} — {s.shopify_domain}
            </option>
          ))}
        </select>
        {activeStoreInfo && (
          <div className="mt-1 flex items-center gap-2 text-[10px] text-gray-500">
            {activeStoreInfo.niche && <span>Niche: <span className="text-gray-400">{activeStoreInfo.niche}</span></span>}
            {activeStoreInfo.has_brand && (
              <span className="text-indigo-400 border border-indigo-900 rounded px-1 py-0.5">Brand cached</span>
            )}
          </div>
        )}
        {stores.length === 0 && (
          <div className="mt-1 text-[10px] text-gray-600">
            No stores configured — <span className="text-gray-500">add stores in My Stores</span>
          </div>
        )}
      </div>

      {/* Preset buttons */}
      <div className="grid grid-cols-2 gap-1.5">
        {PRESETS.map(p => (
          <button key={p.id} type="button" onClick={() => selectPreset(p)}
            className={`px-2 py-2 rounded-lg text-left transition-all border ${
              activePreset === p.id
                ? 'border-current'
                : 'border-gray-800 opacity-60 hover:opacity-90'
            }`}
            style={activePreset === p.id ? { borderColor: p.color + '70', backgroundColor: p.color + '12', color: p.color } : {}}>
            <div className="text-[11px] font-semibold">{p.label}</div>
            <div className="text-[9px] mt-0.5 opacity-70">{p.desc}</div>
          </button>
        ))}
      </div>

      {/* Task textarea (editable) */}
      <textarea value={task} onChange={e => { setTask(e.target.value); setActivePreset(''); }} rows={3}
        placeholder="Describe the store task…"
        className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-[11px] text-gray-400 placeholder-gray-600 resize-none focus:outline-none focus:border-indigo-500 transition-colors font-mono" />

      <div className="flex items-center gap-2">
        <label className="text-gray-600 text-[10px] shrink-0">Budget $</label>
        <input type="number" value={budget} onChange={e => setBudget(Number(e.target.value))}
          min={1} max={10000}
          className="w-20 bg-gray-900 border border-gray-700 rounded px-2 py-1 text-xs text-gray-200 focus:outline-none focus:border-indigo-500" />
        <button type="submit" disabled={loading || !task.trim() || !apiUp}
          className="flex-1 py-2 rounded-lg text-xs font-bold bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white transition-colors">
          {loading ? '⏳ Starting…' : '▶ Start Run'}
        </button>
      </div>

      {err && <div className="text-red-400 text-[10px] font-mono bg-red-950/30 border border-red-900/40 rounded px-2 py-1">{err}</div>}
    </form>
  );
}

// ── Daemon Panel ─────────────────────────────────────────────────────────────

function DaemonPanel() {
  const [config, setConfig] = useState<DaemonConfig | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const d = await apiGet<DaemonConfig>('/daemon');
      setConfig(d);
    } catch { /* API may not support daemon yet */ }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [load]);

  const patch = async (update: Partial<DaemonConfig>) => {
    if (!config) return;
    setSaving(true);
    try {
      const d = await apiPost<DaemonConfig>('/daemon', update);
      setConfig(d);
    } finally {
      setSaving(false);
    }
  };

  if (!config) return null;

  const intervals = [
    { label: '30m', value: 30 },
    { label: '1h', value: 60 },
    { label: '4h', value: 240 },
    { label: '12h', value: 720 },
    { label: '24h', value: 1440 },
  ];

  return (
    <div className="border-b border-gray-800 p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-gray-500 text-[10px] uppercase tracking-wider font-semibold">Auto-Run (Daemon)</span>
        <button
          onClick={() => patch({ enabled: !config.enabled })}
          disabled={saving}
          className={`relative w-8 h-4 rounded-full transition-colors ${config.enabled ? 'bg-indigo-600' : 'bg-gray-700'}`}
        >
          <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${config.enabled ? 'translate-x-4' : 'translate-x-0.5'}`} />
        </button>
      </div>

      {config.enabled && (
        <div className="space-y-1.5">
          <div className="flex gap-1">
            {intervals.map(iv => (
              <button key={iv.value}
                onClick={() => patch({ interval_minutes: iv.value })}
                className={`flex-1 py-0.5 rounded text-[10px] font-mono transition-colors ${
                  config.interval_minutes === iv.value
                    ? 'bg-indigo-700 text-indigo-100'
                    : 'bg-gray-800 text-gray-500 hover:text-gray-300'
                }`}>
                {iv.label}
              </button>
            ))}
          </div>
          {config.next_run_at && (
            <div className="text-gray-600 text-[10px]">
              Next: <span className="text-gray-400">{new Date(config.next_run_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            </div>
          )}
          {config.last_started_at && (
            <div className="text-gray-600 text-[10px]">
              Last: <span className="text-gray-400">{new Date(config.last_started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Run Card ─────────────────────────────────────────────────────────────────

function RunCard({ run, selected, onClick }: { run: RunSummary; selected: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className={`w-full text-left px-3 py-3 rounded-xl border transition-all ${
        selected ? 'border-indigo-600/60 bg-indigo-950/30' : 'border-gray-800 hover:border-gray-700 hover:bg-gray-800/30'
      }`}>
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${STATUS_STYLE[run.status] ?? STATUS_STYLE.pending}`}>
          {run.status === 'running' && <span className="inline-block w-1.5 h-1.5 rounded-full bg-current mr-1 animate-pulse" />}
          {run.status}
        </span>
        <span className="text-gray-600 text-[10px] font-mono shrink-0">
          {new Date(run.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
      <div className="text-gray-300 text-xs font-medium truncate mb-1.5">{run.task}</div>
      <div className="flex items-center gap-3 text-[10px] font-mono text-gray-600">
        <span>{run.total_llm_calls} calls</span>
        <span>{fmt(run.total_tokens)} tok</span>
        <span>{elapsed(run.started_at, run.finished_at)}</span>
      </div>
    </button>
  );
}

// ── KIBANA LOG PANEL ──────────────────────────────────────────────────────────

interface KibanaEvent {
  ts: string;
  node: string;
  msg: string;
  level: string;
  kind: 'log' | 'llm';
  model?: string;
  tokens?: number;
  duration_ms?: number;
}

function KibanaLogPanel({ threadId, isRunning }: { threadId: string; isRunning: boolean }) {
  const [events, setEvents] = useState<KibanaEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [follow, setFollow] = useState(true);
  const [search, setSearch] = useState('');
  const [levelFilter, setLevelFilter] = useState<string>('all');
  const [nodeFilter, setNodeFilter] = useState<Set<string>>(new Set());
  const [showLLM, setShowLLM] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);
  const esRef = useRef<EventSource | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Connect SSE
  useEffect(() => {
    if (!threadId) return;
    esRef.current?.close();
    setEvents([]);
    setConnected(false);

    const es = new EventSource(`${API_BASE}/runs/${threadId}/stream`);
    esRef.current = es;

    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === 'log') {
          setEvents(prev => [...prev, {
            ts: data.ts ?? new Date().toISOString(),
            node: data.node ?? 'unknown',
            msg: data.msg ?? '',
            level: data.level ?? 'info',
            kind: 'log',
          }]);
        } else if (data.type === 'llm_call') {
          setEvents(prev => [...prev, {
            ts: data.ts ?? new Date().toISOString(),
            node: data.node ?? 'unknown',
            msg: `LLM ◈ ${data.model ?? ''}  ${fmt(data.tokens ?? 0)} tok  ${fmtMs(data.duration_ms ?? 0)}`,
            level: 'info',
            kind: 'llm',
            model: data.model,
            tokens: data.tokens,
            duration_ms: data.duration_ms,
          }]);
        } else if (data.type === 'done') {
          setConnected(false);
          es.close();
        }
      } catch { /* ignore */ }
    };

    return () => { es.close(); esRef.current = null; };
  }, [threadId]);

  // Auto-scroll
  useEffect(() => {
    if (follow) bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events, follow]);

  // Detect manual scroll = disable follow
  const onScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    setFollow(scrollHeight - scrollTop - clientHeight < 60);
  };

  const filtered = useMemo(() => events.filter(ev => {
    if (ev.kind === 'llm' && !showLLM) return false;
    if (levelFilter !== 'all' && ev.level !== levelFilter) return false;
    if (nodeFilter.size > 0 && !nodeFilter.has(ev.node)) return false;
    if (search && !ev.msg.toLowerCase().includes(search.toLowerCase()) && !ev.node.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  }), [events, levelFilter, nodeFilter, search, showLLM]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { total: events.length, error: 0, warning: 0, success: 0, action: 0 };
    events.forEach(ev => { if (c[ev.level] !== undefined) c[ev.level]++; });
    return c;
  }, [events]);

  const toggleNode = (node: string) => {
    setNodeFilter(prev => {
      const next = new Set(prev);
      if (next.has(node)) next.delete(node); else next.add(node);
      return next;
    });
  };

  const levels = ['all', 'action', 'success', 'info', 'warning', 'error'];
  const levelColors: Record<string, string> = { all: '#6b7280', action: '#60a5fa', success: '#34d399', info: '#6b7280', warning: '#fbbf24', error: '#f87171' };

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* ── Toolbar ────────────────────────────────────────────────────────── */}
      <div className="shrink-0 border-b border-gray-800 bg-gray-950/80 p-2 space-y-2">
        {/* Row 1: connection status + counts */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : isRunning ? 'bg-yellow-400 animate-pulse' : 'bg-gray-600'}`} />
            <span className="text-[10px] text-gray-500 font-mono">
              {connected ? 'LIVE' : isRunning ? 'connecting…' : 'ended'}
            </span>
          </div>
          <span className="text-gray-700 text-[10px]">|</span>
          <span className="text-gray-400 text-[10px] font-mono">{counts.total} lines</span>
          {counts.error > 0 && <span className="text-red-400 text-[10px] font-mono bg-red-400/10 px-1.5 rounded">{counts.error} errors</span>}
          {counts.warning > 0 && <span className="text-yellow-400 text-[10px] font-mono bg-yellow-400/10 px-1.5 rounded">{counts.warning} warnings</span>}
          {counts.action > 0 && <span className="text-blue-400 text-[10px] font-mono bg-blue-400/10 px-1.5 rounded">{counts.action} actions</span>}
          <div className="ml-auto flex items-center gap-2">
            <button onClick={() => setShowLLM(s => !s)}
              className={`text-[10px] px-1.5 py-0.5 rounded border transition-colors ${showLLM ? 'border-purple-700 text-purple-400 bg-purple-400/10' : 'border-gray-700 text-gray-600'}`}>
              ◈ LLM calls
            </button>
            <button onClick={() => { setFollow(true); bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }}
              className={`text-[10px] px-1.5 py-0.5 rounded border transition-colors ${follow ? 'border-indigo-700 text-indigo-400 bg-indigo-400/10' : 'border-gray-700 text-gray-600'}`}>
              ↓ Follow
            </button>
          </div>
        </div>

        {/* Row 2: node filter chips */}
        <div className="flex gap-1 flex-wrap">
          {ALL_NODES.filter(n => n !== 'unknown').map(node => {
            const meta = NODE_META[node];
            const active = nodeFilter.size === 0 || nodeFilter.has(node);
            return (
              <button key={node} onClick={() => toggleNode(node)}
                className={`px-1.5 py-0.5 rounded text-[9px] font-mono border transition-colors ${active ? '' : 'opacity-30'}`}
                style={{ borderColor: meta.color + '60', color: meta.color, backgroundColor: active ? meta.color + '18' : 'transparent' }}>
                {meta.icon} {meta.label}
              </button>
            );
          })}
          {nodeFilter.size > 0 && (
            <button onClick={() => setNodeFilter(new Set())}
              className="px-1.5 py-0.5 rounded text-[9px] border border-gray-700 text-gray-500 hover:text-gray-300">
              ✕ clear
            </button>
          )}
        </div>

        {/* Row 3: level filter + search */}
        <div className="flex gap-2 items-center">
          <div className="flex gap-0.5">
            {levels.map(lv => (
              <button key={lv} onClick={() => setLevelFilter(lv)}
                className={`px-1.5 py-0.5 rounded text-[9px] font-mono border transition-colors ${levelFilter === lv ? 'border-current' : 'border-transparent text-gray-600 hover:text-gray-400'}`}
                style={{ color: levelFilter === lv ? levelColors[lv] : undefined, backgroundColor: levelFilter === lv ? levelColors[lv] + '20' : undefined }}>
                {lv === 'all' ? 'ALL' : LEVEL_ICON[lv] + ' ' + lv}
              </button>
            ))}
          </div>
          <div className="relative flex-1">
            <input value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Search logs…"
              className="w-full bg-gray-900 border border-gray-800 rounded px-2 py-0.5 text-[11px] text-gray-300 placeholder-gray-700 focus:outline-none focus:border-gray-600 font-mono" />
            {search && (
              <button onClick={() => setSearch('')}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-400 text-[10px]">✕</button>
            )}
          </div>
          <span className="text-gray-700 text-[10px] font-mono shrink-0">{filtered.length} / {events.length}</span>
        </div>
      </div>

      {/* ── Log lines ──────────────────────────────────────────────────────── */}
      <div ref={containerRef} onScroll={onScroll}
        className="flex-1 overflow-y-auto font-mono text-[11px] leading-5 bg-gray-950/40 min-h-0">

        {events.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-gray-700 gap-3">
            {isRunning || connected ? (
              <>
                <div className="flex gap-1">
                  <span className="w-1.5 h-5 rounded bg-gray-700 animate-pulse" />
                  <span className="w-1.5 h-5 rounded bg-gray-700 animate-pulse [animation-delay:150ms]" />
                  <span className="w-1.5 h-5 rounded bg-gray-700 animate-pulse [animation-delay:300ms]" />
                </div>
                <span className="text-sm">Agents starting…</span>
              </>
            ) : (
              <>
                <span className="text-2xl opacity-30">📋</span>
                <span className="text-sm">No logs for this run yet.</span>
              </>
            )}
          </div>
        )}

        {filtered.map((ev, i) => {
          const meta = NODE_META[ev.node] ?? NODE_META.unknown;
          const isLLM = ev.kind === 'llm';
          return (
            <div key={i}
              className={`flex items-start gap-0 px-3 py-0 min-h-[20px] hover:bg-white/[0.02] border-l-2 ${
                ev.level === 'error' ? 'border-red-900/60 bg-red-950/10' :
                ev.level === 'success' ? 'border-emerald-900/40' :
                ev.level === 'warning' ? 'border-yellow-900/40 bg-yellow-950/5' :
                isLLM ? 'border-purple-900/30 bg-purple-950/5' :
                'border-transparent'
              }`}>
              {/* Timestamp */}
              <span className="text-gray-700 shrink-0 w-28 pr-2 tabular-nums select-none">
                {ev.ts ? fmtTime(ev.ts) : ''}
              </span>

              {/* Agent badge (short) */}
              <span className="shrink-0 w-5 h-5 flex items-center justify-center text-[10px] font-bold mr-1.5 rounded"
                style={{ color: meta.color, backgroundColor: meta.color + '20' }}>
                {meta.icon}
              </span>
              <span className="shrink-0 text-[9px] font-mono mr-2 w-[80px] truncate" style={{ color: meta.color + 'aa' }}>
                {meta.label}
              </span>

              {/* Level icon */}
              <span className="shrink-0 w-4 mr-1 text-center"
                style={{ color: isLLM ? '#a78bfa' : LEVEL_COLOR[ev.level] ?? '#6b7280' }}>
                {isLLM ? '◈' : LEVEL_ICON[ev.level] ?? '·'}
              </span>

              {/* Message */}
              <span className="flex-1 min-w-0 break-words"
                style={{ color: isLLM ? '#c4b5fd' : LEVEL_COLOR[ev.level] ?? '#9ca3af' }}>
                {ev.msg}
              </span>
            </div>
          );
        })}

        {/* Running typing indicator */}
        {(connected || isRunning) && events.length > 0 && (
          <div className="flex gap-1.5 px-3 py-1 items-center">
            <span className="w-1 h-3 rounded-sm bg-gray-700 animate-pulse" />
            <span className="w-1 h-3 rounded-sm bg-gray-700 animate-pulse [animation-delay:150ms]" />
            <span className="w-1 h-3 rounded-sm bg-gray-700 animate-pulse [animation-delay:300ms]" />
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

type Tab = 'logs' | 'llm' | 'stats';

export function RunsPage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [trace, setTrace] = useState<RunTrace | null>(null);
  const [tab, setTab] = useState<Tab>('logs');
  const [error, setError] = useState<string | null>(null);
  const [apiUp, setApiUp] = useState(false);

  const selectedRun = runs.find(r => r.thread_id === selectedId) ?? null;
  const isRunning = selectedRun?.status === 'running' || selectedRun?.status === 'pending';

  const fetchRuns = useCallback(async () => {
    try {
      const data = await apiGet<RunSummary[]>('/runs');
      setRuns(data);
      setApiUp(true);
      setError(null);
    } catch (e) {
      setApiUp(false);
      setError(`Cannot reach API: ${(e as Error).message}`);
    }
  }, []);

  useEffect(() => {
    fetchRuns();
    const id = setInterval(fetchRuns, 3000);
    return () => clearInterval(id);
  }, [fetchRuns]);

  const fetchTrace = useCallback(async (threadId: string) => {
    try {
      const data = await apiGet<RunTrace>(`/runs/${threadId}/trace`);
      setTrace(data);
    } catch {
      // Trace not ready yet — that's fine, SSE handles live logs
    }
  }, []);

  // Refresh trace every 3s while selected run is active, once on select
  useEffect(() => {
    if (!selectedId) return;
    fetchTrace(selectedId);
    if (isRunning) {
      const id = setInterval(() => fetchTrace(selectedId), 3000);
      return () => clearInterval(id);
    }
  }, [selectedId, isRunning, fetchTrace]);

  // Also refresh trace once when run transitions to completed/failed
  useEffect(() => {
    if (selectedId && !isRunning && selectedRun) {
      fetchTrace(selectedId);
    }
  }, [selectedRun?.status]);

  const handleStarted = (threadId: string) => {
    setSelectedId(threadId);
    setTrace(null);
    setTab('logs');
    fetchRuns();
  };

  const handleSelect = (id: string) => {
    setSelectedId(id);
    setTrace(null);
    setTab('logs');
    fetchTrace(id);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-gray-950">

      {/* ── Left sidebar ────────────────────────────────────────────────────── */}
      <div className="w-72 shrink-0 border-r border-gray-800 flex flex-col">
        <div className="px-4 py-3 border-b border-gray-800 shrink-0">
          <h2 className="text-sm font-semibold text-white">Agent Runs</h2>
          <p className="text-gray-600 text-[10px] mt-0.5">Auto-refreshes · SSE live logs</p>

          {/* Pipeline flow */}
          <div className="mt-2.5 bg-gray-900/60 border border-gray-800 rounded-lg px-3 py-2">
            <div className="text-gray-700 text-[9px] uppercase tracking-wider mb-1.5">Full Build flow</div>
            <div className="flex items-center gap-1 flex-wrap">
              {[
                { label: 'Store Setup', color: '#F59E0B' },
                { label: 'Design', color: '#EC4899' },
                { label: 'Scraper', color: '#E67E22' },
                { label: 'E-com', color: '#5E8E3E' },
              ].map((a, i, arr) => (
                <span key={a.label} className="flex items-center gap-1">
                  <span className="text-[9px] font-mono px-1.5 py-0.5 rounded border"
                    style={{ color: a.color, borderColor: a.color + '40', backgroundColor: a.color + '15' }}>
                    {a.label}
                  </span>
                  {i < arr.length - 1 && <span className="text-gray-700 text-[9px]">→</span>}
                </span>
              ))}
            </div>
          </div>
        </div>

        <DaemonPanel />
        <StartRunPanel onStarted={handleStarted} apiUp={apiUp} />

        {error && (
          <div className="mx-3 mt-3 p-2.5 rounded-lg bg-red-950/40 border border-red-900/50 text-red-400 text-xs">{error}</div>
        )}

        <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-0">
          {runs.length === 0 && !error && (
            <div className="flex flex-col items-center justify-center h-40 text-gray-600 text-xs text-center gap-2">
              <span className="text-2xl opacity-40">🤖</span>
              <span>No runs yet.<br />Use the form above to start one.</span>
            </div>
          )}
          {[...runs].reverse().map(run => (
            <RunCard key={run.thread_id} run={run} selected={selectedId === run.thread_id}
              onClick={() => handleSelect(run.thread_id)} />
          ))}
        </div>
      </div>

      {/* ── Right: log/trace panel ─────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0">
        {!selectedId ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-700 gap-4">
            <span className="text-5xl opacity-20">📋</span>
            <div className="text-center">
              <div className="text-white text-sm font-medium mb-1">No run selected</div>
              <div className="text-gray-600 text-xs">Start a run or select one from the sidebar to see live logs</div>
            </div>
          </div>
        ) : (
          <>
            {/* ── Run header ─────────────────────────────────────────────── */}
            <div className="shrink-0 border-b border-gray-800 px-5 py-3 flex items-center gap-3 bg-gray-950">
              {selectedRun && (
                <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border shrink-0 ${STATUS_STYLE[selectedRun.status] ?? STATUS_STYLE.pending}`}>
                  {selectedRun.status === 'running' && <span className="inline-block w-1.5 h-1.5 rounded-full bg-current mr-1 animate-pulse" />}
                  {selectedRun.status}
                </span>
              )}
              <span className="text-gray-300 text-sm truncate flex-1 min-w-0">{selectedRun?.task ?? selectedId}</span>
              {selectedRun && (
                <span className="text-gray-600 text-[10px] font-mono shrink-0">{elapsed(selectedRun.started_at, selectedRun.finished_at)}</span>
              )}
            </div>

            {/* ── Tabs ───────────────────────────────────────────────────── */}
            <div className="shrink-0 flex border-b border-gray-800 bg-gray-950 px-4">
              {([
                { id: 'logs' as Tab, label: 'Live Logs', icon: '📋' },
                { id: 'llm' as Tab, label: `LLM Calls${trace ? ` (${trace.total_llm_calls})` : ''}`, icon: '◈' },
                { id: 'stats' as Tab, label: 'Stats', icon: '📊' },
              ] as const).map(t => (
                <button key={t.id} onClick={() => setTab(t.id)}
                  className={`px-3 py-2.5 text-xs font-medium transition-colors border-b-2 ${
                    tab === t.id ? 'border-indigo-500 text-indigo-300' : 'border-transparent text-gray-500 hover:text-gray-300'
                  }`}>
                  {t.icon} {t.label}
                </button>
              ))}
            </div>

            {/* ── Tab content ─────────────────────────────────────────────── */}
            <div className="flex-1 min-h-0 overflow-hidden">

              {/* LOGS TAB */}
              {tab === 'logs' && (
                <KibanaLogPanel threadId={selectedId} isRunning={isRunning} />
              )}

              {/* LLM CALLS TAB */}
              {tab === 'llm' && (
                <div className="h-full overflow-y-auto p-5">
                  {!trace ? (
                    <div className="text-gray-600 text-sm text-center py-16 animate-pulse">Loading trace…</div>
                  ) : trace.llm_calls.length === 0 ? (
                    <div className="text-gray-600 text-sm text-center py-16">
                      {isRunning ? 'Waiting for first LLM call…' : 'No LLM calls recorded.'}
                    </div>
                  ) : (
                    <div className="space-y-2 max-w-4xl mx-auto">
                      <TokenBar
                        input={trace.total_input_tokens}
                        output={trace.total_output_tokens}
                        cacheRead={trace.llm_calls.reduce((s, c) => s + c.cache_read_tokens, 0)}
                        cacheWrite={trace.llm_calls.reduce((s, c) => s + c.cache_write_tokens, 0)}
                      />
                      <div className="text-gray-600 text-xs pb-2">
                        {trace.llm_calls.length} calls · expand to see prompts and responses
                      </div>
                      {trace.llm_calls.map((call, i) => <LLMCallCard key={call.id} call={call} index={i} />)}
                    </div>
                  )}
                </div>
              )}

              {/* STATS TAB */}
              {tab === 'stats' && (
                <div className="h-full overflow-y-auto p-5">
                  {selectedRun ? (
                    <div className="max-w-2xl mx-auto space-y-4">
                      <div className="grid grid-cols-2 gap-3">
                        {[
                          { label: 'Status',        value: selectedRun.status },
                          { label: 'Duration',      value: elapsed(selectedRun.started_at, selectedRun.finished_at) },
                          { label: 'LLM Calls',     value: String(selectedRun.total_llm_calls) },
                          { label: 'Total Tokens',  value: fmt(selectedRun.total_tokens) },
                          { label: 'Input Tokens',  value: fmt(selectedRun.total_input_tokens) },
                          { label: 'Output Tokens', value: fmt(selectedRun.total_output_tokens) },
                        ].map(({ label, value }) => (
                          <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl px-4 py-3">
                            <div className="text-gray-600 text-[10px] uppercase tracking-wide mb-0.5">{label}</div>
                            <div className="text-white font-mono text-lg font-semibold">{value}</div>
                          </div>
                        ))}
                      </div>
                      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                        <div className="text-gray-600 text-[10px] uppercase tracking-wide mb-2">Task</div>
                        <p className="text-gray-300 text-sm leading-relaxed">{selectedRun.task}</p>
                      </div>
                      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                        <div className="text-gray-600 text-[10px] uppercase tracking-wide mb-1">Thread ID</div>
                        <p className="text-gray-500 font-mono text-xs">{selectedRun.thread_id}</p>
                      </div>
                    </div>
                  ) : (
                    <div className="text-gray-600 text-sm text-center py-16">No data</div>
                  )}
                </div>
              )}

            </div>
          </>
        )}
      </div>
    </div>
  );
}
