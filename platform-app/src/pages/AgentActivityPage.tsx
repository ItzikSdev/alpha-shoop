import { useEffect, useRef, useState } from 'react';
import { apiGet } from '../api/client';

// ── Types ────────────────────────────────────────────────────────────────────

interface AgentRun {
  run_id: string;
  agent_name: string;
  task: string;
  store_slug: string;
  ticket_id: string;
  status: 'running' | 'done' | 'error' | 'max_steps' | 'killed';
  started_at: string;
  finished_at: string | null;
  steps: number;
  final_text: string;
}

interface AgentStep {
  id: number;
  run_id: string;
  seq: number;
  kind: 'status' | 'thought' | 'tool_call' | 'tool_result';
  tool_name: string;
  text: string;
  args_json: string;
  result_json: string;
  ok: number | null;
  ts: string;
}

interface RosterAgent {
  name: string;
  role: string;
  status: string;
}

// ── Constants ────────────────────────────────────────────────────────────────

const SSE_BASE = `${window.location.protocol}//${window.location.hostname}:8000/api/v1`;

const STATUS_STYLE: Record<string, string> = {
  live: 'text-green-400 bg-green-400/10 border-green-400/30',
  running: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
  done: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30',
  error: 'text-red-400 bg-red-400/10 border-red-400/30',
  max_steps: 'text-orange-400 bg-orange-400/10 border-orange-400/30',
  killed: 'text-orange-400 bg-orange-400/10 border-orange-400/30',
  idle: 'text-gray-500 bg-gray-500/10 border-gray-500/30',
};

const AGENT_COLORS: Record<string, string> = { Sol: '#818cf8' };
function agentColor(name: string): string {
  if (AGENT_COLORS[name]) return AGENT_COLORS[name];
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return `hsl(${hash % 360}, 65%, 65%)`;
}

const GROUP_META: Record<string, { label: string; icon: string; color: string; x: number; y: number }> = {
  store_code: { label: 'Store Code', icon: '🗂️', color: '#6366f1', x: 200, y: 30 },
  shopify: { label: 'Shopify', icon: '🛍️', color: '#10b981', x: 357, y: 137 },
  sourcing: { label: 'Sourcing (CJ)', icon: '📦', color: '#f59e0b', x: 300, y: 320 },
  knowledge: { label: 'RAG / Knowledge', icon: '📚', color: '#38bdf8', x: 100, y: 320 },
  comms: { label: 'Comms', icon: '✉️', color: '#ec4899', x: 43, y: 137 },
};
const CENTER = { x: 200, y: 175 };

const KIND_META: Record<string, { icon: string; label: string }> = {
  status: { icon: '🚀', label: 'Status' },
  thought: { icon: '💭', label: 'Thought' },
  tool_call: { icon: '🔧', label: 'Tool call' },
  tool_result: { icon: '✅', label: 'Result' },
};

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return iso;
  }
}

// Wrap a caption into up to `maxLines` short lines for the SVG center label — plain
// greedy word-wrap, no measurement (fixed-width font-ish approximation is fine at this size).
function wrapCaption(text: string, charsPerLine = 15, maxLines = 2): string[] {
  const words = text.replace(/\s+/g, ' ').trim().split(' ');
  const lines: string[] = [];
  let cur = '';
  for (const w of words) {
    if ((cur + ' ' + w).trim().length > charsPerLine) {
      if (cur) lines.push(cur);
      cur = w;
      if (lines.length === maxLines) break;
    } else {
      cur = (cur + ' ' + w).trim();
    }
  }
  if (lines.length < maxLines && cur) lines.push(cur);
  if (lines.length === maxLines && words.join(' ').length > lines.join(' ').length) {
    lines[maxLines - 1] = lines[maxLines - 1].replace(/.{0,2}$/, '…');
  }
  return lines;
}

// ── Tool graph (custom animated SVG) — the agent's node shows what it's doing,
// right in the middle, and the edge to whichever tool is active pulses live. ──

