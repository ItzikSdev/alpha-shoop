import { useState, useEffect, useRef } from 'react';

// ── Agent metadata ───────────────────────────────────────────────────────────

const AGENT_META: Record<string, { name: string; color: string; icon: string; model: string }> = {
  director:          { name: 'Orchestrator',   color: '#82B366', icon: '⚙️', model: 'plain Python' },
  store_setup:       { name: 'Store Setup',    color: '#F59E0B', icon: '🏪', model: 'Sonnet 4.6' },
  design_agent:      { name: 'Design Agent',   color: '#EC4899', icon: '✦',  model: 'Sonnet 4.6' },
  trend_scraper:     { name: 'Trend Scraper',  color: '#E67E22', icon: '📦', model: 'Haiku 4.5' },
  ecommerce_manager: { name: 'E-com Manager',  color: '#5E8E3E', icon: '🛒', model: 'Sonnet 4.6' },
  marketing_agent:   { name: 'Marketing',      color: '#4285F4', icon: '📢', model: 'Sonnet 4.6' },
  fulfillment_agent: { name: 'Fulfillment',    color: '#7C3AED', icon: '🚚', model: 'Haiku 4.5' },
};

const AGENT_ORDER = [
  'director', 'store_setup', 'design_agent', 'trend_scraper', 'ecommerce_manager', 'marketing_agent', 'fulfillment_agent',
];

// ── Types ────────────────────────────────────────────────────────────────────

type RunStatus = 'idle' | 'running' | 'done';
type EntryType = 'routing' | 'tool_call' | 'tool_result' | 'decision' | 'complete' | 'webhook';

interface PipelineState {
  store_brand: string;
  store_designed: boolean;
  target_keyword: string;
  supplier_product_id: string;
  supplier_price: number | null;
  supplier_sku: string;
  arbitrage_margin_approved: boolean;
  shopify_product_id: string;
  final_retail_price: number | null;
  store_url: string;
  google_campaign_id: string;
  pipeline_complete: boolean;
}

interface Step {
  agentId: string;
  delayMs: number;
  type: EntryType;
  message: string;
  data?: Record<string, unknown>;
  stateUpdate?: Partial<PipelineState>;
}

interface LogEntry extends Step {
  id: number;
}

// ── Initial state ────────────────────────────────────────────────────────────

const INITIAL_STATE: PipelineState = {
  store_brand: '',
  store_designed: false,
  target_keyword: '',
  supplier_product_id: '',
  supplier_price: null,
  supplier_sku: '',
  arbitrage_margin_approved: false,
  shopify_product_id: '',
  final_retail_price: null,
  store_url: '',
  google_campaign_id: '',
  pipeline_complete: false,
};

// ── Simulation script ────────────────────────────────────────────────────────

