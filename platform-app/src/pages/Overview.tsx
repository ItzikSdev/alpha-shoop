import { useNavigate } from 'react-router-dom';

const PAGE_PATHS: Record<string, string> = {
  tools: '/tools',
  agents: '/agents',
  endpoints: '/endpoints',
  architecture: '/architecture',
  technologies: '/technologies',
};

const STATS = [
  { label: 'Agent Roles', value: '5', icon: '🤖', color: '#CC785C' },
  { label: 'MCP Tools', value: '10', icon: '🔌', color: '#7C3AED' },
  { label: 'API Endpoints', value: '6', icon: '⚡', color: '#009688' },
  { label: 'Max Ad Spend/Day', value: '$500', icon: '🛡️', color: '#E92063' },
  { label: 'Max Order Value', value: '$200', icon: '🔒', color: '#E67E22' },
];

const FLOW = [
  { step: 1, title: 'CEO (Ava) picks the next run', icon: '👑', desc: 'Orchestrator/router — reads live store state + Claude budget, fires a build / boost / monitor run and Slack alerts at critical stages' },
  { step: 2, title: 'Product Hunter (Hunter)', icon: '🔍', desc: 'Sources CJ products by rating, shipping & inventory; pulls competitor prices; computes NET margin (after 18% VAT + payment fees)' },
  { step: 3, title: 'Evaluator (self-correction)', icon: '⚖️', desc: 'Approves batches above the net-margin target; below it, loops back to the Hunter with feedback — hard cap 3 loops, then escalates to Slack' },
  { step: 4, title: 'UX & Content (Remy) → Shopify Developer (Devon) → Growth Marketer (Max)', icon: '🔄', desc: 'Copy + brand design → push to Shopify via GraphQL (tags/SEO/variants) → Facebook & Instagram ad blueprint' },
  { step: 5, title: 'Guardrails + HITL gates', icon: '🛡️', desc: 'Kill-switch on every ad spend/order, budget auto-fallback to local Ollama, and Slack notify-gates before going live / before ad spend' },
  { step: 6, title: 'Single SQLite (traces.db) + Redis + ChromaDB', icon: '💾', desc: 'One shared DB for org, stores & traces; Redis cache; product embeddings' },
];

export function Overview() {
  const navigate = useNavigate();
  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      {/* Hero */}
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Alpha Shoop</h1>
        <p className="text-gray-400 text-lg">
          Autonomous Arbitrage & E-commerce Multi-Agent System — powered by{' '}
          <span className="text-violet-400 font-semibold">LangGraph</span> +{' '}
          <span className="text-amber-400 font-semibold">Claude</span> +{' '}
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

      {/* Quick nav */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {([['tools', '🔌', 'MCP Tools', '10 tools across 5 groups'], ['agents', '🤖', 'AI Agents', '5-role team — Claude + local Ollama'], ['endpoints', '⚡', 'API Endpoints', '6 endpoints with live tests'], ['architecture', '🗺️', 'Architecture', 'Draw.io + Mermaid diagrams'], ['technologies', '🎨', 'Technologies', '18 tech badges with docs']] as const).map(([page, icon, title, desc]) => (
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
