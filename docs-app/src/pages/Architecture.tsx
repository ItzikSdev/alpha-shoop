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
          Three views: MCP server, full LangGraph flow with store setup + niche-aware scraper, and Draw.io diagram. Use +/− or Ctrl+scroll to zoom.
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
    end

    GW["FastAPI :8000\nJWT · CORS · rate-limit"]
    IN --> GW

    subgraph GRAPH ["LangGraph StateGraph"]
        direction LR
        DIR["Director\nClaude Opus 4.8"]
        SS["Store Setup\nSonnet 4.6\nruns once"]
        TS["Trend Scraper\nHaiku 4.5\nniche-aware"]
        EM["E-com Manager\nSonnet 4.6"]
        MA["Marketing\nSonnet 4.6"]
        FA["Fulfillment\nHaiku 4.5"]
        DIR --> SS & TS & EM & MA & FA
        SS & TS & EM & MA & FA -.->|"report"| DIR
    end

    GW --> DIR

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

    classDef agent fill:#4B0082,stroke:#6d28d9,color:#e2e8f0
    classDef mcp fill:#1e3a5f,stroke:#2563eb,color:#e2e8f0
    classDef ext fill:#450a0a,stroke:#dc2626,color:#fee2e2
    classDef theme fill:#065f46,stroke:#059669,color:#d1fae5
    classDef gw fill:#292524,stroke:#78716c,color:#d6d3d1
    class DIR,SS,TS,EM,MA,FA agent
    class T1,T2,T3,T4,T5 mcp
    class CJ,SERP,SHOP,GADS ext
    class THEME,HZ theme
    class GW gw`;