const STEPS: Step[] = [
  {
    agentId: 'director', delayMs: 0, type: 'routing',
    message: 'Pipeline started. store_brand is null → routing to Store Setup.',
    data: { next_node: 'store_setup', reason: 'brand identity not set', iteration: 1 },
  },
  {
    agentId: 'store_setup', delayMs: 600, type: 'tool_call',
    message: 'Generating brand brief (name · tagline · palette · differentiator)…',
  },
  {
    agentId: 'store_setup', delayMs: 1800, type: 'tool_result',
    message: '✓ Brand: "LumeNest" — "Light your living, effortlessly." · tone: warm · accent: #D4750A',
    data: {
      store_name: 'LumeNest',
      tagline: 'Light your living, effortlessly.',
      tone: 'warm',
      differentiator: 'Curated home ambiance essentials at honest prices',
      palette: { bg: '#FAFAF7', fg: '#1C1917', accent: '#D4750A' },
    },
    stateUpdate: { store_brand: 'LumeNest (warm · #D4750A)' },
  },
  {
    agentId: 'store_setup', delayMs: 2600, type: 'tool_call',
    message: 'build_homepage(5 sections: hero · marquee · brand-story · products · CTA)',
  },
  {
    agentId: 'store_setup', delayMs: 3800, type: 'tool_result',
    message: '✓ Homepage built · About Us page created · Policies added · Navigation wired (GraphQL)',
  },
  {
    agentId: 'director', delayMs: 4500, type: 'routing',
    message: 'Store brand set ✓ · store_designed = false → routing to Design Agent.',
    data: { next_node: 'design_agent', reason: 'CSS design pass not yet applied', iteration: 2 },
  },
  {
    agentId: 'design_agent', delayMs: 5000, type: 'tool_call',
    message: 'read_theme_context() → reading settings_data.json + templates/index.json',
  },
  {
    agentId: 'design_agent', delayMs: 5700, type: 'tool_call',
    message: 'Generating premium CSS (typography · spacing · buttons · cards · header · mobile)…',
  },
  {
    agentId: 'design_agent', delayMs: 7100, type: 'tool_result',
    message: '✓ 2847 chars of CSS → assets/custom-alpha.css · injected into layout/theme.liquid',
    data: {
      css_size_chars: 2847,
      sections_covered: ['root-vars', 'typography', 'breathing-room', 'buttons', 'product-cards', 'header', 'announcement-bar', 'footer', 'micro-interactions', 'mobile'],
    },
    stateUpdate: { store_designed: true },
  },
  {
    agentId: 'director', delayMs: 7800, type: 'routing',
    message: 'Design pass complete ✓ · no products yet → routing to Trend Scraper.',
    data: { next_node: 'trend_scraper', reason: 'store ready, no products in state', iteration: 3 },
    stateUpdate: { target_keyword: 'Home Decor' },
  },
  {
    agentId: 'trend_scraper', delayMs: 8500, type: 'tool_call',
    message: 'search_trending_products(category="Home Decor", max_results=10, min_margin_pct=30.0)',
  },
  {
    agentId: 'trend_scraper', delayMs: 10000, type: 'tool_result',
    message: 'CJ API → 10 products fetched, 7 passed margin filter.',
    data: {
      found: 7,
      top_3: [
        { title: 'Wireless Bluetooth Earbuds TWS Pro', supplier_price_usd: 8.50, suggested_retail_usd: 21.25, margin_pct: 60.0 },
        { title: 'LED Ring Light 10" + Tripod',        supplier_price_usd: 12.00, suggested_retail_usd: 30.00, margin_pct: 60.0 },
        { title: 'Adjustable Phone Stand Holder',      supplier_price_usd: 3.20,  suggested_retail_usd: 8.00,  margin_pct: 60.0 },
      ],
      note: 'CJ_EMAIL / CJ_API_KEY not set — showing sample data',
    },
  },
  {
    agentId: 'trend_scraper', delayMs: 10900, type: 'decision',
    message: 'Best pick: "Minimalist LED Desk Lamp" — highest order volume at 58% margin.',
    stateUpdate: {
      supplier_product_id: 'CJ-4421987',
      supplier_price: 11.20,
      supplier_sku: 'CJ-4421987-WHT',
    },
  },
  {
    agentId: 'director', delayMs: 11700, type: 'routing',
    message: 'Margin 58% ≥ 30% threshold ✓ — routing to E-commerce Manager.',
    data: { next_node: 'ecommerce_manager', margin_approved: true, iteration: 4 },
    stateUpdate: { arbitrage_margin_approved: true },
  },
  {
    agentId: 'ecommerce_manager', delayMs: 12500, type: 'tool_call',
    message: 'create_shopify_product(title="Minimalist LED Desk Lamp", price=26.90, compare_at_price=36.00)',
  },
  {
    agentId: 'ecommerce_manager', delayMs: 14200, type: 'tool_result',
    message: 'Shopify ACTIVE product created ✓ — added to "Home Decor" collection.',
    data: {
      success: true,
      product: {
        id: 9876543210,
        title: 'Minimalist LED Desk Lamp',
        status: 'active',
        price: '26.90',
        compare_at_price: '36.00',
        admin_url: 'https://alpha-shoop.myshopify.com/admin/products/9876543210',
      },
    },
    stateUpdate: {
      shopify_product_id: '9876543210',
      final_retail_price: 26.90,
      store_url: 'https://alpha-shoop.myshopify.com/products/minimalist-led-desk-lamp',
    },
  },
  {
    agentId: 'director', delayMs: 15000, type: 'routing',
    message: 'Product on Shopify ✓ — routing to Marketing Agent.',
    data: { next_node: 'marketing_agent', iteration: 5 },
  },
  {
    agentId: 'marketing_agent', delayMs: 15800, type: 'tool_call',
    message: 'create_google_campaign(name="AS-led-lamp-Jun26", daily_budget_usd=25.0, keywords=["led desk lamp","minimalist lamp","home office lighting"], target_countries=["US"])',
  },
  {
    agentId: 'marketing_agent', delayMs: 17400, type: 'tool_result',
    message: 'Campaign ENABLED ✓ — $25/day · $475.00 guardrail remaining today.',
    data: {
      campaign_id: 'G-2847562',
      status: 'ENABLED',
      daily_budget_usd: 25.0,
      keywords: ['led desk lamp', 'minimalist lamp', 'home office lighting'],
      guardrail_remaining_usd: 475.0,
    },
    stateUpdate: { google_campaign_id: 'G-2847562' },
  },
  {
    agentId: 'director', delayMs: 18200, type: 'complete',
    message: 'Pipeline complete ✓ — branded store live, product published, campaign running.',
    data: {
      gross_margin_pct: 58.0,
      shopify_product_id: '9876543210',
      google_campaign_id: 'G-2847562',
      daily_ad_budget_usd: 25.0,
      next_trigger: 'Shopify Order webhook → fulfillment_agent auto-fulfills',
    },
    stateUpdate: { pipeline_complete: true },
  },
  // Simulated order arriving
  {
    agentId: 'fulfillment_agent', delayMs: 20200, type: 'webhook',
    message: 'Shopify Order webhook received → order #1042 for "Minimalist LED Desk Lamp".',
    data: {
      shopify_order_id: '5554321098',
      customer: 'Sarah K.',
      quantity: 1,
      paid_usd: 26.90,
    },
  },
  {
    agentId: 'fulfillment_agent', delayMs: 20900, type: 'tool_call',
    message: 'place_supplier_order(product_id="CJ-4421987", quantity=1, order_reference="SH-1042")',
  },
  {
    agentId: 'fulfillment_agent', delayMs: 22400, type: 'tool_result',
    message: 'Supplier order placed ✓ — tracking: YT2498765432 · ETA 12–15 days.',
    data: {
      supplier_order_id: 'CJ-SH-1042',
      tracking_number: 'YT2498765432',
      carrier: 'CJ Packet',
      estimated_delivery: '12-15 days',
    },
  },
  {
    agentId: 'fulfillment_agent', delayMs: 23100, type: 'tool_call',
    message: 'fulfill_shopify_order(shopify_order_id="5554321098", tracking_number="YT2498765432", carrier="CJ Packet")',
  },
  {
    agentId: 'fulfillment_agent', delayMs: 24300, type: 'tool_result',
    message: 'Shopify order marked Fulfilled ✓ — customer notification email sent.',
    data: {
      fulfillment_id: '9876543210',
      status: 'success',
      customer_notified: true,
    },
  },
];

