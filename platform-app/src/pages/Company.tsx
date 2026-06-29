import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost } from '../api/client';

// ── Types (mirror src/org/models.py to_dict / to_public) ──────────────────────

interface AgentPublic {
  agent_id: string;
  name: string;
  role: string;
  skill: string;
  team: string;
  status: string;
  hired_at: string;
  hired_by: string;
  lessons: string[];
  training: string;
  perf: Record<string, number>;
}

interface CompanyState {
  founded_at: string;
  headcount: number;
  treasury_usd: number;
  goals: string[];
  lessons: string[];
  culture: { values?: string[]; language?: string[] };
  daemon: { enabled: boolean; interval_minutes: number; last_tick_at: string | null; tick_count: number };
}

interface Decision {
  type: string;
  [k: string]: unknown;
}

interface Meeting {
  meeting_id: string;
  kind: string;
  held_at: string;
  attendees: string[];
  decisions: Decision[];
  notes: string;
  context_snapshot: { revenue_7d_total_usd?: number; store_count?: number };
}

const ROLE_ICON: Record<string, string> = {
  CEO: '👑', 'Product Hunter': '🔍', 'UX & Content': '🎨',
  'Shopify Developer': '🛠️', 'Growth Marketer': '📣',
  // legacy roles (departed agents)
  CTO: '🧠', HR: '🧑‍💼', store_builder: '🏗️', marketer: '📣', Developer: '👩‍💻',
};

const KIND_COLOR: Record<string, string> = {
  standup: 'text-sky-400 bg-sky-900/30',
  strategy: 'text-indigo-300 bg-indigo-900/40',
  retro: 'text-amber-300 bg-amber-900/30',
  teambuilding: 'text-emerald-300 bg-emerald-900/30',
};

