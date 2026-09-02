import { useState, useEffect } from 'react';
import { MermaidDiagram } from '../components/MermaidDiagram';
import { DrawioViewer } from '../components/DrawioViewer';

type DiagramTab = 'drawio' | 'mcp' | 'system' | 'sol_rag';

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
    { id: 'sol_rag', label: 'Sol: RAG + Fulfillment + Email', icon: '🧠' },
  ];

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Architecture</h1>
        <p className="text-gray-400 text-sm mt-1">
          Four views: MCP server, full system, Draw.io diagram, and Sol's RAG/fulfillment/email
          plumbing. The company today is a 6-agent org — <strong>Ava</strong> (CEO), <strong>Sol</strong> (sourcing
          &amp; copy), <strong>Reel</strong> (video), <strong>Nora</strong> (support inbox), <strong>Milo</strong> (fulfillment),
          <strong> Kai</strong> (TikTok Ads reporting) — that chats over Telegram and acts on a 60-second
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

      {/* Sol: store integration registry + Redis RAG + fulfillment + email */}
      {tab === 'sol_rag' && (
        <div className="space-y-2">
          <p className="text-gray-500 text-xs">
            Store integration registry (per-store supplier/email creds), the two Redis RAG
            corpora (CJ catalog + Sol's playbook), automatic order fulfillment, and the
            customer email tool. See <code className="text-gray-400">docs/sol_integrations_rag_fulfillment_email.md</code>.
          </p>
          <DrawioViewer url="/sol_integrations_rag_fulfillment_email.drawio" height={700} />
        </div>
      )}
    </div>
  );
}

