import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { apiGet, apiPost } from '../api/client';

// ── Types ────────────────────────────────────────────────────────────────────

interface GraphNode {
  id: number;
  type: string;
  name: string;
  role?: string | null;
  props?: Record<string, unknown>;
}

interface GraphEdge {
  source: number;
  target: number;
  type: string;
  ok: boolean | null;
  label: string;
}

interface GraphData {
  available: boolean;
  nodes: GraphNode[];
  edges: GraphEdge[];
  note?: string;
  error?: string;
  columns?: string[];
  rows?: unknown[][];
}

// A node inside the physics simulation.
interface SimNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  pinned?: boolean;
}

const NODE_COLOR: Record<string, string> = {
  Agent: '#ec4899',
  Tool: '#3b82f6',
  Media: '#f59e0b',
  Action: '#10b981',
};
const DEFAULT_NODE_COLOR = '#94a3b8';

const EDGE_STYLE: Record<string, { color: string; dash?: string; faint?: boolean }> = {
  CAN_USE: { color: '#475569', dash: '4 4', faint: true },
  EXECUTED: { color: '#3b82f6' },
  ASSIGNED: { color: '#ec4899' },
  DECIDED: { color: '#10b981' },
  GENERATED: { color: '#f59e0b' },
};

const W = 1400;
const H = 900;

// The FalkorDB Browser only draws something when the URL carries BOTH the graph
// name AND a query — with `?graph=` alone it loads, selects nothing, and sits on
// an empty canvas showing "Type your query here to start".
const FALKOR_GRAPH = 'alpha_org';

// Served from its own mirror port (vite.config.ts `falkorMirror`), not a
// sub-path of this app — the embedded app's client-side nav (e.g. its
// unauthenticated `/login` redirect) resolves against the real browser
// origin, which only works if that origin has no path prefix to escape.
const FALKOR_MIRROR_ORIGIN = `${window.location.protocol}//${window.location.hostname}:3009`;

function falkorUrl(query: string): string {
  return `${FALKOR_MIRROR_ORIGIN}/graph?graph=${FALKOR_GRAPH}&query=${encodeURIComponent(query)}`;
}

const PRESETS: { label: string; query: string }[] = [
  { label: 'Everything', query: 'MATCH (n) RETURN n' },
  { label: 'Who did what', query: 'MATCH (a:Agent)-[e:EXECUTED]->(t:Tool) RETURN a, e, t' },
  { label: 'Failures only', query: 'MATCH (a:Agent)-[e:EXECUTED]->(t:Tool) WHERE e.ok = false RETURN a, e, t' },
  { label: 'Delegation', query: 'MATCH (a:Agent)-[e:ASSIGNED]->(b:Agent) RETURN a, e, b' },
  { label: 'Agent capabilities', query: 'MATCH (a:Agent)-[e:CAN_USE]->(t:Tool) RETURN a, e, t' },
  { label: 'Heartbeat turns', query: 'MATCH (a:Agent)-[e:DECIDED]->(x) RETURN a, e, x' },
];

/**
 * Force-directed layout, hand-rolled.
 *
 * The dashboard deliberately carries almost no dependencies (react + router +
 * mermaid), so pulling in d3-force for one page isn't worth it. This is the
 * standard velocity-Verlet loop: every pair repels (Coulomb), every edge pulls
 * (Hooke), a weak force draws everything toward the centre, and velocity decays
 * so it settles instead of oscillating forever.
 */
