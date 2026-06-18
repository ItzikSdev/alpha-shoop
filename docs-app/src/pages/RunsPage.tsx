import { useState, useEffect, useCallback, useRef } from 'react';
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
}

// ── Constants ─────────────────────────────────────────────────────────────────

const NODE_META: Record<string, { label: string; color: string; icon: string }> = {
  director:          { label: 'Director',       color: '#CC785C', icon: 'D' },
  store_setup:       { label: 'Store Setup',    color: '#F59E0B', icon: 'S' },
  trend_scraper:     { label: 'Trend Scraper',  color: '#E67E22', icon: 'T' },
  ecommerce_manager: { label: 'E-com Manager',  color: '#5E8E3E', icon: 'E' },
  marketing_agent:   { label: 'Marketing',      color: '#4285F4', icon: 'M' },
  fulfillment_agent: { label: 'Fulfillment',    color: '#7C3AED', icon: 'F' },
  unknown:           { label: 'Unknown',        color: '#666',    icon: '?' },
};

const STATUS_STYLE: Record<string, string> = {
  running:   'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
  completed: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30',
  failed:    'text-red-400 bg-red-400/10 border-red-400/30',
  killed:    'text-orange-400 bg-orange-400/10 border-orange-400/30',
  pending:   'text-gray-400 bg-gray-400/10 border-gray-400/30',
};

const DEFAULT_TASK =
  'Build a store for trending home decor products under $50. Set up the store brand, find top products with 30%+ margin, list them on Shopify with great copy.';

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(n: number): string {
  return n.toLocaleString();
}

