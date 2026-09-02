import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiGet } from '../api/client';

const PAGE_PATHS: Record<string, string> = {
  tools: '/tools',
  agents: '/agents',
  endpoints: '/endpoints',
  architecture: '/architecture',
  technologies: '/technologies',
  company: '/company',
  updates: '/updates',
  integrations: '/integrations',
};

const FLOW = [
  { step: 1, title: 'Telegram chat, not a per-client pipeline request', icon: '💬', desc: 'Ava (CEO) and specialists route + reply live over Telegram — the org’s only chat interface (replaced Slack) — on top of a 60s heartbeat + 30s org-daemon loop' },
  { step: 2, title: 'Sol — sourcing & copy', icon: '🛒', desc: 'Sources CJ Dropshipping products, writes copy/SEO, and pushes straight to Shopify via GraphQL — runs his own real tool loop, not just narration' },
  { step: 3, title: 'Reel — video', icon: '🎬', desc: 'Local Wan2.2/ComfyUI pipeline generates product photos + 360° rotation videos; gates publishing until real media exists' },
  { step: 4, title: 'Nora — support · Milo — fulfillment · Kai — growth', icon: '📮', desc: 'Nora runs the central Gmail support inbox; Milo places CJ orders and pushes tracking on Shopify webhooks; Kai reports TikTok Ads + Microsoft Clarity data (read-only, never launches campaigns)' },
  { step: 5, title: 'Guardrails + a legacy pipeline underneath', icon: '🛡️', desc: 'Hard ad-spend/order caps, a $100/mo Claude budget that auto-falls back to local qwen3, and src/agents/orchestrator.py still handles full store builds via build_store/boost_store decisions' },
  { step: 6, title: 'One shared SQLite (traces.db) + Redis RAG', icon: '💾', desc: 'Single DB for org state, stores, tickets and traces; Redis holds the CJ catalog + Sol’s playbook embeddings' },
];

interface OrgResp { roster: { status: string }[] }
interface IntegResp { connected: number; total: number }

export function Overview() {
  const navigate = useNavigate();
  const [recentUpdates, setRecentUpdates] = useState<string[]>([]);
  const [headcount, setHeadcount] = useState<number | null>(null);
  const [integrations, setIntegrations] = useState<{ connected: number; total: number } | null>(null);

  useEffect(() => {
    fetch('/decisions-log.md')
      .then(r => (r.ok ? r.text() : ''))
      .then(raw => {
        const headings = [...raw.matchAll(/^## (.+)$/gm)].map(m => m[1]);
        setRecentUpdates(headings.slice(0, 3));
      })
      .catch(() => setRecentUpdates([]));

    apiGet<OrgResp>('/org')
      .then(org => setHeadcount(org.roster.filter(m => m.status === 'active').length))
      .catch(() => setHeadcount(null));

    apiGet<IntegResp>('/org/integrations')
      .then(i => setIntegrations({ connected: i.connected, total: i.total }))
      .catch(() => setIntegrations(null));
  }, []);

  const STATS = [
    { label: 'Active Agents', value: headcount != null ? String(headcount) : '—', icon: '🤖', color: '#CC785C' },
    { label: 'Integrations Connected', value: integrations ? `${integrations.connected}/${integrations.total}` : '—', icon: '🔌', color: '#7C3AED' },
    { label: 'Comms Channel', value: 'Telegram', icon: '💬', color: '#009688' },
    { label: 'Max Ad Spend/Day', value: '$500', icon: '🛡️', color: '#E92063' },
    { label: 'Max Order Value', value: '$200', icon: '🔒', color: '#E67E22' },
  ];

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      {/* Hero */}
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Alpha Shoop</h1>
        <p className="text-gray-400 text-lg">
          A self-managing e-commerce org of AI agents — chats over{' '}
          <span className="text-sky-400 font-semibold">Telegram</span>, runs on{' '}
          <span className="text-amber-400 font-semibold">Claude</span> (local qwen3 fallback), served by{' '}
          <span className="text-teal-400 font-semibold">FastAPI</span>
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {STATS.map(s => (
          <div
            key={s.label}
            className="bg-gray-900 border border-gray-700 rounded-xl p-4 text-center"
            style={{ borderColor: s.color + '40' }}
          >
            <div className="text-2xl mb-1">{s.icon}</div>
            <div className="text-2xl font-bold" style={{ color: s.color }}>{s.value}</div>
            <div className="text-gray-500 text-xs mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Flow */}
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6">
        <h2 className="text-lg font-bold text-white mb-4">System Flow</h2>
        <div className="space-y-3">
          {FLOW.map(f => (
            <div key={f.step} className="flex items-start gap-4">
              <div className="shrink-0 w-8 h-8 rounded-full bg-indigo-900/60 border border-indigo-700 flex items-center justify-center text-xs font-bold text-indigo-300">
                {f.step}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span>{f.icon}</span>
                  <span className="text-white text-sm font-medium">{f.title}</span>
                </div>
                <p className="text-gray-500 text-xs mt-0.5">{f.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Recent updates teaser */}
      {recentUpdates.length > 0 && (
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-bold text-white">📰 Recent Updates</h2>
            <button
              onClick={() => navigate('/updates')}
              className="text-xs text-indigo-400 hover:text-indigo-300"
            >
              View all →
            </button>
          </div>
          <ul className="space-y-2">
            {recentUpdates.map((h, i) => (
              <li key={i} className="text-sm text-gray-400 flex items-start gap-2">
                <span className="text-gray-600 mt-0.5">•</span>
                <span>{h}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Quick nav */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {([
          ['company', '🏢', 'The Company', 'Live roster, meetings, goals'],
          ['updates', '📰', 'Updates', 'Chronological dev decisions log'],
          ['integrations', '🔌', 'Integrations', 'What’s actually connected, live'],
          ['agents', '🤖', 'AI Agents', 'The team, tasks + connections — live'],
          ['architecture', '🗺️', 'Architecture', 'Draw.io + Mermaid diagrams'],
          ['tools', '🔌', 'MCP Tools', 'Reference: legacy pipeline tool catalog'],
        ] as const).map(([page, icon, title, desc]) => (
          <button
            key={page}
            onClick={() => navigate(PAGE_PATHS[page])}
            className="bg-gray-900 border border-gray-700 rounded-xl p-4 text-left hover:border-indigo-700/60 hover:bg-indigo-900/10 transition-all group"
          >
            <div className="text-2xl mb-2">{icon}</div>
            <div className="text-white text-sm font-medium group-hover:text-indigo-300">{title}</div>
            <div className="text-gray-500 text-xs mt-0.5">{desc}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
