import type { Technology } from '../types';

export const TECHNOLOGIES: Record<string, Technology> = {
  python: {
    id: 'python', name: 'Python 3.11', icon: '🐍',
    color: '#fff', bg: '#3776AB', border: '#2c5f8a',
    docsUrl: 'https://docs.python.org/3/', category: 'backend',
    description: 'Core language for all backend agents and MCP tools.',
  },
  fastapi: {
    id: 'fastapi', name: 'FastAPI', icon: '⚡',
    color: '#fff', bg: '#009688', border: '#00796b',
    docsUrl: 'https://fastapi.tiangolo.com/', category: 'backend',
    description: 'Async API gateway — handles all HTTP requests, auth, rate limiting.',
  },
  langgraph: {
    id: 'langgraph', name: 'LangGraph', icon: '🔗',
    color: '#fff', bg: '#4B0082', border: '#380062',
    docsUrl: 'https://langchain-ai.github.io/langgraph/', category: 'ai',
    description: 'StateGraph engine that wires all agents into a loop with conditional routing.',
  },
  claude: {
    id: 'claude', name: 'Claude', icon: '🧠',
    color: '#fff', bg: '#CC785C', border: '#a05a40',
    docsUrl: 'https://docs.anthropic.com/', category: 'ai',
    description: 'Powers all agents: Opus for Director, Sonnet for E-com/Marketing, Haiku for Scraper/Fulfillment.',
  },
  mcp: {
    id: 'mcp', name: 'MCP', icon: '🔌',
    color: '#fff', bg: '#7C3AED', border: '#5b21b6',
    docsUrl: 'https://modelcontextprotocol.io/', category: 'protocol',
    description: 'Model Context Protocol — exposes tools to Claude without leaking API keys.',
  },
  pydantic: {
    id: 'pydantic', name: 'Pydantic v2', icon: '✅',
    color: '#fff', bg: '#E92063', border: '#c01750',
    docsUrl: 'https://docs.pydantic.dev/', category: 'backend',
    description: 'Strict I/O validation on all agent inputs, outputs, and API request bodies.',
  },
  shopify: {
    id: 'shopify', name: 'Shopify', icon: '🛒',
    color: '#fff', bg: '#5E8E3E', border: '#3d6327',
    docsUrl: 'https://shopify.dev/docs/api/admin-graphql', category: 'external-api',
    description: 'Admin GraphQL API 2024-07 — product creation, inventory, order fulfillment.',
  },
  cj: {
    id: 'cj', name: 'CJ Dropshipping', icon: '📦',
    color: '#fff', bg: '#E67E22', border: '#ca6f1e',
    docsUrl: 'https://developers.cjdropshipping.com/', category: 'external-api',
    description: 'REST API v2 — product search, shipping rates, order placement.',
  },
  aliexpress: {
    id: 'aliexpress', name: 'AliExpress', icon: '🏭',
    color: '#fff', bg: '#E74C3C', border: '#cb4335',
    docsUrl: 'https://developers.aliexpress.com/', category: 'external-api',
    description: 'DS API — supplementary product sourcing and pricing data.',
  },
  google_ads: {
    id: 'google_ads', name: 'Google Ads', icon: '📢',
    color: '#fff', bg: '#4285F4', border: '#2a75f3',
    docsUrl: 'https://developers.google.com/google-ads/api/docs/start', category: 'external-api',
    description: 'Google Ads API v17 — campaign creation and performance metrics.',
  },
  meta_ads: {
    id: 'meta_ads', name: 'Meta Ads', icon: '📣',
    color: '#fff', bg: '#1877F2', border: '#0d65d9',
    docsUrl: 'https://developers.facebook.com/docs/marketing-api/', category: 'external-api',
    description: 'Meta Marketing API v19 — Facebook/Instagram ad campaigns.',
  },
  serper: {
    id: 'serper', name: 'Serper API', icon: '🔍',
    color: '#fff', bg: '#111827', border: '#374151',
    docsUrl: 'https://serper.dev/docs', category: 'external-api',
    description: 'Google Shopping results for real-time market price validation.',
  },
  google_trends: {
    id: 'google_trends', name: 'Google Trends', icon: '📈',
    color: '#fff', bg: '#34A853', border: '#2d9249',
    docsUrl: 'https://trends.google.com/', category: 'external-api',
    description: 'Trend scores — validates that a product has growing demand.',
  },
  postgresql: {
    id: 'postgresql', name: 'PostgreSQL 15', icon: '🐘',
    color: '#fff', bg: '#336791', border: '#275581',
    docsUrl: 'https://www.postgresql.org/docs/', category: 'database',
    description: 'LangGraph checkpoint store + all business data (orders, products, campaigns).',
  },
  redis: {
    id: 'redis', name: 'Redis 7', icon: '⚡',
    color: '#fff', bg: '#DC382D', border: '#c32d22',
    docsUrl: 'https://redis.io/docs/', category: 'database',
    description: 'Agent state cache, pub/sub for real-time status updates, ARQ task queue.',
  },
  chromadb: {
    id: 'chromadb', name: 'ChromaDB', icon: '🧮',
    color: '#fff', bg: '#9B59B6', border: '#8e44ad',
    docsUrl: 'https://docs.trychroma.com/', category: 'database',
    description: 'Vector database for product embeddings and semantic deduplication.',
  },
  langsmith: {
    id: 'langsmith', name: 'LangSmith', icon: '🔭',
    color: '#fff', bg: '#FF6B35', border: '#e55a24',
    docsUrl: 'https://docs.smith.langchain.com/', category: 'infrastructure',
    description: 'Full LLM trace observability — every agent call is logged and searchable.',
  },
  arq: {
    id: 'arq', name: 'ARQ', icon: '🌿',
    color: '#fff', bg: '#37814A', border: '#2d6b3c',
    docsUrl: 'https://arq-docs.helpmanual.io/', category: 'infrastructure',
    description: 'Async task queue backed by Redis — runs agent graph jobs off the request thread.',
  },
};

export const TECH_LIST = Object.values(TECHNOLOGIES);