function fmtMs(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`;
}

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function elapsed(started: string, finished: string | null): string {
  const end = finished ? new Date(finished) : new Date();
  const ms = end.getTime() - new Date(started).getTime();
  return fmtMs(ms);
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function NodeChip({ node }: { node: string }) {
  const meta = NODE_META[node] ?? NODE_META.unknown;
  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold border"
      style={{ color: meta.color, borderColor: meta.color + '50', backgroundColor: meta.color + '18' }}
    >
      <span className="w-3 h-3 rounded-full flex items-center justify-center text-[8px]"
        style={{ backgroundColor: meta.color + '30' }}>{meta.icon}</span>
      {meta.label}
    </span>
  );
}

function TokenBar({ input, output, cacheRead, cacheWrite }: {
  input: number; output: number; cacheRead: number; cacheWrite: number;
}) {
  const total = input + output;
  if (!total) return null;
  const inputPct = (input / total) * 100;
  const outputPct = (output / total) * 100;
  return (
    <div className="flex gap-3 items-center text-xs">
      <div className="flex-1 h-1.5 rounded-full bg-gray-800 overflow-hidden flex">
        <div className="h-full bg-blue-500/70" style={{ width: `${inputPct}%` }} />
        <div className="h-full bg-emerald-500/70" style={{ width: `${outputPct}%` }} />
      </div>
      <div className="flex gap-3 shrink-0 text-[10px] font-mono">
        <span className="text-blue-400">{fmt(input)} in</span>
        <span className="text-emerald-400">{fmt(output)} out</span>
        {cacheRead > 0 && <span className="text-purple-400">{fmt(cacheRead)} cache-read</span>}
        {cacheWrite > 0 && <span className="text-indigo-400">{fmt(cacheWrite)} cache-write</span>}
      </div>
    </div>
  );
}

function PromptSection({ label, text, defaultOpen = false }: {
  label: string; text: string; defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  if (!text) return null;
  return (
    <div className="border border-gray-800 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs font-mono text-gray-400 hover:text-gray-200 hover:bg-gray-800/40 transition-colors"
      >
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
  const meta = NODE_META[call.node] ?? NODE_META.unknown;

  return (
    <div className={`border rounded-xl overflow-hidden transition-all ${
      call.error ? 'border-red-900/50' : 'border-gray-800'
    }`}>
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-800/30 transition-colors text-left"
      >
        <span className="text-gray-700 font-mono text-xs w-5 shrink-0">#{index + 1}</span>
        <NodeChip node={call.node} />
        <span className="text-gray-600 font-mono text-[10px] shrink-0">{call.model}</span>
        <span className="text-gray-500 text-xs truncate flex-1 min-w-0">
          {call.user_prompt.slice(0, 80).replace(/\n/g, ' ')}
          {call.user_prompt.length > 80 && '…'}
        </span>
        {call.error && (
          <span className="shrink-0 text-[10px] text-red-400 bg-red-400/10 border border-red-400/30 px-1.5 py-0.5 rounded">
            ERROR
          </span>
        )}
        <span className="shrink-0 font-mono text-xs text-gray-500">{fmt(call.total_tokens)} tok</span>
        <span className="shrink-0 font-mono text-xs text-gray-600">{fmtMs(call.duration_ms)}</span>
        <span className="shrink-0 text-gray-700 ml-1">{expanded ? '▾' : '▸'}</span>
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-gray-800">
          <div className="pt-3">
            <TokenBar
              input={call.input_tokens}
              output={call.output_tokens}
              cacheRead={call.cache_read_tokens}
              cacheWrite={call.cache_write_tokens}
            />
          </div>
          <div className="flex gap-4 text-[10px] font-mono text-gray-600">
            <span>Time: <span className="text-gray-400">{fmtTime(call.timestamp)}</span></span>
            <span>Duration: <span className="text-gray-400">{fmtMs(call.duration_ms)}</span></span>
            <span>Model: <span className="text-gray-400">{call.model}</span></span>
          </div>
          {call.error && (
            <div className="p-3 rounded-lg bg-red-950/30 border border-red-900/50 text-red-300 text-xs font-mono">
              {call.error}
            </div>
          )}
          <PromptSection label="System Prompt" text={call.system_prompt} />
          <PromptSection label="User Prompt" text={call.user_prompt} defaultOpen />
          <PromptSection label="Response" text={call.response} defaultOpen />
        </div>
      )}
    </div>
  );
}

function RunCard({ run, selected, onClick }: {
  run: RunSummary; selected: boolean; onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-3 rounded-xl border transition-all ${
        selected
          ? 'border-indigo-600/60 bg-indigo-950/30'
          : 'border-gray-800 hover:border-gray-700 hover:bg-gray-800/30'
      }`}
    >
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${STATUS_STYLE[run.status] ?? STATUS_STYLE.pending}`}>
          {run.status === 'running' && (
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-current mr-1 animate-pulse" />
          )}
          {run.status}
        </span>
        <span className="text-gray-600 text-[10px] font-mono shrink-0">
          {fmtTime(run.started_at)}
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

// ── Start Run panel ───────────────────────────────────────────────────────────

function StartRunPanel({ onStarted }: { onStarted: (threadId: string) => void }) {
  const [task, setTask] = useState(DEFAULT_TASK);
  const [budget, setBudget] = useState(100);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!task.trim()) return;
    setLoading(true);
    setErr(null);
    try {
      const data = await apiPost<{ thread_id: string }>('/run', {
        task: task.trim(),
        max_budget_usd: budget,
      });
      onStarted(data.thread_id);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="border-b border-gray-800 p-3 space-y-2">
      <textarea
        value={task}
        onChange={e => setTask(e.target.value)}
        rows={3}
        placeholder="Describe the store task…"
        className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-200 placeholder-gray-600 resize-none focus:outline-none focus:border-indigo-500 transition-colors"
      />
      <div className="flex items-center gap-2">
        <label className="text-gray-600 text-[10px] shrink-0">Budget $</label>
        <input
          type="number"
          value={budget}
          onChange={e => setBudget(Number(e.target.value))}
          min={1}
          max={10000}
          className="w-20 bg-gray-900 border border-gray-700 rounded px-2 py-1 text-xs text-gray-200 focus:outline-none focus:border-indigo-500"
        />
        <button
          type="submit"
          disabled={loading || !task.trim()}
          className="flex-1 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white transition-colors"
        >
          {loading ? 'Starting…' : '▶ Start Run'}
        </button>
      </div>
      {err && (
        <div className="text-red-400 text-[10px] font-mono bg-red-950/30 border border-red-900/40 rounded px-2 py-1">
          {err}
        </div>
      )}
    </form>
  );
}

// ── Live Log ──────────────────────────────────────────────────────────────────

interface LogEvent {
  type: 'log' | 'llm_call' | 'done' | 'error';
  ts?: string;
  node?: string;
  msg?: string;
  level?: 'info' | 'action' | 'success' | 'error' | 'warning';
  // llm_call fields
  model?: string;
  tokens?: number;
  duration_ms?: number;
  error?: string | null;
  // done fields
  status?: string;
}

const LEVEL_STYLE: Record<string, string> = {
  info:    'text-gray-400',
  action:  'text-blue-400',
  success: 'text-emerald-400',
  error:   'text-red-400',
  warning: 'text-yellow-400',
};

const LEVEL_ICON: Record<string, string> = {
  info: '·', action: '→', success: '✓', error: '✗', warning: '⚠',
};

function LiveLogPanel({ threadId, isRunning }: { threadId: string; isRunning: boolean }) {
  const [events, setEvents] = useState<LogEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!threadId) return;

    // Close any previous SSE connection
    esRef.current?.close();
    setEvents([]);

    const API = (import.meta as unknown as { env: Record<string, string> }).env?.VITE_API_URL ?? 'http://localhost:8000/api/v1';
    const url = `${API}/runs/${threadId}/stream`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);

    es.onmessage = (e) => {
      try {
        const data: LogEvent = JSON.parse(e.data);
        if (data.type === 'done') {
          setConnected(false);
          es.close();
        }
        setEvents(prev => [...prev, { ...data, ts: data.ts ?? new Date().toISOString() }]);
      } catch { /* ignore parse errors */ }
    };

    return () => { es.close(); esRef.current = null; };
  }, [threadId]);

  // Auto-scroll to bottom on new events
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events]);

  return (
    <div className="border border-gray-800 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-800 bg-gray-900/50">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Live Log</span>
        <div className="flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : 'bg-gray-600'}`} />
          <span className="text-[10px] text-gray-600">{connected ? 'streaming' : isRunning ? 'connecting...' : 'ended'}</span>
        </div>
      </div>

      <div className="overflow-y-auto font-mono text-[11px] leading-relaxed bg-gray-950/60" style={{ maxHeight: 280, minHeight: 80 }}>
        {events.length === 0 && (
          <div className="px-4 py-6 text-gray-700 text-center">Waiting for agent activity…</div>
        )}
        {events.map((ev, i) => {
          if (ev.type === 'log') {
            const style = LEVEL_STYLE[ev.level ?? 'info'];
            const icon = LEVEL_ICON[ev.level ?? 'info'];
            return (
              <div key={i} className="flex gap-2 px-4 py-0.5 hover:bg-gray-900/40">
                <span className="text-gray-700 shrink-0 w-20 truncate">{ev.ts ? fmtTime(ev.ts) : ''}</span>
                <NodeChip node={ev.node ?? 'unknown'} />
                <span className={`${style} shrink-0`}>{icon}</span>
                <span className={style}>{ev.msg}</span>
              </div>
            );
          }
          if (ev.type === 'llm_call') {
            return (
              <div key={i} className="flex gap-2 px-4 py-0.5 hover:bg-gray-900/40">
                <span className="text-gray-700 shrink-0 w-20 truncate">{ev.ts ? fmtTime(ev.ts) : ''}</span>
                <NodeChip node={ev.node ?? 'unknown'} />
                <span className="text-purple-400 shrink-0">◈</span>
                <span className="text-purple-300">LLM</span>
                <span className="text-gray-600 text-[10px]">{ev.model}</span>
                <span className="text-gray-500 text-[10px] ml-auto shrink-0">{fmt(ev.tokens ?? 0)} tok · {fmtMs(ev.duration_ms ?? 0)}</span>
                {ev.error && <span className="text-red-400 text-[10px]">ERR</span>}
              </div>
            );
          }
          if (ev.type === 'done') {
            return (
              <div key={i} className="flex gap-2 px-4 py-1 border-t border-gray-800 mt-1">
                <span className={`font-semibold ${ev.status === 'completed' ? 'text-emerald-400' : 'text-red-400'}`}>
                  ■ Run {ev.status}
                </span>
              </div>
            );
          }
          return null;
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function RunsPage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [trace, setTrace] = useState<RunTrace | null>(null);
  const [loadingTrace, setLoadingTrace] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRuns = useCallback(async () => {
    try {
      const data = await apiGet<RunSummary[]>('/runs');
      setRuns(data);
      setError(null);
    } catch (e) {
      setError(`Cannot reach API: ${(e as Error).message}`);
    }
  }, []);

  useEffect(() => {
    fetchRuns();
    const id = setInterval(fetchRuns, 2000);
    return () => clearInterval(id);
  }, [fetchRuns]);

  const fetchTrace = useCallback(async (threadId: string) => {
    setLoadingTrace(true);
    try {
      const data = await apiGet<RunTrace>(`/runs/${threadId}/trace`);
      setTrace(data);
    } catch {
      setTrace(null);
    } finally {
      setLoadingTrace(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    fetchTrace(selectedId);
    const selected = runs.find(r => r.thread_id === selectedId);
    if (selected?.status === 'running') {
      const id = setInterval(() => fetchTrace(selectedId), 2000);
      return () => clearInterval(id);
    }
  }, [selectedId, fetchTrace, runs]);

  const handleStarted = (threadId: string) => {
    fetchRuns();
    setSelectedId(threadId);
    setTrace(null);
  };

  const handleSelect = (id: string) => {
    setSelectedId(id);
    setTrace(null);
    fetchTrace(id);
  };

  return (
    <div className="flex h-screen overflow-hidden">

      {/* ── Left: runs list + start form ─────────────────────────────────── */}
      <div className="w-72 shrink-0 border-r border-gray-800 flex flex-col bg-gray-950">
        <div className="px-4 py-4 border-b border-gray-800">
          <h2 className="text-sm font-semibold text-white">Live Runs</h2>
          <p className="text-gray-500 text-xs mt-0.5">Auto-refreshes every 2s</p>
        </div>

        <StartRunPanel onStarted={handleStarted} />

        {error && (
          <div className="mx-3 mt-3 p-2.5 rounded-lg bg-red-950/40 border border-red-900/50 text-red-400 text-xs">
            {error}
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {runs.length === 0 && !error && (
            <div className="flex flex-col items-center justify-center h-40 text-gray-600 text-xs text-center gap-2">
              <span className="text-2xl opacity-40">🤖</span>
              <span>No runs yet.<br />Use the form above to start one.</span>
            </div>
          )}
          {[...runs].reverse().map(run => (
            <RunCard
              key={run.thread_id}
              run={run}
              selected={selectedId === run.thread_id}
              onClick={() => handleSelect(run.thread_id)}
            />
          ))}
        </div>
      </div>

      {/* ── Right: trace inspector ─────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto bg-gray-950">
        {!selectedId && (
          <div className="flex flex-col items-center justify-center h-full text-gray-600 gap-3">
            <span className="text-4xl opacity-30">🔍</span>
            <span className="text-sm">Select a run to inspect its LLM calls</span>
          </div>
        )}

        {selectedId && loadingTrace && !trace && (
          <div className="flex items-center justify-center h-full">
            <span className="text-gray-600 text-sm animate-pulse">Loading trace…</span>
          </div>
        )}

        {trace && (
          <div className="p-6 max-w-5xl mx-auto space-y-6">

            {/* Run header */}
            <div className="space-y-2">
              <div className="flex items-center gap-3 flex-wrap">
                <span className={`text-xs font-medium px-2 py-1 rounded border ${STATUS_STYLE[trace.status] ?? STATUS_STYLE.pending}`}>
                  {trace.status === 'running' && (
                    <span className="inline-block w-1.5 h-1.5 rounded-full bg-current mr-1.5 animate-pulse" />
                  )}
                  {trace.status}
                </span>
                <span className="text-gray-400 text-sm font-medium">{trace.task}</span>
                <span className="text-gray-600 text-xs font-mono ml-auto">
                  {trace.thread_id.slice(0, 8)}…
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { label: 'LLM Calls',     value: String(trace.total_llm_calls) },
                  { label: 'Input Tokens',  value: fmt(trace.total_input_tokens) },
                  { label: 'Output Tokens', value: fmt(trace.total_output_tokens) },
                  { label: 'Duration',      value: elapsed(trace.started_at, trace.finished_at) },
                ].map(({ label, value }) => (
                  <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl px-4 py-3">
                    <div className="text-gray-600 text-[10px] uppercase tracking-wide mb-0.5">{label}</div>
                    <div className="text-white font-mono text-lg font-semibold">{value}</div>
                  </div>
                ))}
              </div>

              <TokenBar
                input={trace.total_input_tokens}
                output={trace.total_output_tokens}
                cacheRead={trace.llm_calls.reduce((s, c) => s + c.cache_read_tokens, 0)}
                cacheWrite={trace.llm_calls.reduce((s, c) => s + c.cache_write_tokens, 0)}
              />
            </div>

            {/* Live log */}
            <LiveLogPanel threadId={trace.thread_id} isRunning={trace.status === 'running'} />

            {/* LLM calls */}
            <div>
              <div className="text-gray-500 text-xs uppercase tracking-wide mb-3">
                LLM Calls ({trace.llm_calls.length})
                <span className="text-gray-700 normal-case tracking-normal ml-2">
                  — click a row to expand prompts and response
                </span>
              </div>

              {trace.llm_calls.length === 0 && (
                <div className="text-gray-600 text-sm text-center py-8">
                  {trace.status === 'running'
                    ? 'Waiting for first LLM call…'
                    : 'No LLM calls were recorded for this run.'}
                </div>
              )}

              <div className="space-y-2">
                {trace.llm_calls.map((call, i) => (
                  <LLMCallCard key={call.id} call={call} index={i} />
                ))}
              </div>
            </div>

            {trace.status === 'running' && (
              <div className="text-center text-gray-700 text-xs pb-4 animate-pulse">
                Live — refreshing every 2s
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