function useForceSimulation(nodes: GraphNode[], edges: GraphEdge[]) {
  const [sim, setSim] = useState<SimNode[]>([]);
  const simRef = useRef<SimNode[]>([]);
  const frame = useRef<number | null>(null);
  const alpha = useRef(1);

  // Rebuild when the topology changes, preserving positions of nodes we already
  // had so a 10s refresh doesn't teleport the whole picture.
  useEffect(() => {
    const prev = new Map(simRef.current.map((n) => [n.id, n]));
    const next: SimNode[] = nodes.map((n, i) => {
      const old = prev.get(n.id);
      if (old) return { ...n, x: old.x, y: old.y, vx: old.vx, vy: old.vy, pinned: old.pinned };
      // Seed on a ring — starting everything at the exact centre makes the
      // repulsion step explode on the first frame.
      const a = (i / Math.max(nodes.length, 1)) * Math.PI * 2;
      return { ...n, x: W / 2 + Math.cos(a) * 260, y: H / 2 + Math.sin(a) * 260, vx: 0, vy: 0 };
    });
    simRef.current = next;
    alpha.current = 1;
    setSim(next);
  }, [nodes, edges]);

  useEffect(() => {
    const adjacency = edges.map((e) => ({ s: e.source, t: e.target }));

    function step() {
      const list = simRef.current;
      if (list.length === 0) {
        frame.current = requestAnimationFrame(step);
        return;
      }
      const a = alpha.current;
      const byId = new Map(list.map((n) => [n.id, n]));

      // Repulsion — O(n²), fine for the few hundred nodes this graph holds.
      for (let i = 0; i < list.length; i++) {
        for (let j = i + 1; j < list.length; j++) {
          const p = list[i];
          const q = list[j];
          let dx = q.x - p.x;
          let dy = q.y - p.y;
          let d2 = dx * dx + dy * dy;
          if (d2 < 1) {
            dx = Math.random() - 0.5;
            dy = Math.random() - 0.5;
            d2 = 1;
          }
          const d = Math.sqrt(d2);
          const force = 5200 / d2;
          const fx = (dx / d) * force;
          const fy = (dy / d) * force;
          p.vx -= fx;
          p.vy -= fy;
          q.vx += fx;
          q.vy += fy;
        }
      }

      // Springs along edges.
      for (const { s, t } of adjacency) {
        const p = byId.get(s);
        const q = byId.get(t);
        if (!p || !q) continue;
        const dx = q.x - p.x;
        const dy = q.y - p.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = (d - 130) * 0.014;
        const fx = (dx / d) * force;
        const fy = (dy / d) * force;
        p.vx += fx;
        p.vy += fy;
        q.vx -= fx;
        q.vy -= fy;
      }

      for (const n of list) {
        if (n.pinned) {
          n.vx = 0;
          n.vy = 0;
          continue;
        }
        n.vx += (W / 2 - n.x) * 0.0022;   // gentle gravity to the middle
        n.vy += (H / 2 - n.y) * 0.0022;
        n.vx *= 0.82;                      // damping
        n.vy *= 0.82;
        n.x += n.vx * a;
        n.y += n.vy * a;
      }

      alpha.current = Math.max(a * 0.995, 0.02);
      setSim([...list]);
      frame.current = requestAnimationFrame(step);
    }

    frame.current = requestAnimationFrame(step);
    return () => {
      if (frame.current) cancelAnimationFrame(frame.current);
    };
  }, [edges]);

  const reheat = useCallback(() => {
    alpha.current = 1;
    for (const n of simRef.current) n.pinned = false;
  }, []);

  const setPosition = useCallback((id: number, x: number, y: number, pinned: boolean) => {
    const n = simRef.current.find((m) => m.id === id);
    if (!n) return;
    n.x = x;
    n.y = y;
    n.vx = 0;
    n.vy = 0;
    n.pinned = pinned;
    setSim([...simRef.current]);
  }, []);

  return { sim, reheat, setPosition };
}