const SYSTEM_MERMAID = `graph TB
    subgraph IN ["Interfaces"]
        direction LR
        TG["Telegram\nonly chat interface\n(replaced Slack)"]
        WH["Shopify webhooks\nHMAC SHA-256"]
        API["FastAPI :8000\n/org · /images · /videos ..."]
    end

    subgraph LOOPS ["main.py lifespan — 8 background loops"]
        direction LR
        HB["Heartbeat\nevery 60s"]
        ORGD["Org daemon\nevery 30s"]
        SUPL["Support-inbox poll\nevery 120s"]
        CEOR["CEO report\ndaily 21:00 Asia/Jerusalem"]
        MGR["Manager check-in\nevery 30min"]
        LEGD["Legacy single-store daemon\ndisabled by default"]
        IMGL["Reel image scan\ndisabled by default"]
    end

    subgraph ORG ["Org — 6 agents · org_agents / org_company tables"]
        direction LR
        AVA["Ava · CEO\nrouting · reports · meeting decisions"]
        SOL["Sol · sourcing & copy\nCJ search → Shopify push"]
        REEL["Reel · video\nlocal Wan2.2/ComfyUI pipeline"]
        NORA["Nora · support\ncentral Gmail inbox"]
        MILO["Milo · fulfillment\norder → CJ → tracking"]
        KAI["Kai · TikTok Ads\nread-only reporting"]
    end

    TG <--> ORG
    API --> ORG
    HB --> ORG
    ORGD --> ORG
    SUPL --> NORA
    CEOR --> AVA
    MGR --> AVA
    WH --> MILO

    ORG -->|"build_store / boost_store\nmeeting decisions"| PIPE
    subgraph PIPE ["Legacy pipeline — src/agents/orchestrator.py (still live, no longer client-facing)"]
        direction LR
        SS["store_setup"] --> DA["design"] --> FR["frontend"] --> TSN["trend_scraper"] --> EV["evaluator"] --> EM["ecommerce"] --> MA["marketing"] --> FA["fulfillment"]
    end
    LEGD -.->|"disabled by default"| PIPE

    subgraph TOOLS ["Per-agent tools"]
        direction LR
        CJREST["CJ REST\nsrc/mcp_tools — catalog search"]
        CJMCP["CJ real MCP\nsrc/cj_mcp — inventory + tracking"]
        SHOP["Shopify Admin\nGraphQL 2024-07"]
        TT["TikTok Ads real MCP\nsrc/tiktok_mcp — read-only"]
        GMAIL["Central Gmail inbox\nsend via Resend"]
        WAN["Local Wan2.2/ComfyUI\n+ TTS + ffmpeg"]
    end

    SOL --> CJREST & CJMCP & SHOP
    KAI --> TT
    NORA --> GMAIL
    MILO --> CJREST & SHOP
    REEL --> WAN
    PIPE --> SHOP
    IMGL --> REEL

    CJ["CJ Dropshipping"]
    SHOPADM["Shopify Admin API"]
    TIKTOK["TikTok Marketing API"]
    CJREST & CJMCP --> CJ
    SHOP --> SHOPADM
    TT --> TIKTOK

    subgraph LLM ["Model routing — src/llm/client.py, LiteLLM proxy"]
        direction LR
        LITELLM["get_llm(role)\nrole → LiteLLM model alias"]
        CLAUDE["Anthropic Claude\nCEO smart-tier, Sol fast-tier"]
        QWEN["Local qwen3\ndefault fallback for every role\nwhen ORG_LOCAL_LLM=1 or over budget"]
        LITELLM --> CLAUDE
        LITELLM --> QWEN
    end
    ORG --> LITELLM
    PIPE --> LITELLM

    subgraph GRAPH ["Knowledge graph — FalkorDB (Stage 1 of 3 built)"]
        direction LR
        FALKOR[("alpha_org graph\nAgent → CAN_USE → Tool\nAgent → EXECUTED → Tool\nAgent → ASSIGNED → Agent")]
    end
    ORG -.->|"best-effort, non-blocking"| FALKOR

    subgraph DATA ["Data layer — one shared data/traces.db"]
        direction LR
        SQLITE[("SQLite\norg_agents · org_meetings · org_company\nagent_runs · trace runs · product_mappings")]
        REDIS[("Redis\nRAG: CJ catalog + Sol's playbook")]
    end
    ORG --> SQLITE
    SOL --> REDIS

    subgraph SF ["Storefront — Shopify CLI Liquid themes"]
        direction LR
        DOCS["platform-app\nMy Stores"]
        RUNNER["Storefront Runner\nhost :8788"]
        THEMEDIR["Liquid themes\nstores/shopify/*"]
        CLI["shopify theme\npull · dev · push"]
        DOCS --> RUNNER --> CLI --> THEMEDIR
    end
    RUNNER -->|"/stores/{id}/theme-creds"| API
    CLI --> SHOPADM

    subgraph MON ["Daily CJ stock sweep — src/org/stock_watch.py, outside the org tick"]
        direction LR
        STOCKW["check_store_stock()\nfails closed · 2 consecutive zero-stock\nchecks before removal · cap 3/cycle"]
    end
    STOCKW --> CJ
    STOCKW --> SHOPADM

    classDef agent fill:#4B0082,stroke:#6d28d9,color:#e2e8f0
    classDef legacy fill:#292524,stroke:#57534e,color:#a8a29e
    classDef ext fill:#450a0a,stroke:#dc2626,color:#fee2e2
    classDef data fill:#312e81,stroke:#6366f1,color:#e0e7ff
    classDef llm fill:#1e3a5f,stroke:#2563eb,color:#e2e8f0
    classDef gw fill:#374151,stroke:#78716c,color:#d6d3d1
    classDef store fill:#065f46,stroke:#059669,color:#d1fae5
    classDef kg fill:#0b3d2e,stroke:#10b981,color:#d1fae5
    class AVA,SOL,REEL,NORA,MILO,KAI agent
    class SS,DA,FR,TSN,EV,EM,MA,FA,LEGD legacy
    class CJREST,CJMCP,SHOP,TT,GMAIL,WAN,CJ,SHOPADM,TIKTOK ext
    class SQLITE,REDIS data
    class LITELLM,CLAUDE,QWEN llm
    class TG,WH,API,HB,ORGD,SUPL,CEOR,MGR,IMGL gw
    class RUNNER,CLI,THEMEDIR,DOCS,STOCKW store
    class FALKOR kg`;