// ── Helpers ──────────────────────────────────────────────────────────────────

function elapsed(ms: number) {
  return `${(ms / 1000).toFixed(1)}s`;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function LogEntryRow({
  entry,
  expanded,
  onToggle,
}: {
  entry: LogEntry;
  expanded: boolean;
  onToggle: () => void;
}) {
  const meta = AGENT_META[entry.agentId];
  const hasData = !!entry.data;

  const prefix = {
    routing:    '→',
    tool_call:  '⚙',
    tool_result:'✓',
    decision:   '◆',
    complete:   '★',
    webhook:    '⚡',
  }[entry.type];

  const msgCls = {
    routing:    'text-white',
    tool_call:  'text-gray-500',
    tool_result:'text-gray-300',
    decision:   'text-gray-200',
    complete:   'text-emerald-400 font-semibold',
    webhook:    'text-violet-300',
  }[entry.type];

  const rowBg = entry.type === 'complete'
    ? 'bg-emerald-950/25 border border-emerald-900/30'
    : entry.type === 'webhook'
    ? 'bg-violet-950/20 border border-violet-900/20'
    : '';

  return (
    <div className={`rounded px-2 py-1.5 ${rowBg}`}>
      <div className="flex items-start gap-2 min-w-0">
        <span className="text-gray-600 shrink-0 w-9 text-right tabular-nums">{elapsed(entry.delayMs)}</span>
        <span className="shrink-0 w-3 text-center" style={{ color: meta.color + 'bb' }}>{prefix}</span>
        <span className="shrink-0 font-sans text-[10px] font-medium" style={{ color: meta.color }}>
          [{meta.name}]
        </span>
        <span className={`${msgCls} leading-tight break-all flex-1 min-w-0`}>{entry.message}</span>
        {hasData && (
          <button
            onClick={onToggle}
            className="ml-1 shrink-0 text-gray-600 hover:text-gray-400 transition-colors"
          >
            {expanded ? '▾' : '▸'}
          </button>
        )}
      </div>
      {hasData && expanded && (
        <pre className="mt-1.5 ml-[68px] text-[10px] text-gray-500 bg-gray-950/70 rounded p-2 overflow-x-auto leading-relaxed">
          {JSON.stringify(entry.data, null, 2)}
        </pre>
      )}
    </div>
  );
}

function StateField({
  label,
  value,
  changed,
}: {
  label: string;
  value: unknown;
  changed: boolean;
}) {
  const isEmpty =
    value === null ||
    value === '' ||
    value === false ||
    (typeof value === 'number' && value === 0);

  const display =
    value === null
      ? 'null'
      : typeof value === 'boolean'
      ? value
        ? 'true ✓'
        : 'false'
      : typeof value === 'number'
      ? String(value)
      : String(value) || '""';

  const valCls = isEmpty
    ? 'text-gray-700'
    : typeof value === 'boolean' && value
    ? 'text-yellow-400'
    : typeof value === 'number'
    ? 'text-blue-400'
    : 'text-emerald-400';

  return (
    <div
      className={`flex items-center gap-2 px-2 py-[3px] rounded text-xs transition-all duration-500 ${
        changed ? 'bg-yellow-400/10' : ''
      }`}
    >
      <span className="text-gray-600 font-mono w-36 shrink-0 truncate">{label}</span>
      <span className={`font-mono ${valCls} flex-1 truncate`}>{display}</span>
      {changed && (
        <span className="text-yellow-400/80 text-[10px] shrink-0">← new</span>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function PipelineSimulator() {
  const [status, setStatus] = useState<RunStatus>('idle');
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [pipeState, setPipeState] = useState<PipelineState>(INITIAL_STATE);
  const [changedKeys, setChangedKeys] = useState<Set<string>>(new Set());
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [doneAgents, setDoneAgents] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const logRef = useRef<HTMLDivElement>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const clearHighlightTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function clearAll() {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    if (clearHighlightTimer.current) clearTimeout(clearHighlightTimer.current);
  }

  function reset() {
    clearAll();
    setStatus('idle');
    setEntries([]);
    setPipeState(INITIAL_STATE);
    setChangedKeys(new Set());
    setActiveAgent(null);
    setDoneAgents(new Set());
    setExpanded(new Set());
  }

  function start() {
    reset();
    // give reset a tick to flush state, then begin
    setTimeout(() => {
      setStatus('running');
      setActiveAgent('director');

      STEPS.forEach((step, idx) => {
        const t = setTimeout(() => {
          const entry: LogEntry = { ...step, id: idx };
          setEntries(prev => [...prev, entry]);
          setActiveAgent(step.agentId);
          setDoneAgents(prev => new Set([...prev, step.agentId]));

          if (step.stateUpdate) {
            const keys = Object.keys(step.stateUpdate);
            setPipeState(prev => ({ ...prev, ...step.stateUpdate }));
            setChangedKeys(new Set(keys));
            if (clearHighlightTimer.current) clearTimeout(clearHighlightTimer.current);
            clearHighlightTimer.current = setTimeout(() => setChangedKeys(new Set()), 900);
          }

          if (step.type === 'complete') {
            setStatus('done');
          }
        }, step.delayMs);

        timers.current.push(t);
      });

      // Mark final done state after last step
      const last = STEPS[STEPS.length - 1];
      const finalT = setTimeout(() => setActiveAgent(null), last.delayMs + 800);
      timers.current.push(finalT);
    }, 50);
  }

  // Auto-scroll log to bottom
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [entries]);

  // Cleanup on unmount
  useEffect(() => () => clearAll(), []);

  function toggleExpand(id: number) {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  const totalMs = STEPS[STEPS.length - 1].delayMs;
  const progressMs = entries.length > 0 ? entries[entries.length - 1].delayMs : 0;
  const progressPct = Math.round((progressMs / totalMs) * 100);

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 px-5 py-3 border-b border-gray-700">
        <span className="text-sm font-semibold text-white">Pipeline Simulator</span>
        <span className="text-gray-600 text-xs">orchestrator.py · fixed Python sequence</span>

        {status === 'running' && (
          <span className="flex items-center gap-1.5 text-xs text-yellow-400">
            <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 animate-pulse" />
            Running…
          </span>
        )}
        {status === 'done' && (
          <span className="flex items-center gap-1.5 text-xs text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            Complete
          </span>
        )}

        <div className="ml-auto flex gap-2">
          {status !== 'idle' && (
            <button
              onClick={reset}
              className="px-3 py-1.5 text-xs text-gray-400 hover:text-white border border-gray-700 hover:border-gray-500 rounded-lg transition-colors"
            >
              Reset
            </button>
          )}
          <button
            onClick={start}
            disabled={status === 'running'}
            className={`px-4 py-1.5 text-xs font-medium rounded-lg transition-colors ${
              status === 'running'
                ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                : 'bg-indigo-600 hover:bg-indigo-500 text-white'
            }`}
          >
            {status === 'running' ? 'Running…' : status === 'done' ? '▶ Run Again' : '▶ Run'}
          </button>
        </div>
      </div>

      {/* ── Progress bar ────────────────────────────────────────────────────── */}
      {status !== 'idle' && (
        <div className="h-0.5 bg-gray-800">
          <div
            className="h-full bg-indigo-500 transition-all duration-500"
            style={{ width: `${status === 'done' ? 100 : progressPct}%` }}
          />
        </div>
      )}

      {/* ── Agent status chips ──────────────────────────────────────────────── */}
      <div className="flex items-center gap-1 px-5 py-2.5 border-b border-gray-800 bg-gray-950/40 flex-wrap">
        {AGENT_ORDER.map((agentId, i) => {
          const meta = AGENT_META[agentId];
          const isActive = activeAgent === agentId;
          const isDone = doneAgents.has(agentId) && activeAgent !== agentId;

          return (
            <div key={agentId} className="flex items-center gap-1">
              <div
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs border transition-all duration-300 ${
                  isActive
                    ? 'font-medium'
                    : isDone
                    ? 'opacity-60'
                    : 'border-gray-700 text-gray-600 bg-transparent'
                }`}
                style={
                  isActive || isDone
                    ? {
                        borderColor: meta.color + '70',
                        color: meta.color,
                        backgroundColor: meta.color + '12',
                      }
                    : {}
                }
              >
                <span>{meta.icon}</span>
                <span>{meta.name}</span>
                {isActive && (
                  <span
                    className="w-1.5 h-1.5 rounded-full animate-pulse"
                    style={{ backgroundColor: meta.color }}
                  />
                )}
                {isDone && !isActive && (
                  <span className="text-emerald-400 text-[10px]">✓</span>
                )}
              </div>
              {i < AGENT_ORDER.length - 1 && (
                <span className="text-gray-700 text-xs">→</span>
              )}
            </div>
          );
        })}
      </div>

      {/* ── 2-column body ───────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] divide-y lg:divide-y-0 lg:divide-x divide-gray-800">

        {/* Left: live log */}
        <div ref={logRef} className="h-80 overflow-y-auto p-3 space-y-0.5 font-mono text-xs scroll-smooth">
          {entries.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-gray-600 font-sans gap-2">
              <span className="text-2xl">🤖</span>
              <span className="text-sm">Press Run to simulate a full pipeline execution</span>
              <span className="text-xs text-gray-700">
                Trend Scraper → Shopify listing → Google Ads → Fulfillment
              </span>
            </div>
          )}

          {entries.map(entry => (
            <LogEntryRow
              key={entry.id}
              entry={entry}
              expanded={expanded.has(entry.id)}
              onToggle={() => toggleExpand(entry.id)}
            />
          ))}

          {status === 'running' && (
            <div className="flex items-center gap-1 pl-12 py-1">
              <span className="inline-block w-1 h-3 rounded bg-gray-700 animate-pulse" />
              <span className="inline-block w-1 h-3 rounded bg-gray-700 animate-pulse [animation-delay:150ms]" />
              <span className="inline-block w-1 h-3 rounded bg-gray-700 animate-pulse [animation-delay:300ms]" />
            </div>
          )}
        </div>

        {/* Right: SharedArbitrageState */}
        <div className="p-4 flex flex-col gap-0.5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 text-xs font-semibold uppercase tracking-wide">
              SharedArbitrageState
            </span>
            <span className="text-gray-700 text-[10px] font-mono">src/shared/state.py</span>
          </div>

          <div className="space-y-0 text-xs">
            {/* brand section */}
            <div className="text-gray-700 text-[10px] uppercase tracking-wider px-2 pt-2 pb-1">
              Brand
            </div>
            {(['store_brand', 'store_designed'] as const).map(k => (
              <StateField key={k} label={k} value={pipeState[k]} changed={changedKeys.has(k)} />
            ))}

            {/* sourcing section */}
            <div className="text-gray-700 text-[10px] uppercase tracking-wider px-2 pt-3 pb-1">
              Sourcing
            </div>
            {(['target_keyword', 'supplier_product_id', 'supplier_price', 'supplier_sku'] as const).map(k => (
              <StateField key={k} label={k} value={pipeState[k]} changed={changedKeys.has(k)} />
            ))}

            {/* market validation */}
            <div className="text-gray-700 text-[10px] uppercase tracking-wider px-2 pt-3 pb-1">
              Market Validation
            </div>
            {(['arbitrage_margin_approved'] as const).map(k => (
              <StateField key={k} label={k} value={pipeState[k]} changed={changedKeys.has(k)} />
            ))}

            {/* store & ads */}
            <div className="text-gray-700 text-[10px] uppercase tracking-wider px-2 pt-3 pb-1">
              Store & Ads
            </div>
            {(['shopify_product_id', 'final_retail_price', 'store_url', 'google_campaign_id'] as const).map(k => (
              <StateField key={k} label={k} value={pipeState[k]} changed={changedKeys.has(k)} />
            ))}

            {/* control */}
            <div className="text-gray-700 text-[10px] uppercase tracking-wider px-2 pt-3 pb-1">
              Pipeline Control
            </div>
            {(['pipeline_complete'] as const).map(k => (
              <StateField key={k} label={k} value={pipeState[k]} changed={changedKeys.has(k)} />
            ))}
          </div>

          {/* Computed: gross_margin_pct */}
          {pipeState.final_retail_price !== null && pipeState.supplier_price !== null && (
            <div className="mt-3 pt-3 border-t border-gray-800">
              <div className="flex items-center gap-2 px-2 py-0.5 text-xs">
                <span className="text-gray-600 font-mono w-36 shrink-0">gross_margin_pct</span>
                <span className="font-mono text-indigo-400 font-semibold">
                  {(
                    ((pipeState.final_retail_price - pipeState.supplier_price) /
                      pipeState.final_retail_price) *
                    100
                  ).toFixed(1)}
                  %
                </span>
                <span className="text-gray-700 text-[10px]">@property</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Footer hint ─────────────────────────────────────────────────────── */}
      <div className="px-5 py-2 border-t border-gray-800 text-[10px] text-gray-700 flex items-center gap-2">
        <span>▸ = expand payload</span>
        <span className="text-gray-800">·</span>
        <span>highlighted fields = state just updated</span>
        <span className="text-gray-800">·</span>
        <span>fulfillment triggered by Shopify Order webhook</span>
      </div>
    </div>
  );
}
