import { useState, useEffect } from 'react';
import { MermaidDiagram } from '../components/MermaidDiagram';
import { DrawioViewer } from '../components/DrawioViewer';

type DiagramTab = 'drawio' | 'mcp' | 'system';

export function Architecture() {
  const [tab, setTab] = useState<DiagramTab>('mcp');
  const [mcpContent, setMcpContent] = useState<string | null>(null);

  useEffect(() => {
    fetch('/mcp.mmd')
      .then(r => r.ok ? r.text() : null)
      .then(t => setMcpContent(t));
  }, []);

  const TABS: { id: DiagramTab; label: string; icon: string }[] = [
    { id: 'mcp', label: 'MCP Architecture', icon: '🔌' },
    { id: 'system', label: 'Full System', icon: '🗺️' },
    { id: 'drawio', label: 'Draw.io Diagram', icon: '📐' },
  ];

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Architecture</h1>
        <p className="text-gray-400 text-sm mt-1">
          Three views: MCP server, full orchestrator pipeline (store setup → design/frontend loop → niche-aware scraper/e-commerce loop → marketing → fulfillment, sequenced by plain Python — no LLM router), and Draw.io diagram. The full-system view also covers the storefront layer — the platform-app drives the host Storefront Runner (:8788), which uses the official Shopify CLI (`shopify theme pull · dev · push`) to run and deploy each store's Liquid theme from stores/shopify/* — plus the separate price/stock monitor job. Use +/− or Ctrl+scroll to zoom.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        {TABS.map(t => (
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

      {/* MCP Mermaid */}
      {tab === 'mcp' && (
        <div className="space-y-2">
          <p className="text-gray-500 text-xs">
            Source: <code className="text-gray-400">mcp.mmd</code> — MCP server with 5 tool groups, Stdio/SSE transport, no exposed API keys.
          </p>
          {mcpContent ? (
            <MermaidDiagram content={mcpContent} id="mcp-diagram" />
          ) : (
            <div className="p-4 bg-gray-900 border border-gray-700 rounded-xl text-gray-500 text-sm animate-pulse">
              Loading mcp.mmd...
            </div>
          )}
        </div>
      )}

      {/* Full system mermaid (hardcoded since architecture.mmd may not exist) */}
      {tab === 'system' && (
        <MermaidDiagram
          content={SYSTEM_MERMAID}
          id="system-diagram"
        />
      )}

      {/* Draw.io */}
      {tab === 'drawio' && (
        <DrawioViewer url="/architecture.drawio" height={700} />
      )}
    </div>
  );
}

const SYSTEM_MERMAID = `graph TB
    subgraph IN ["Triggers & Auth"]
        direction LR
        WH["Webhooks\nHMAC SHA-256"]
        RUN["POST /api/v1/run"]
        AT["POST /auth/token\nJWT Issuer"]
        DAEMON["Daemon loop (main.py)\nfires [MONITOR] run per\nactive store on interval"]
    end

    GW["FastAPI :8000\nJWT · CORS · rate-limit"]
    IN --> GW
    DAEMON --> GW

    subgraph PIPE ["Orchestrator — run_pipeline() (plain Python control flow, no LLM router)"]
        direction LR
        ORC["Orchestrator"]
        SS["Store Setup\nSonnet 4.6\nruns once"]
        DA["Design Agent\nSonnet 4.6\nUI/UX CSS"]
        FRA["Frontend Agent\nSonnet 4.6\nimplements UI, locks store"]
        TS["Trend Scraper\nHaiku 4.5\nniche-aware"]
        EM["E-com Manager\nSonnet 4.6"]
        MA["Marketing\ndeterministic, no LLM"]
        FA["Fulfillment\ndeterministic, no LLM"]
        ORC --> SS
        SS --> DA
        DA <-.->|"design loop"| FRA
        FRA --> TS
        TS <-.->|"catalog-fill loop"| EM
        EM --> MA --> FA
    end

    GW --> ORC

    THEME["shopify_theme.py\ncolors · hero · marquee · story · nav"]
    HZ["Horizon Theme\nkgg8n0-k0.myshopify.com"]
    SS --> THEME --> HZ

    subgraph MCP ["MCP Tools"]
        direction LR
        T1["Sourcing\nCJ · price cap 3×"]
        T2["Market Data\nSerper / Trends"]
        T3["Shopify\nGraphQL + REST"]
        T4["Ads Tools"]
        T5["Fulfillment"]
    end

    TS --> T1 & T2
    EM --> T3
    MA --> T4
    FA --> T5 & T3

    CJ["CJ Dropshipping"]
    SERP["Serper"]
    SHOP["Shopify Admin\nGraphQL 2024-07"]
    GADS["Google Ads"]

    T1 & T5 --> CJ
    T2 --> SERP
    T3 --> SHOP
    T4 --> GADS

    subgraph SF ["Storefront — Shopify CLI Liquid themes"]
        direction LR
        DOCS["platform-app\nMy Stores"]
        RUNNER["Storefront Runner\nhost :8788"]
        THEMEDIR["Liquid themes\nstores/shopify/*"]
        CLI["shopify theme\npull · dev · push"]
        DOCS --> RUNNER
        RUNNER --> CLI
        CLI --> THEMEDIR
    end

    CREDS["FastAPI\n/stores/{id}/theme-creds"]
    DOCS --> RUNNER
    RUNNER --> CREDS
    CREDS --> GW
    CLI --> SHOP

    subgraph MON ["Price/stock monitor — outside the pipeline"]
        direction LR
        MONJOB["check_store_prices()\nmonitoring.py — deterministic,\nno LLM, manually/cron-triggered"]
    end
    MONJOB --> CJ
    MONJOB --> SHOP

    classDef agent fill:#4B0082,stroke:#6d28d9,color:#e2e8f0
    classDef detagent fill:#1e293b,stroke:#475569,color:#cbd5e1
    classDef mcp fill:#1e3a5f,stroke:#2563eb,color:#e2e8f0
    classDef ext fill:#450a0a,stroke:#dc2626,color:#fee2e2
    classDef theme fill:#065f46,stroke:#059669,color:#d1fae5
    classDef gw fill:#292524,stroke:#78716c,color:#d6d3d1
    classDef store fill:#312e81,stroke:#6366f1,color:#e0e7ff
    class ORC,SS,DA,FRA,TS,EM agent
    class MA,FA,MONJOB detagent
    class T1,T2,T3,T4,T5 mcp
    class CJ,SERP,SHOP,GADS ext
    class THEME,HZ theme
    class GW,CREDS,DAEMON gw
    class RUNNER,CLI,THEMEDIR,DOCS store`;