function fmtTime(iso: string): string {
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function decisionLabel(d: Decision): string {
  switch (d.type) {
    case 'build_store': return `🏗️ Build store — ${d.niche ?? ''} ($${d.budget_usd ?? 0})`;
    case 'boost_store': return `📈 Boost ${String(d.store_id ?? '').slice(0, 8)} [${d.mode ?? 'MARKETING'}]`;
    case 'hire': return `🧑‍💼 Hire ${d.role ?? ''} — ${String(d.skill ?? '').slice(0, 50)}`;
    case 'train': return `🎓 Train ${d.target_role ?? ''} on ${d.topic ?? ''}`;
    case 'set_goal': return `🎯 Goal: ${d.goal ?? ''}`;
    case 'record_lesson': return `📝 Lesson: ${d.lesson ?? ''}`;
    default: return `• ${d.type}`;
  }
}

export function Company() {
  const [company, setCompany] = useState<CompanyState | null>(null);
  const [roster, setRoster] = useState<AgentPublic[]>([]);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [org, mtgs] = await Promise.all([
        apiGet<{ company: CompanyState; roster: AgentPublic[] }>('/org'),
        apiGet<Meeting[]>('/org/meetings?limit=30'),
      ]);
      setCompany(org.company);
      setRoster(org.roster);
      setMeetings(mtgs);
      setError(null);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000); // poll so live meetings/hires appear
    return () => clearInterval(t);
  }, [load]);

  const runMeeting = async (kind?: string) => {
    setBusy(true);
    try {
      await apiPost('/org/tick', kind ? { kind } : {});
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const toggleDaemon = async () => {
    if (!company) return;
    setBusy(true);
    try {
      await apiPost('/org/daemon', { enabled: !company.daemon.enabled });
      await load();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">🏢 The Company</h1>
          <p className="text-gray-500 text-sm mt-1">
            A self-managing organization of agents that builds stores, earns real money, and grows itself.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => runMeeting()}
            disabled={busy}
            className="px-3 py-2 rounded-lg text-sm bg-indigo-700 hover:bg-indigo-600 text-white disabled:opacity-40"
          >
            {busy ? '…' : '📋 Run a meeting now'}
          </button>
          <button
            onClick={toggleDaemon}
            disabled={busy || !company}
            className={`px-3 py-2 rounded-lg text-sm text-white disabled:opacity-40 ${
              company?.daemon.enabled ? 'bg-rose-700 hover:bg-rose-600' : 'bg-emerald-700 hover:bg-emerald-600'
            }`}
          >
            {company?.daemon.enabled ? '⏸ Stop 24/7' : '▶️ Start 24/7'}
          </button>
        </div>
      </div>

      {error && <div className="mb-4 p-3 rounded-lg bg-rose-900/40 text-rose-300 text-sm">{error}</div>}

      {/* KPI strip */}
      {company && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <Kpi label="Treasury (real)" value={`$${company.treasury_usd.toFixed(2)}`} />
          <Kpi label="Headcount" value={String(company.headcount)} />
          <Kpi label="Meetings held" value={String(company.daemon.tick_count)} />
          <Kpi
            label="Autonomous loop"
            value={company.daemon.enabled ? `ON · every ${company.daemon.interval_minutes}m` : 'OFF'}
            tone={company.daemon.enabled ? 'good' : 'muted'}
          />
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-6">
        {/* Roster */}
        <section>
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
            Team ({roster.length})
          </h2>
          <div className="space-y-3">
            {roster.map(a => (
              <div key={a.agent_id} className="p-4 rounded-xl bg-gray-900 border border-gray-800">
                <div className="flex items-center gap-2">
                  <span className="text-lg">{ROLE_ICON[a.role] ?? '🤖'}</span>
                  <span className="font-semibold text-white">{a.name}</span>
                  <span className="px-2 py-0.5 rounded-full text-xs bg-gray-800 text-gray-300">{a.role}</span>
                  <span className="ml-auto text-xs text-gray-600">{a.team}</span>
                </div>
                <p className="text-sm text-gray-400 mt-2">{a.skill}</p>
                {a.lessons.length > 0 && (
                  <div className="mt-2 text-xs text-gray-500">
                    <span className="text-gray-600">Latest lesson:</span> {a.lessons[a.lessons.length - 1]}
                  </div>
                )}
                <div className="mt-2 text-xs text-gray-600">
                  Hired by {a.hired_by} · {fmtTime(a.hired_at)}
                </div>
              </div>
            ))}
            {roster.length === 0 && <p className="text-gray-600 text-sm">No agents yet.</p>}
          </div>

          {company && company.goals.length > 0 && (
            <div className="mt-6">
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">Goals (OKRs)</h2>
              <ul className="space-y-1">
                {company.goals.map((g, i) => (
                  <li key={i} className="text-sm text-gray-300">🎯 {g}</li>
                ))}
              </ul>
            </div>
          )}

          {company && (company.culture.values?.length ?? 0) > 0 && (
            <div className="mt-6">
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">Culture</h2>
              <ul className="space-y-1">
                {company.culture.values!.map((v, i) => (
                  <li key={i} className="text-sm text-gray-400">🤝 {v}</li>
                ))}
              </ul>
            </div>
          )}
        </section>

        {/* Meeting feed */}
        <section>
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">Meeting feed</h2>
          <div className="space-y-3">
            {meetings.map(m => (
              <div key={m.meeting_id} className="p-4 rounded-xl bg-gray-900 border border-gray-800">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`px-2 py-0.5 rounded-full text-xs ${KIND_COLOR[m.kind] ?? 'text-gray-300 bg-gray-800'}`}>
                    {m.kind}
                  </span>
                  <span className="text-xs text-gray-600">{fmtTime(m.held_at)}</span>
                  <span className="ml-auto text-xs text-gray-600">
                    ${(m.context_snapshot.revenue_7d_total_usd ?? 0).toFixed(2)} rev · {m.attendees.length} attendees
                  </span>
                </div>
                {m.notes && <p className="text-sm text-gray-300 mb-2">{m.notes}</p>}
                {m.decisions.length > 0 ? (
                  <ul className="space-y-1">
                    {m.decisions.map((d, i) => (
                      <li key={i} className="text-xs text-gray-400">{decisionLabel(d)}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-gray-600">No decisions.</p>
                )}
              </div>
            ))}
            {meetings.length === 0 && (
              <p className="text-gray-600 text-sm">No meetings yet — click "Run a meeting now".</p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function Kpi({ label, value, tone }: { label: string; value: string; tone?: 'good' | 'muted' }) {
  return (
    <div className="p-4 rounded-xl bg-gray-900 border border-gray-800">
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`text-lg font-semibold mt-1 ${
        tone === 'good' ? 'text-emerald-400' : tone === 'muted' ? 'text-gray-500' : 'text-white'
      }`}>
        {value}
      </div>
    </div>
  );
}