export function GraphPage() {
  const [raw, setRaw] = useState<GraphData | null>(null);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [running, setRunning] = useState(false);
  const [view, setView] = useState<'graph' | 'table'>('graph');
  // 'falkor' = the real FalkorDB Browser embedded via the vite-dev-only mirror
  // (vite.config.ts `falkorMirror`, full feature set); 'native' = the built-in
  // view below, which keeps working if the browser container is down or the
  // mirror isn't available — as in this production build, where the mirror
  // (a Vite `configureServer` hook) never runs at all, so 'falkor' mode would
  // just show "localhost refused to connect".
  const isDev = (import.meta as unknown as { env: Record<string, unknown> }).env?.DEV === true;
  const [mode, setMode] = useState<'falkor' | 'native'>(isDev ? 'falkor' : 'native');
  // Query the embedded browser opens with. "MATCH (n) RETURN n" draws every
  // agent and tool — the same URL shape that works when you open :3002 directly.
  const [falkorQuery, setFalkorQuery] = useState('MATCH (n) RETURN n');
  const [hiddenEdges, setHiddenEdges] = useState<Set<string>>(new Set());
  const [hiddenLabels, setHiddenLabels] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [live, setLive] = useState(true);
  // Bumped to force the embedded FalkorDB Browser iframe to reload — unlike
  // the Built-in view (which cheaply polls /org/graph), the real browser is a
  // full third-party SPA that reads its query from the URL once on mount and
  // never refetches. Reloading it on a timer (tried first) forces its own
  // internal graph view to restart its physics/animation from scratch every
  // cycle, wiping zoom/pan/selection and never letting it settle — worse than
  // the staleness it was meant to fix. Manual refresh only, via the button
  // below, rather than an automatic interval.
  const [falkorNonce, setFalkorNonce] = useState(0);

  // Viewport (zoom + pan)
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragNode = useRef<number | null>(null);
  const panning = useRef<{ x: number; y: number } | null>(null);

  const loadAll = useCallback(async () => {
    try {
      const d = await apiGet<GraphData>('/org/graph');
      setRaw(d);
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Live refresh only while showing the default view — a custom query shouldn't
  // be silently replaced underneath you.
  useEffect(() => {
    if (!live || query.trim()) return;
    const t = window.setInterval(loadAll, 10_000);
    return () => window.clearInterval(t);
  }, [live, query, loadAll]);

  async function runQuery(q: string) {
    const text = q.trim();
    setQuery(text);
    if (!text) {
      loadAll();
      return;
    }
    setRunning(true);
    try {
      const d = await apiPost<GraphData>('/org/graph/query', { query: text });
      setRaw(d);
      setError(d.error ?? '');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }

  const nodes = useMemo(
    () => (raw?.nodes ?? []).filter((n) => !hiddenLabels.has(n.type)),
    [raw, hiddenLabels],
  );
  const nodeIds = useMemo(() => new Set(nodes.map((n) => n.id)), [nodes]);
  const edges = useMemo(
    () =>
      (raw?.edges ?? []).filter(
        (e) => !hiddenEdges.has(e.type) && nodeIds.has(e.source) && nodeIds.has(e.target),
      ),
    [raw, hiddenEdges, nodeIds],
  );

  const { sim, reheat, setPosition } = useForceSimulation(nodes, edges);
  const byId = useMemo(() => new Map(sim.map((n) => [n.id, n])), [sim]);

  const labelCounts = useMemo(() => {
    const c = new Map<string, number>();
    for (const n of raw?.nodes ?? []) c.set(n.type, (c.get(n.type) ?? 0) + 1);
    return [...c.entries()].sort((a, b) => b[1] - a[1]);
  }, [raw]);

  const edgeCounts = useMemo(() => {
    const c = new Map<string, number>();
    for (const e of raw?.edges ?? []) c.set(e.type, (c.get(e.type) ?? 0) + 1);
    return [...c.entries()].sort((a, b) => b[1] - a[1]);
  }, [raw]);

  // ── Pointer interaction: drag nodes, pan background, wheel to zoom ─────────

  function toSvg(evt: React.PointerEvent | React.WheelEvent) {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const rect = svg.getBoundingClientRect();
    const sx = (evt.clientX - rect.left) / rect.width * W;
    const sy = (evt.clientY - rect.top) / rect.height * H;
    return { x: (sx - pan.x) / zoom, y: (sy - pan.y) / zoom };
  }

  function onPointerDownNode(evt: React.PointerEvent, id: number) {
    evt.stopPropagation();
    (evt.target as Element).setPointerCapture?.(evt.pointerId);
    dragNode.current = id;
  }

  function onPointerMove(evt: React.PointerEvent) {
    if (dragNode.current !== null) {
      const p = toSvg(evt);
      setPosition(dragNode.current, p.x, p.y, true);
      return;
    }
    if (panning.current) {
      setPan({ x: evt.clientX - panning.current.x, y: evt.clientY - panning.current.y });
    }
  }

  function onPointerUp() {
    dragNode.current = null;
    panning.current = null;
  }

  function onPointerDownBg(evt: React.PointerEvent) {
    panning.current = { x: evt.clientX - pan.x, y: evt.clientY - pan.y };
  }

  function onWheel(evt: React.WheelEvent) {
    const factor = evt.deltaY < 0 ? 1.12 : 1 / 1.12;
    setZoom((z) => Math.min(4, Math.max(0.2, z * factor)));
  }

  function toggle(set: Set<string>, setter: (s: Set<string>) => void, key: string) {
    const next = new Set(set);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setter(next);
  }

  const related = useMemo(() => {
    if (!selected || !raw) return [];
    return (raw.edges ?? [])
      .filter((e) => e.source === selected.id || e.target === selected.id)
      .map((e) => {
        const otherId = e.source === selected.id ? e.target : e.source;
        const other = (raw.nodes ?? []).find((n) => n.id === otherId);
        return { edge: e, other, outgoing: e.source === selected.id };
      })
      .filter((r) => r.other);
  }, [selected, raw]);

  return (
    <div className="p-4 md:p-6 text-slate-200">
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-1">
        <h1 className="text-2xl font-bold">🕸️ Knowledge Graph</h1>
        <div className="flex items-center gap-3 text-xs">
          <div className="flex rounded-lg border border-slate-700 overflow-hidden">
            <button onClick={() => setMode('falkor')}
                    className={`px-3 py-1 ${mode === 'falkor' ? 'bg-slate-700 text-slate-100' : 'text-slate-400 hover:bg-slate-800'}`}>
              FalkorDB Browser
            </button>
            <button onClick={() => setMode('native')}
                    className={`px-3 py-1 ${mode === 'native' ? 'bg-slate-700 text-slate-100' : 'text-slate-400 hover:bg-slate-800'}`}>
              Built-in
            </button>
          </div>
          {mode === 'native' && (
            <>
              <label className="flex items-center gap-1.5 text-slate-400">
                <input type="checkbox" checked={live} onChange={(e) => setLive(e.target.checked)} />
                live (10s)
              </label>
              <button onClick={() => setView(view === 'graph' ? 'table' : 'graph')}
                      className="px-2 py-1 rounded border border-slate-700 hover:bg-slate-800">
                {view === 'graph' ? '▦ Table' : '🕸 Graph'}
              </button>
            </>
          )}
        </div>
      </div>

      {mode === 'falkor' && (
        <div>
          <p className="text-sm text-slate-400 mb-2">
            The full FalkorDB Browser, embedded, on graph{' '}
            <code className="text-slate-300">{FALKOR_GRAPH}</code>. Pick a view below (it reloads the
            frame with that query), then use the browser's own query box for anything else. The frame
            never refetches on its own — the underlying graph keeps getting written to live, but this
            view only shows it as of the last load. Hit <b>🔄 Refresh</b> to pull the latest.
          </p>
          <div className="flex flex-wrap gap-1.5 mb-3">
            {PRESETS.map((p) => (
              <button
                key={p.label}
                onClick={() => setFalkorQuery(p.query)}
                className={`px-2 py-0.5 text-xs rounded border ${
                  falkorQuery === p.query
                    ? 'border-slate-400 bg-slate-700 text-slate-100'
                    : 'border-slate-700 text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                }`}
              >
                {p.label}
              </button>
            ))}
            <button onClick={() => setFalkorNonce((n) => n + 1)}
                    className="px-2 py-0.5 text-xs rounded border border-slate-700 text-slate-400 hover:bg-slate-800">
              🔄 Refresh
            </button>
            <a href={`${window.location.protocol}//${window.location.hostname}:3002/graph?graph=${FALKOR_GRAPH}&query=${encodeURIComponent(falkorQuery)}`}
               target="_blank" rel="noreferrer"
               className="px-2 py-0.5 text-xs rounded border border-slate-700 text-slate-400 hover:bg-slate-800">
              ↗ own tab
            </a>
          </div>
          <div className="rounded-xl border border-slate-800 overflow-hidden bg-slate-950">
            <iframe
              // key: force a full reload when the query changes, or every 10s
              // while "live" is on (falkorNonce) — the browser reads its query
              // from the URL on mount, not reactively, so it never sees new
              // graph writes on its own.
              key={`${falkorQuery}::${falkorNonce}`}
              src={falkorUrl(falkorQuery)}
              title="FalkorDB Browser"
              className="w-full"
              style={{ height: '80vh', border: 0 }}
            />
          </div>
          <p className="text-xs text-slate-600 mt-2">
            Served through the dev proxy at <code>/falkor</code> (the browser sets
            <code> X-Frame-Options: DENY</code>, which the proxy strips locally). If this stays blank,
            the container may be down — check <code>docker compose ps falkordb-browser</code>. The{' '}
            <button className="underline text-slate-400" onClick={() => setMode('native')}>Built-in</button>{' '}
            view always works and needs no proxy.
          </p>
        </div>
      )}

      {mode === 'native' && (
      <>
      <p className="text-sm text-slate-400 mb-3">
        Who works here, what each agent can run, and what they actually did — live from FalkorDB.
      </p>

      {/* Query bar */}
      <div className="mb-3">
        <div className="flex gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && runQuery(query)}
            placeholder="MATCH (n) RETURN n     — read-only Cypher, Enter to run"
            className="flex-1 px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 font-mono text-sm
                       focus:outline-none focus:border-slate-500"
          />
          <button onClick={() => runQuery(query)} disabled={running}
                  className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-sm font-medium">
            {running ? 'Running…' : 'Run'}
          </button>
          <button onClick={() => { setQuery(''); loadAll(); }}
                  className="px-3 py-2 rounded-lg border border-slate-700 hover:bg-slate-800 text-sm">
            Reset
          </button>
        </div>
        <div className="flex flex-wrap gap-1.5 mt-2">
          {PRESETS.map((p) => (
            <button key={p.label} onClick={() => runQuery(p.query)}
                    className="px-2 py-0.5 text-xs rounded border border-slate-700 text-slate-400 hover:bg-slate-800 hover:text-slate-200">
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-800 bg-red-950/40 p-3 text-sm text-red-300 mb-3">{error}</div>
      )}
      {raw && !raw.available && (
        <div className="rounded-lg border border-amber-800 bg-amber-950/30 p-4 text-sm text-amber-200 mb-3">
          <strong>Graph offline.</strong> {raw.note}
        </div>
      )}

      {/* Filters */}
      {raw?.available && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mb-3 text-xs">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-slate-500">labels:</span>
            {labelCounts.map(([type, n]) => {
              const on = !hiddenLabels.has(type);
              return (
                <button key={type} onClick={() => toggle(hiddenLabels, setHiddenLabels, type)}
                        className={`px-2 py-0.5 rounded border ${on ? 'border-slate-500 bg-slate-800' : 'border-slate-800 text-slate-600'}`}>
                  <span className="inline-block w-2.5 h-2.5 rounded-full mr-1 align-middle"
                        style={{ background: on ? (NODE_COLOR[type] ?? DEFAULT_NODE_COLOR) : '#334155' }} />
                  {type} ({n})
                </button>
              );
            })}
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-slate-500">edges:</span>
            {edgeCounts.map(([type, n]) => {
              const on = !hiddenEdges.has(type);
              return (
                <button key={type} onClick={() => toggle(hiddenEdges, setHiddenEdges, type)}
                        className={`px-2 py-0.5 rounded border ${on ? 'border-slate-500 bg-slate-800' : 'border-slate-800 text-slate-600'}`}>
                  <span className="inline-block w-2.5 h-2.5 rounded-full mr-1 align-middle"
                        style={{ background: on ? (EDGE_STYLE[type]?.color ?? '#64748b') : '#334155' }} />
                  {type} ({n})
                </button>
              );
            })}
          </div>
          <div className="flex items-center gap-1.5 ml-auto">
            <button onClick={() => setZoom((z) => Math.min(4, z * 1.2))} className="px-2 py-0.5 rounded border border-slate-700">＋</button>
            <button onClick={() => setZoom((z) => Math.max(0.2, z / 1.2))} className="px-2 py-0.5 rounded border border-slate-700">－</button>
            <button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); reheat(); }}
                    className="px-2 py-0.5 rounded border border-slate-700">Re-layout</button>
            <span className="text-slate-600">{Math.round(zoom * 100)}%</span>
          </div>
        </div>
      )}

      {view === 'table' ? (
        <div className="rounded-xl border border-slate-800 bg-slate-950 overflow-auto max-h-[720px]">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-slate-900">
              <tr>
                {(raw?.columns?.length ? raw.columns : ['type', 'name', 'role']).map((c) => (
                  <th key={c} className="text-left px-3 py-2 font-semibold text-slate-300">{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(raw?.rows?.length
                ? raw.rows
                : (raw?.nodes ?? []).map((n) => [n.type, n.name, n.role ?? ''])
              ).map((row, i) => (
                <tr key={i} className="border-t border-slate-800/60 hover:bg-slate-900/50">
                  {(row as unknown[]).map((cell, j) => (
                    <td key={j} className="px-3 py-1.5 text-slate-300 font-mono">
                      {typeof cell === 'object' ? JSON.stringify(cell) : String(cell ?? '')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-4">
          <div className="rounded-xl border border-slate-800 bg-slate-950 overflow-hidden">
            <svg
              ref={svgRef}
              viewBox={`0 0 ${W} ${H}`}
              className="w-full touch-none select-none"
              style={{ cursor: panning.current ? 'grabbing' : 'grab' }}
              onPointerDown={onPointerDownBg}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
              onPointerLeave={onPointerUp}
              onWheel={onWheel}
            >
              <defs>
                {Object.entries(EDGE_STYLE).map(([type, s]) => (
                  <marker key={type} id={`ar-${type}`} viewBox="0 0 10 10" refX="10" refY="5"
                          markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                    <path d="M 0 0 L 10 5 L 0 10 z" fill={s.color} />
                  </marker>
                ))}
                <marker id="ar-default" viewBox="0 0 10 10" refX="10" refY="5"
                        markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
                </marker>
              </defs>

              <g transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}>
                {edges.map((e, i) => {
                  const a = byId.get(e.source);
                  const b = byId.get(e.target);
                  if (!a || !b) return null;
                  const s = EDGE_STYLE[e.type] ?? { color: '#64748b' };
                  const failed = e.type === 'EXECUTED' && e.ok === false;
                  const dim = selected && selected.id !== e.source && selected.id !== e.target ? 0.07 : 1;
                  return (
                    <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                          stroke={failed ? '#ef4444' : s.color}
                          strokeWidth={failed ? 2.2 : s.faint ? 0.7 : 1.6}
                          strokeDasharray={s.dash}
                          opacity={(s.faint ? 0.3 : 0.75) * dim}
                          markerEnd={`url(#ar-${EDGE_STYLE[e.type] ? e.type : 'default'})`} />
                  );
                })}

                {sim.map((n) => {
                  const isAgent = n.type === 'Agent';
                  const color = NODE_COLOR[n.type] ?? DEFAULT_NODE_COLOR;
                  const active = selected?.id === n.id;
                  const r = isAgent ? 24 : 8;
                  return (
                    <g key={n.id}
                       onPointerDown={(e) => onPointerDownNode(e, n.id)}
                       onClick={(e) => { e.stopPropagation(); setSelected(active ? null : n); }}
                       style={{ cursor: 'pointer' }}>
                      <circle cx={n.x} cy={n.y} r={r} fill={color}
                              stroke={active ? '#fff' : n.pinned ? '#94a3b8' : '#0f172a'}
                              strokeWidth={active ? 3 : n.pinned ? 2 : 1.5} />
                      <text x={n.x} y={isAgent ? n.y + r + 16 : n.y - r - 5} textAnchor="middle"
                            fontSize={isAgent ? 15 : 10}
                            fontWeight={isAgent ? 700 : 400}
                            fill={isAgent ? '#f1f5f9' : '#94a3b8'}
                            style={{ pointerEvents: 'none' }}>
                        {n.name}
                      </text>
                      {isAgent && n.role && (
                        <text x={n.x} y={n.y + r + 30} textAnchor="middle" fontSize={10} fill="#64748b"
                              style={{ pointerEvents: 'none' }}>{n.role}</text>
                      )}
                    </g>
                  );
                })}
              </g>
            </svg>
            <div className="px-3 py-1.5 text-[11px] text-slate-600 border-t border-slate-800">
              drag a node to pin it · drag the background to pan · scroll to zoom · Re-layout unpins everything
            </div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4 text-sm">
            {!selected ? (
              <>
                <p className="text-slate-400 mb-3">Click any node to inspect it.</p>
                <dl className="space-y-1.5 text-xs text-slate-400">
                  <div><strong className="text-slate-300">CAN_USE</strong> — a tool the agent is capable of running (the static wiring).</div>
                  <div><strong className="text-slate-300">EXECUTED</strong> — a tool actually run. <span className="text-red-400">Red = failed.</span></div>
                  <div><strong className="text-slate-300">ASSIGNED</strong> — one agent delegated work to another.</div>
                  <div><strong className="text-slate-300">DECIDED</strong> — a proactive heartbeat turn.</div>
                </dl>
              </>
            ) : (
              <>
                <div className="flex items-center gap-2 mb-1">
                  <span className="inline-block w-3 h-3 rounded-full"
                        style={{ background: NODE_COLOR[selected.type] ?? DEFAULT_NODE_COLOR }} />
                  <h2 className="font-bold text-slate-100">{selected.name}</h2>
                </div>
                <p className="text-xs text-slate-500 mb-3">
                  {selected.type}{selected.role ? ` · ${selected.role}` : ''}
                </p>
                <p className="text-xs text-slate-500 mb-2">{related.length} connection(s)</p>
                <ul className="space-y-1.5 max-h-[520px] overflow-y-auto pr-1">
                  {related.map((r, i) => (
                    <li key={i} className="text-xs">
                      <span className="text-slate-500">{r.outgoing ? '→' : '←'}</span>{' '}
                      <span style={{ color: EDGE_STYLE[r.edge.type]?.color ?? '#94a3b8' }}>{r.edge.type}</span>{' '}
                      <button className="text-slate-200 underline decoration-dotted"
                              onClick={() => r.other && setSelected(r.other)}>
                        {r.other!.name}
                      </button>
                      {r.edge.ok === false && <span className="text-red-400"> (failed)</span>}
                      {r.edge.label && (
                        <div className="text-slate-500 pl-4 break-words" title={r.edge.label}>{r.edge.label}</div>
                      )}
                    </li>
                  ))}
                </ul>
                <button className="mt-3 text-xs text-slate-400 underline" onClick={() => setSelected(null)}>
                  clear selection
                </button>
              </>
            )}
          </div>
        </div>
      )}
      </>
      )}
    </div>
  );
}
