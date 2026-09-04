import { useState } from 'react';
import { DrawioViewer } from '../components/DrawioViewer';

type SystemTab = 'mcp' | 'system' | 'drawio' | 'sol_rag';
type StoreSubTab = 'org' | 'deploy' | 'store';

interface StoreEntry {
  id: string;
  label: string;
  icon: string;
  subTabs: { id: StoreSubTab; label: string; icon: string; url: string; desc: React.ReactNode }[];
}

// Adding a second store domain: append another entry here — it gets its own
// grouped button + sub-tab row automatically, same shape as this one.
const STORES: StoreEntry[] = [
  {
    id: 'alphaforbaby',
    label: 'AlphaForBaby',
    icon: '🏪',
    subTabs: [
      {
        id: 'org', label: 'Agent Org', icon: '👥', url: '/agent-org-architecture.drawio',
        desc: <>The live 7-agent org, Telegram, heartbeat/org-daemon/support-poll triggers, the ticket
          board, and the shared data layer (SQLite/Redis/FalkorDB).</>,
      },
      {
        id: 'deploy', label: 'Deploy Flow', icon: '🚀', url: '/deploy-branch-flow.drawio',
        desc: <>Branch naming → preview → human review gate → per-store production branch → Oxygen
          deploy, plus the PR-merge-notify pipeline. See <code className="text-gray-400">docs/DEV_WORKFLOW.md</code>.</>,
      },
      {
        id: 'store', label: 'Store Architecture', icon: '🏬', url: '/alphaforbaby-store-architecture.drawio',
        desc: <>alphaforbaby's traffic &amp; data flow — TikTok Ads → Hydrogen storefront → Shopify-hosted
          checkout (Hyp gateway) → Clarity, and Kai/Nora's separate read-only reporting paths.</>,
      },
    ],
  },
];

