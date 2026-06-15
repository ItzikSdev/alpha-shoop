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
          Three views of the system: MCP server (Mermaid), full LangGraph flow (Mermaid), and the detailed Draw.io diagram.
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

const SYSTEM_MERMAID = `graph TD
    WH[Shopify Webhooks] -->|HMAC SHA-256| GW
    TR[Manual Trigger POST /api/v1/run] --> GW
    GW[FastAPI Gateway :8000<br>JWT · slowapi · CORS]
    GW --> DIR

    subgraph LangGraph["LangGraph StateGraph"]
        DIR[Director Agent<br>Claude Opus 4.8]
        TS[Trend Scraper<br>Claude Haiku 4.5]
        EM[E-com Manager<br>Claude Sonnet 4.6]
        MA[Marketing Agent<br>Claude Sonnet 4.6]
        FA[Fulfillment Agent<br>Claude Haiku 4.5]
        DIR -->|route| TS & EM & MA & FA
        TS & EM & MA & FA -->|loop back| DIR
    end

    subgraph MCP["MCP Server (Stdio/SSE)"]
        T1[Sourcing Tools]
        T2[Market Validation]
        T3[Shopify Tools]
        T4[Ads Tools]
        T5[Fulfillment Tools]
    end

    TS --> T1 & T2
    EM --> T3
    MA --> T4
    FA --> T5 & T3

    T1 & T5 --> CJ[CJ Dropshipping API]
    T2 --> SERP[Serper / Google Trends]
    T3 --> SHOP[Shopify Admin GraphQL]
    T4 --> GADS[Google Ads API v17]

    subgraph Guardrails
        KS[Kill-Switch<br>MAX_AD=$500/day]
        VAL[Pydantic Validator]
    end

    MA -.->|spend check| KS
    FA -.->|order check| KS

    subgraph Persistence
        PG[(PostgreSQL 15<br>checkpoints)]
        RD[(Redis 7<br>state cache)]
        CH[(ChromaDB<br>embeddings)]
    end

    DIR --- PG
    GW --- RD

    classDef agent fill:#4B0082,stroke:#6d28d9,color:#e2e8f0
    classDef mcp fill:#7C3AED,stroke:#8b5cf6,color:#e2e8f0
    classDef ext fill:#1e3a5f,stroke:#2563eb,color:#e2e8f0
    classDef guard fill:#7f1d1d,stroke:#dc2626,color:#e2e8f0
    class DIR,TS,EM,MA,FA agent
    class T1,T2,T3,T4,T5 mcp
    class CJ,SERP,SHOP,GADS ext
    class KS,VAL guard`;