function ToolGraph({ agentName, activeTool, activeStepId, toolGroups, caption }: {
  agentName: string; activeTool: string | null; activeStepId: number | null;
  toolGroups: Record<string, string[]>; caption: string;
}) {
  const activeGroup = activeTool
    ? Object.entries(toolGroups).find(([, tools]) => tools.includes(activeTool))?.[0] ?? null
    : null;
  // Keying the active node/edge on the triggering step id forces React to remount them on
  // EVERY tool call — including back-to-back calls to the same tool/group — so the flash
  // animation always restarts and the diagram visibly reacts each time the agent switches
  // tasks, instead of just staying lit on a group it was already glowing on.
  const flashKey = activeGroup ? `${activeGroup}-${activeStepId ?? 0}` : 'none';
  const captionLines = wrapCaption(caption);

  return (
    <div>
      <style>{`
        @keyframes solPulse { 0%,100% { opacity: 0.55; } 50% { opacity: 1; } }
        @keyframes solFlash { 0% { transform: scale(1.35); filter: brightness(1.8); } 100% { transform: scale(1); filter: brightness(1); } }
        @keyframes solDash { to { stroke-dashoffset: -24; } }
        .sol-edge-active { stroke-width: 4; animation: solDash 0.6s linear infinite, solFlash 0.5s ease-out; }
        .sol-node-active circle { animation: solPulse 1.1s ease-in-out infinite; }
        .sol-node-active { transform-box: fill-box; transform-origin: center; animation: solFlash 0.5s ease-out; }
      `}</style>
      <svg viewBox="0 0 400 380" className="w-full h-auto">
        {Object.entries(GROUP_META).map(([id, meta]) => {
          const active = id === activeGroup;
          return (
            <line
              key={active ? `${id}-${flashKey}` : id}
              x1={CENTER.x} y1={CENTER.y} x2={meta.x} y2={meta.y}
              stroke={active ? meta.color : '#374151'}
              strokeDasharray={active ? '7 5' : undefined}
              className={active ? 'sol-edge-active' : ''}
            />
          );
        })}

        {/* Agent node — enlarged center: name + a live 2-line caption of what it's doing now */}
        <g key={flashKey === 'none' ? 'agent-idle' : `agent-${flashKey}`} className={activeTool ? 'sol-node-active' : undefined}>
          <circle cx={CENTER.x} cy={CENTER.y} r={58} fill="#1e293b" stroke="#818cf8" strokeWidth={2.5} />
          <text x={CENTER.x} y={CENTER.y - 32} textAnchor="middle" fontSize="15" fill="#e2e8f0" fontWeight={700}>
            🛰️ {agentName}
          </text>
          {captionLines.map((line, i) => (
            <text key={i} x={CENTER.x} y={CENTER.y - 4 + i * 13} textAnchor="middle" fontSize="10" fill="#94a3b8">
              {line}
            </text>
          ))}
        </g>

        {Object.entries(GROUP_META).map(([id, meta]) => {
          const active = id === activeGroup;
          return (
            <g key={active ? `${id}-${flashKey}` : id} className={active ? 'sol-node-active' : ''}>
              <circle
                cx={meta.x} cy={meta.y} r={32}
                fill={active ? meta.color + '33' : '#111827'}
                stroke={active ? meta.color : '#374151'}
                strokeWidth={active ? 3 : 1.5}
              />
              <text x={meta.x} y={meta.y + 6} textAnchor="middle" fontSize="18">{meta.icon}</text>
              <text x={meta.x} y={meta.y + 48} textAnchor="middle" fontSize="10" fill={active ? meta.color : '#6b7280'} fontWeight={active ? 700 : 400}>
                {meta.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ── Timeline step card ───────────────────────────────────────────────────────

function StepCard({ step }: { step: AgentStep }) {
  const [open, setOpen] = useState(false);
  const meta = KIND_META[step.kind] ?? { icon: '·', label: step.kind };
  const jsonDetail = step.kind === 'tool_call' ? step.args_json : step.kind === 'tool_result' ? step.result_json : '';
  const isResult = step.kind === 'tool_result';
  const failed = isResult && step.ok === 0;
  // The preview line is CSS-truncated to one line — anything long enough to plausibly
  // be cut (a full thought, a long task/status line) needs a way to read it in full.
  const expandable = Boolean(jsonDetail) || step.text.length > 70;

  return (
    <div className="relative pl-8" style={{ animation: 'stepIn 260ms ease-out' }}>
      <div
        className={`absolute left-1.5 top-1.5 w-3 h-3 rounded-full border-2 ${
          failed ? 'bg-red-500 border-red-400' : isResult ? 'bg-emerald-500 border-emerald-400' : 'bg-gray-700 border-gray-600'
        }`}
      />
      <div className={`rounded-lg border p-3.5 mb-3 ${failed ? 'border-red-900/50 bg-red-950/20' : 'border-gray-800 bg-gray-900/40'}`}>
        <button
          onClick={() => expandable && setOpen((o) => !o)}
          className="w-full min-w-0 text-left"
        >
          {/* Row 1: short, fixed-size bits only — never fights the text for space */}
          <div className="flex items-center gap-2">
            <span className="text-base shrink-0">{meta.icon}</span>
            {step.tool_name && (
              <span className="font-mono text-xs text-indigo-300 shrink-0 truncate">{step.tool_name}</span>
            )}
            <span className="text-xs text-gray-600 shrink-0 ml-auto">{fmtTime(step.ts)}</span>
            {expandable && <span className="text-gray-700 shrink-0">{open ? '▾' : '▸'}</span>}
          </div>
          {/* Row 2: the text gets the full card width to truncate against, independent of row 1 */}
          <div className="mt-1 text-sm text-gray-300 truncate min-w-0">{step.text}</div>
        </button>
        {open && (
          <div className="mt-2 pt-2 border-t border-gray-800 space-y-2">
            <p className="text-xs text-gray-300 whitespace-pre-wrap break-words">{step.text}</p>
            {jsonDetail && (
              <pre className="text-[11px] text-gray-400 font-mono whitespace-pre-wrap break-words max-h-64 overflow-y-auto">
                {(() => {
                  try {
                    return JSON.stringify(JSON.parse(jsonDetail), null, 2);
                  } catch {
                    return jsonDetail;
                  }
                })()}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Task line (the run's task text — expandable if it doesn't fit one line) ──

function TaskLine({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const expandable = text.length > 90;
  return (
    <button
      onClick={() => expandable && setOpen((o) => !o)}
      className="mt-1.5 w-full text-left flex items-start gap-1.5"
    >
      <p className={`text-sm text-gray-200 flex-1 min-w-0 ${open ? 'whitespace-pre-wrap break-words' : 'truncate'}`}>
        {text}
      </p>
      {expandable && <span className="text-[10px] text-gray-600 shrink-0 mt-0.5">{open ? '▾ less' : '▸ show all'}</span>}
    </button>
  );
}

// ── One agent's always-on live card: header + scrolling timeline + tool graph ──

function AgentLiveCard({ agent, latestRun, toolGroups }: {
  agent: RosterAgent; latestRun: AgentRun | null; toolGroups: Record<string, string[]>;
}) {
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [runStatus, setRunStatus] = useState<string>('idle');
  const esRef = useRef<EventSource | null>(null);
  const connectedRunId = useRef<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!latestRun || connectedRunId.current === latestRun.run_id) return;
    esRef.current?.close();
    connectedRunId.current = latestRun.run_id;
    setSteps([]);
    setRunStatus('running');
    const es = new EventSource(`${SSE_BASE}/org/agents/runs/${latestRun.run_id}/stream`);
    es.onmessage = (ev) => {
      const data = JSON.parse(ev.data);
      if (data.type === 'step') {
        const { type: _type, ...step } = data;
        setSteps((prev) => [...prev, step as AgentStep]);
      } else if (data.type === 'done') {
        setRunStatus(data.status);
      } else if (data.type === 'error') {
        setRunStatus('error');
      }
    };
    es.onerror = () => {};
    esRef.current = es;
  }, [latestRun]);

  useEffect(() => () => { esRef.current?.close(); }, []);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [steps.length]);

  const isLive = runStatus === 'running';
  const lastStep = steps.length ? steps[steps.length - 1] : null;
  const lastToolCall = [...steps].reverse().find((s) => s.kind === 'tool_call');
  const lastToolStep = [...steps].reverse().find((s) => s.kind === 'tool_call' || s.kind === 'tool_result');
  const activeTool = isLive ? lastToolStep?.tool_name ?? null : null;
  const activeStepId = isLive ? lastToolCall?.id ?? null : null;
  const caption = isLive ? (lastStep?.text ?? 'starting…') : latestRun ? 'idle' : 'no runs yet';
  const displayStatus = isLive ? 'live' : latestRun ? runStatus : agent.status;

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/40 overflow-hidden">
      <div className="p-5 border-b border-gray-800">
        <div className="flex items-center gap-2.5 flex-wrap">
          <span className="text-2xl">🛰️</span>
          <span className="text-lg font-bold text-gray-100" style={{ color: agentColor(agent.name) }}>{agent.name}</span>
          <span className="text-sm text-gray-500">{agent.role}</span>
          <span className={`ml-auto text-xs px-2.5 py-1 rounded border ${STATUS_STYLE[displayStatus] || STATUS_STYLE.idle}`}>
            {displayStatus}
            {isLive && <span className="ml-1 inline-block w-1.5 h-1.5 rounded-full bg-current animate-pulse" />}
          </span>
        </div>
        {latestRun ? (
          <>
            <div className="mt-1.5 flex items-center gap-2 text-xs text-gray-500">
              <span>🏪 {latestRun.store_slug}</span>
              {latestRun.ticket_id && <span className="text-indigo-400">🎫 {latestRun.ticket_id}</span>}
              <span className="ml-auto font-mono text-gray-600">{latestRun.run_id}</span>
            </div>
            <TaskLine text={latestRun.task} />
          </>
        ) : (
          <p className="mt-1.5 text-xs text-gray-600">No runs yet — this card lights up the moment a task starts (Slack, a ticket, or the heartbeat loop).</p>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_560px]">
        <div className="min-w-0 p-5 max-h-[36rem] overflow-y-auto overflow-x-hidden">
          {steps.length === 0 && <div className="text-xs text-gray-600 pl-1">Waiting for the first step…</div>}
          <div className="relative">
            <div className="absolute left-[13px] top-2 bottom-2 w-0.5 bg-gray-700" />
            {steps.map((s) => <StepCard key={s.id} step={s} />)}
            <div ref={bottomRef} />
          </div>
        </div>
        <div className="p-5 flex items-center border-t lg:border-t-0 lg:border-l border-gray-800">
          <ToolGraph agentName={agent.name} activeTool={activeTool} activeStepId={activeStepId} toolGroups={toolGroups} caption={caption} />
        </div>
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export function AgentActivityPage() {
  const [roster, setRoster] = useState<RosterAgent[]>([]);
  const [latestByAgent, setLatestByAgent] = useState<Record<string, AgentRun>>({});
  const [toolGroupsByAgent, setToolGroupsByAgent] = useState<Record<string, Record<string, string[]>>>({});

  // Roster changes rarely — a slow poll is enough.
  useEffect(() => {
    const load = () => apiGet<{ roster: RosterAgent[] }>('/org').then((d) => setRoster(d.roster)).catch(() => {});
    load();
    const id = setInterval(load, 20000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    apiGet<{ groups: Record<string, Record<string, string[]>> }>('/org/agents/tools')
      .then((d) => setToolGroupsByAgent(d.groups))
      .catch(() => {});
  }, []);

  // Each agent's most recent run — fast poll so a brand-new run gets picked up quickly
  // and the matching card switches its live stream over to it.
  useEffect(() => {
    const load = () =>
      apiGet<AgentRun[]>('/org/agents/runs?limit=50')
        .then((runs) => {
          const byAgent: Record<string, AgentRun> = {};
          for (const r of runs) if (!byAgent[r.agent_name]) byAgent[r.agent_name] = r; // already DESC by started_at
          setLatestByAgent(byAgent);
        })
        .catch(() => {});
    load();
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="mx-auto max-w-[1900px] p-6">
      <style>{`@keyframes stepIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }`}</style>
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-gray-100">🛰️ Agent Activity</h1>
        <p className="text-sm text-gray-500">Every agent in the org, always live — what they're doing shows right on their own node as it happens.</p>
      </div>

      {/* One agent per row, full width — a busy timeline+diagram needs the room, and
          it scales fine even as more agents are added (each just gets its own row). */}
      <div className="grid grid-cols-1 gap-4">
        {roster.map((a) => (
          <AgentLiveCard key={a.name} agent={a} latestRun={latestByAgent[a.name] ?? null} toolGroups={toolGroupsByAgent[a.name] ?? {}} />
        ))}
        {roster.length === 0 && <div className="text-sm text-gray-600">Loading roster…</div>}
      </div>
    </div>
  );
}