export function Architecture() {
  const [category, setCategory] = useState<'system' | 'store'>('system');
  const [tab, setTab] = useState<SystemTab>('mcp');
  const [activeStoreId, setActiveStoreId] = useState<string>(STORES[0].id);
  const [storeSubTab, setStoreSubTab] = useState<StoreSubTab>('org');

  const SYSTEM_TABS: { id: SystemTab; label: string; icon: string }[] = [
    { id: 'mcp', label: 'MCP Architecture', icon: '🔌' },
    { id: 'system', label: 'Full System', icon: '🗺️' },
    { id: 'drawio', label: 'Draw.io Diagram', icon: '📐' },
    { id: 'sol_rag', label: 'Sol: RAG + Fulfillment + Email', icon: '🧠' },
  ];

  const activeStore = STORES.find(s => s.id === activeStoreId)!;
  const activeSubTab = activeStore.subTabs.find(t => t.id === storeSubTab) ?? activeStore.subTabs[0];

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Architecture</h1>
        <p className="text-gray-400 text-sm mt-1">
          Two categories: system-wide diagrams (MCP server, full system, draw.io, Sol's RAG/
          fulfillment/email plumbing) and per-store-domain architecture — one consolidated view
          per store, matching each store's <code className="text-gray-500">ARCHITECTURE.md</code>. AlphaForBaby's
          diagrams are from <code className="text-gray-500">alphaforbaby/pdp-drawio-diagrams</code>, not yet
          merged. The company today is a 7-agent org — <strong>Ava</strong> (CEO), <strong>Sol</strong> (sourcing
          &amp; copy), <strong>Reel</strong> (video), <strong>Nora</strong> (support inbox), <strong>Milo</strong> (fulfillment),
          <strong> Kai</strong> (TikTok Ads + Clarity reporting), <strong>Nova</strong> (stay-on-target, weekly
          audit, no execute authority) — that chats over Telegram and acts on a 60-second
          heartbeat loop, not a per-client pipeline request. A legacy deterministic pipeline
          (<code className="text-gray-500">src/agents/orchestrator.py</code>) still exists underneath for full
          store builds; it's reached only via org <code className="text-gray-500">build_store</code>/
          <code className="text-gray-500">boost_store</code> decisions now, not directly by clients. The
          full-system view also covers the storefront layer — the platform-app drives the host
          Storefront Runner (:8788), which uses the official Shopify CLI
          (`shopify theme pull · dev · push`) to run and deploy each store's Liquid theme from
          stores/shopify/* — plus the standalone daily CJ stock-sweep job. Use +/− or Ctrl+scroll to zoom.
        </p>
      </div>

      {/* Category selector */}
      <div className="flex gap-2 border-b border-gray-800 pb-4">
        <button
          onClick={() => setCategory('system')}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors border ${
            category === 'system'
              ? 'bg-indigo-900/70 text-indigo-200 border-indigo-700'
              : 'bg-gray-800 text-gray-400 border-gray-700 hover:text-gray-200'
          }`}
        >
          🗂️ System-wide
        </button>
        <button
          onClick={() => setCategory('store')}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors border ${
            category === 'store'
              ? 'bg-indigo-900/70 text-indigo-200 border-indigo-700'
              : 'bg-gray-800 text-gray-400 border-gray-700 hover:text-gray-200'
          }`}
        >
          🏪 Stores
        </button>
      </div>

      {/* System-wide sub-tabs */}
      {category === 'system' && (
        <div className="flex gap-2">
          {SYSTEM_TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors border ${
                tab === t.id
                  ? 'bg-indigo-900/70 text-indigo-200 border-indigo-700'
                  : 'bg-gray-800 text-gray-400 border-gray-700 hover:text-gray-200'
              }`}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </div>
      )}

      {/* Store selector, then that store's sub-tabs — one cohesive view per domain */}
      {category === 'store' && (
        <div className="space-y-3">
          <div className="flex gap-2">
            {STORES.map(s => (
              <button
                key={s.id}
                onClick={() => { setActiveStoreId(s.id); setStoreSubTab(s.subTabs[0].id); }}
                className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors border ${
                  activeStoreId === s.id
                    ? 'bg-emerald-900/60 text-emerald-200 border-emerald-700'
                    : 'bg-gray-800 text-gray-400 border-gray-700 hover:text-gray-200'
                }`}
              >
                {s.icon} {s.label}
              </button>
            ))}
          </div>
          <div className="flex gap-2 pl-4 border-l-2 border-emerald-800/60">
            {activeStore.subTabs.map(t => (
              <button
                key={t.id}
                onClick={() => setStoreSubTab(t.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors border ${
                  storeSubTab === t.id
                    ? 'bg-indigo-900/70 text-indigo-200 border-indigo-700'
                    : 'bg-gray-800 text-gray-400 border-gray-700 hover:text-gray-200'
                }`}
              >
                {t.icon} {t.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* MCP Architecture — converted from mcp.mmd to a real .drawio (2026-09-02) */}
      {category === 'system' && tab === 'mcp' && (
        <div className="space-y-2">
          <p className="text-gray-500 text-xs">
            Per-agent real tool sets (<code className="text-gray-400">src/org/tool_catalog.py</code>).
            Only 2 of these actually speak the MCP protocol (<code className="text-gray-400">cj_mcp</code>, <code className="text-gray-400">tiktok_mcp</code>,
            both stdio, shown in green) — the rest are plain Python functions under <code className="text-gray-400">src/mcp_tools/*.py</code> despite the folder name.
          </p>
          <DrawioViewer url="/mcp-architecture.drawio" height={700} />
        </div>
      )}

      {/* Full System — converted from the hardcoded SYSTEM_MERMAID to a real .drawio (2026-09-02) */}
      {category === 'system' && tab === 'system' && (
        <DrawioViewer url="/full-system-architecture.drawio" height={700} />
      )}

      {/* Draw.io */}
      {category === 'system' && tab === 'drawio' && (
        <DrawioViewer url="/architecture.drawio" height={700} />
      )}

      {/* Sol: store integration registry + Redis RAG + fulfillment + email */}
      {category === 'system' && tab === 'sol_rag' && (
        <div className="space-y-2">
          <p className="text-gray-500 text-xs">
            Store integration registry (per-store supplier/email creds), the two Redis RAG
            corpora (CJ catalog + Sol's playbook), automatic order fulfillment, and the
            customer email tool. See <code className="text-gray-400">docs/sol_integrations_rag_fulfillment_email.md</code>.
          </p>
          <DrawioViewer url="/sol_integrations_rag_fulfillment_email.drawio" height={700} />
        </div>
      )}

      {/* Store domain — one consolidated view, sub-tabbed (mirrors that store's ARCHITECTURE.md) */}
      {category === 'store' && (
        <div className="space-y-2">
          <p className="text-gray-500 text-xs">
            {activeSubTab.desc} Copied from
            <code className="text-gray-400"> alphaforbaby/pdp-drawio-diagrams</code> (docs/diagrams{activeSubTab.url}) — not yet merged into main.
          </p>
          <DrawioViewer url={activeSubTab.url} height={700} />
        </div>
      )}
    </div>
  );
}

