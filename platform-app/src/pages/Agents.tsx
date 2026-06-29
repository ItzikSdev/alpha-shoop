import { useEffect, useState } from 'react';
import { apiGet } from '../api/client';

interface Member {
  agent_id: string; name: string; role: string; skill: string;
  status: string; task?: string; training?: string;
  last_result?: { ok?: boolean | null; action?: string; status?: number; detail?: string };
  perf?: Record<string, unknown>;
}
interface OrgResp { company: { goals?: string[] }; roster: Member[] }
interface Integration { name: string; category: string; who: string[]; connected: boolean; detail: string }
interface IntegResp { integrations: Integration[] }

const AVATAR: Record<string, string> = {
  CEO: '👑', 'Product Hunter': '🔍', 'UX & Content': '🎨',
  'Shopify Developer': '🛠️', 'Growth Marketer': '📣',
  // legacy roles (departed agents) kept so history still renders
  CTO: '🧭', Developer: '👩‍💻',
};

// Which Claude model each role runs on (budget-aware tier in src/llm/client.py).
// All roles auto-fall back to the free local Ollama (qwen2.5) over the budget cap.
const MODEL: Record<string, { name: string; tier: 'smart' | 'fast' }> = {
  CEO: { name: 'Claude Sonnet 4.6', tier: 'smart' },
  'Product Hunter': { name: 'Claude Sonnet 4.6', tier: 'smart' },
  'UX & Content': { name: 'Claude Haiku 4.5', tier: 'fast' },
  'Shopify Developer': { name: 'Claude Haiku 4.5', tier: 'fast' },
  'Growth Marketer': { name: 'Claude Haiku 4.5', tier: 'fast' },
  // legacy
  CTO: { name: 'Claude Sonnet 4.6', tier: 'smart' },
  Developer: { name: 'Claude Haiku 4.5', tier: 'fast' },
};

export function Agents() {
  const [roster, setRoster] = useState<Member[]>([]);
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    Promise.all([apiGet<OrgResp>('/org'), apiGet<IntegResp>('/org/integrations')])
      .then(([org, integ]) => {
        if (!alive) return;
        setRoster(org.roster.filter((m) => m.status === 'active'));
        setIntegrations(integ.integrations);
        setError('');
      })
      .catch((e) => alive && setError(String(e)))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, []);

  if (loading) return <div className="p-8 text-gray-400">Loading the team…</div>;
  if (error) return <div className="p-8 text-rose-400">Failed to load: {error}</div>;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-bold text-white">🤖 The Team</h1>
        <p className="mt-1 text-sm text-gray-400">
          Your only employees — live from the shared database. {roster.length} active.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {roster.map((m) => {
          const conns = integrations.filter((i) => i.who.includes(m.name));
          return (
            <div key={m.agent_id} className="rounded-xl border border-gray-800 bg-gray-900/60 p-5">
              <div className="flex items-center gap-3">
                <div className="grid h-11 w-11 place-items-center rounded-full bg-gray-800 text-xl">{AVATAR[m.role] || '🤖'}</div>
                <div>
                  <div className="text-lg font-semibold text-gray-100">{m.name}</div>
                  <div className="text-xs text-gray-500">{m.role}</div>
                </div>
                <span className="ml-auto rounded-full bg-emerald-500/20 px-2 py-0.5 text-xs text-emerald-300">● {m.status}</span>
              </div>

              {MODEL[m.role] && (
                <div className="mt-3 flex items-center gap-2">
                  <span
                    className={`rounded px-2 py-0.5 text-xs font-medium ${
                      MODEL[m.role].tier === 'smart'
                        ? 'bg-violet-500/15 text-violet-300'
                        : 'bg-sky-500/15 text-sky-300'
                    }`}
                    title={MODEL[m.role].tier === 'smart' ? 'Top-tier reasoning model' : 'Fast, cheaper model'}
                  >
                    🧠 {MODEL[m.role].name}
                  </span>
                  <span className="text-[10px] text-gray-600" title="Routes to the free local Ollama model when the monthly Claude budget cap is hit">
                    ↘ local fallback over budget
                  </span>
                </div>
              )}

              <p className="mt-3 line-clamp-4 text-sm text-gray-400">{m.skill}</p>

              <div className="mt-3 rounded-lg border border-gray-800 bg-gray-950/50 p-3">
                <div className="text-[10px] uppercase tracking-wide text-gray-600">Working on now</div>
                <div className="mt-1 text-sm text-gray-200">{m.task || <span className="text-gray-600">— idle —</span>}</div>
                {m.last_result?.action && (
                  <div className={`mt-1 text-xs ${m.last_result.ok === false ? 'text-rose-400' : 'text-emerald-400'}`}>
                    last: {m.last_result.action} {m.last_result.ok === false ? '✗' : m.last_result.ok ? '✓' : ''}
                  </div>
                )}
              </div>

              <div className="mt-3">
                <div className="mb-1 text-[10px] uppercase tracking-wide text-gray-600">Connections</div>
                <div className="flex flex-wrap gap-1">
                  {conns.map((c) => (
                    <span key={c.name}
                      className={`rounded px-2 py-0.5 text-xs ${c.connected ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-300'}`}
                      title={c.detail}>
                      {c.connected ? '●' : '○'} {c.name.split(' (')[0]}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <p className="text-xs text-gray-600">
        Roster, tasks and connections all read live from the shared <code className="text-gray-500">traces.db</code> —
        what you see here is exactly what the team sees. Manage connections in the Integrations tab.
      </p>
    </div>
  );
}
