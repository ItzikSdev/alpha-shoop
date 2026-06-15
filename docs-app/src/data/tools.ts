import type { MCPTool, ToolGroup } from '../types';

const BASE = 'src/mcp_tools';

export const MCP_TOOLS: MCPTool[] = [
  // ── Sourcing ──────────────────────────────────────────────────────────────
  {
    id: 'search_trending_products',
    groupId: 'sourcing', groupName: 'Sourcing Tools',
    name: 'search_trending_products',
    description: 'Search CJ Dropshipping for products above a minimum margin threshold. Falls back to AliExpress when CJ is unavailable.',
    techIds: ['cj', 'aliexpress', 'python', 'pydantic'],
    filePath: `${BASE}/sourcing.py`, lineNumber: 15,
    input: {
      name: 'SearchTrendingProductsInput',
      fields: [
        { name: 'category', type: 'str', required: true, description: 'Product category (e.g. "electronics")', example: 'electronics' },
        { name: 'max_results', type: 'int', required: false, description: 'Max number of products to return', example: 20 },
        { name: 'min_margin', type: 'float', required: false, description: 'Minimum margin 0.0–1.0', example: 0.3 },
      ],
    },
    output: {
      name: 'list[TrendingProduct]',
      description: 'Filtered product candidates sorted by trend score',
      fields: [
        { name: 'product_id', type: 'str', required: true, description: 'CJ product identifier', example: 'CJ000123' },
        { name: 'title', type: 'str', required: true, description: 'Product name', example: 'Wireless Earbuds Pro' },
        { name: 'price_supplier_usd', type: 'float', required: true, description: 'Supplier cost in USD', example: 8.50 },
        { name: 'estimated_price_shopify_usd', type: 'float', required: true, description: 'Recommended Shopify price', example: 24.99 },
        { name: 'margin_pct', type: 'float', required: true, description: 'Gross margin 0.0–1.0', example: 0.66 },
        { name: 'trend_score', type: 'int', required: true, description: 'Trending score 0–100', example: 78 },
      ],
    },
    exampleArgs: { category: 'electronics', max_results: 10, min_margin: 0.3 },
  },
  {
    id: 'get_shipping_cost',
    groupId: 'sourcing', groupName: 'Sourcing Tools',
    name: 'get_shipping_cost',
    description: 'Fetch shipping cost and estimated delivery days from CJ Dropshipping freight calculator.',
    techIds: ['cj', 'python'],
    filePath: `${BASE}/sourcing.py`, lineNumber: 62,
    input: {
      name: 'GetShippingCostInput',
      fields: [
        { name: 'product_id', type: 'str', required: true, description: 'CJ product ID', example: 'CJ000123' },
        { name: 'destination_country', type: 'str', required: true, description: 'ISO 3166-1 alpha-2', example: 'US' },
        { name: 'shipping_method', type: 'str', required: false, description: '"standard" | "express" | "economy"', example: 'standard' },
      ],
    },
    output: {
      name: 'ShippingCostResult',
      fields: [
        { name: 'cost_usd', type: 'float', required: true, description: 'Shipping cost in USD', example: 3.99 },
        { name: 'estimated_days', type: 'int', required: true, description: 'Min estimated delivery days', example: 12 },
        { name: 'carrier', type: 'str', required: true, description: 'Carrier name', example: 'CJ Packet' },
      ],
    },
    exampleArgs: { product_id: 'CJ000123', destination_country: 'US', shipping_method: 'standard' },
  },

  // ── Market Validation ─────────────────────────────────────────────────────
  {
    id: 'search_market_prices',
    groupId: 'market', groupName: 'Market Validation Tools',
    name: 'search_market_prices',
    description: 'Query competitor prices on Google Shopping via Serper API to validate that the margin target is realistic.',
    techIds: ['serper', 'google_trends', 'python', 'pydantic'],
    filePath: `${BASE}/market.py`, lineNumber: 10,
    input: {
      name: 'SearchMarketPricesInput',
      fields: [
        { name: 'query', type: 'str', required: true, description: 'Product search query', example: 'wireless earbuds' },
        { name: 'country', type: 'str', required: false, description: 'ISO country code', example: 'US' },
        { name: 'num_results', type: 'int', required: false, description: 'Number of results', example: 10 },
      ],
    },
    output: {
      name: 'MarketPricesResult',
      fields: [
        { name: 'prices', type: 'list[MarketPrice]', required: true, description: 'Individual competitor listings', example: null },
        { name: 'avg_price', type: 'float', required: true, description: 'Average market price USD', example: 22.49 },
        { name: 'price_range', type: 'PriceRange', required: true, description: '{ min, max } in USD', example: null },
      ],
    },
    exampleArgs: { query: 'wireless earbuds bluetooth', country: 'US', num_results: 10 },
  },
  {
    id: 'check_google_trends',
    groupId: 'market', groupName: 'Market Validation Tools',
    name: 'check_google_trends',
    description: 'Retrieve Google Trends interest score and related queries for a keyword to confirm demand trajectory.',
    techIds: ['google_trends', 'python'],
    filePath: `${BASE}/market.py`, lineNumber: 52,
    input: {
      name: 'CheckGoogleTrendsInput',
      fields: [
        { name: 'keyword', type: 'str', required: true, description: 'Search term to analyse', example: 'wireless earbuds' },
        { name: 'timeframe', type: 'str', required: false, description: 'Time range string', example: 'today 3-m' },
        { name: 'geo', type: 'str', required: false, description: 'Geographic region code', example: 'US' },
      ],
    },
    output: {
      name: 'GoogleTrendsResult',
      fields: [
        { name: 'interest_over_time', type: 'list[TrendDataPoint]', required: true, description: 'Monthly interest values 0–100', example: null },
        { name: 'related_queries', type: 'list[str]', required: true, description: 'Related search queries', example: null },
        { name: 'trend_score', type: 'int', required: true, description: 'Aggregate score 0–100', example: 72 },
      ],
    },
    exampleArgs: { keyword: 'wireless earbuds', timeframe: 'today 3-m', geo: 'US' },
  },

  // ── Shopify ───────────────────────────────────────────────────────────────
  {
    id: 'create_shopify_product',
    groupId: 'shopify', groupName: 'Shopify Tools',
    name: 'create_shopify_product',
    description: 'Create a new product in Shopify store via Admin GraphQL API 2024-07. Sets status=ACTIVE immediately.',
    techIds: ['shopify', 'python', 'pydantic'],
    filePath: `${BASE}/shopify.py`, lineNumber: 47,
    input: {
      name: 'CreateShopifyProductInput',
      fields: [
        { name: 'title', type: 'str', required: true, description: 'Product title', example: 'Wireless Earbuds Pro' },
        { name: 'description', type: 'str', required: true, description: 'HTML product description', example: '<p>Premium wireless...</p>' },
        { name: 'price', type: 'float', required: true, description: 'Selling price in store currency', example: 24.99 },
        { name: 'compare_at_price', type: 'float', required: true, description: 'Strikethrough original price', example: 39.99 },
        { name: 'images', type: 'list[str]', required: false, description: 'Image URLs', example: null },
        { name: 'variants', type: 'list[dict]', required: false, description: 'Product variants', example: null },
      ],
    },
    output: {
      name: 'CreateShopifyProductResult',
      fields: [
        { name: 'product', type: 'ShopifyProduct', required: true, description: '{ id, title, status }', example: null },
        { name: 'success', type: 'bool', required: true, description: 'True if no GraphQL userErrors', example: true },
      ],
    },
    exampleArgs: { title: 'Wireless Earbuds Pro', description: '<p>Premium earbuds</p>', price: 24.99, compare_at_price: 39.99, images: [], variants: [] },
  },
  {
    id: 'update_inventory',
    groupId: 'shopify', groupName: 'Shopify Tools',
    name: 'update_inventory',
    description: 'Adjust inventory quantity for a Shopify product at a given location.',
    techIds: ['shopify', 'python'],
    filePath: `${BASE}/shopify.py`, lineNumber: 80,
    input: {
      name: 'UpdateInventoryInput',
      fields: [
        { name: 'product_id', type: 'str', required: true, description: 'Shopify product GID', example: 'gid://shopify/Product/123' },
        { name: 'location_id', type: 'str', required: true, description: 'Shopify location ID', example: 'default' },
        { name: 'quantity', type: 'int', required: true, description: 'New inventory quantity', example: 10 },
      ],
    },
    output: {
      name: 'UpdateInventoryResult',
      fields: [
        { name: 'updated', type: 'bool', required: true, description: 'Success flag', example: true },
        { name: 'available', type: 'int', required: true, description: 'Current available quantity', example: 10 },
      ],
    },
    exampleArgs: { product_id: 'gid://shopify/Product/123', location_id: 'default', quantity: 10 },
  },

  // ── Ads ───────────────────────────────────────────────────────────────────
  {
    id: 'create_google_campaign',
    groupId: 'ads', groupName: 'Ads Tools',
    name: 'create_google_campaign',
    description: 'Create a Google Ads search campaign. Budget is checked against the $500/day guardrail before creation.',
    techIds: ['google_ads', 'python', 'pydantic'],
    filePath: `${BASE}/ads.py`, lineNumber: 11,
    input: {
      name: 'CreateGoogleCampaignInput',
      fields: [
        { name: 'campaign_name', type: 'str', required: true, description: 'Unique campaign name (max 255 chars)', example: 'AS-wireless-earbuds' },
        { name: 'daily_budget_usd', type: 'float', required: true, description: 'Daily budget USD (guardrail: ≤$500/day total)', example: 25.0 },
        { name: 'keywords', type: 'list[str]', required: true, description: 'Target keywords', example: null },
        { name: 'target_countries', type: 'list[str]', required: true, description: 'ISO country codes', example: null },
      ],
    },
    output: {
      name: 'CreateCampaignResult',
      fields: [
        { name: 'campaign_id', type: 'str', required: true, description: 'Google Ads campaign ID', example: 'camp_as-wireless' },
        { name: 'status', type: 'str', required: true, description: '"ENABLED" | "PAUSED"', example: 'ENABLED' },
        { name: 'resource_name', type: 'str', required: true, description: 'Full Google Ads resource name', example: 'customers/123/campaigns/abc' },
      ],
    },
    exampleArgs: { campaign_name: 'AS-wireless-earbuds', daily_budget_usd: 25.0, keywords: ['wireless earbuds', 'bluetooth earphones'], target_countries: ['US'] },
  },
  {
    id: 'get_campaign_metrics',
    groupId: 'ads', groupName: 'Ads Tools',
    name: 'get_campaign_metrics',
    description: 'Retrieve ROAS, spend, impressions and conversions for a campaign using GAQL.',
    techIds: ['google_ads', 'python'],
    filePath: `${BASE}/ads.py`, lineNumber: 44,
    input: {
      name: 'GetCampaignMetricsInput',
      fields: [
        { name: 'campaign_id', type: 'str', required: true, description: 'Google Ads campaign ID', example: 'camp_as-wireless' },
        { name: 'date_range', type: 'str', required: false, description: 'GAQL date range string', example: 'LAST_7_DAYS' },
      ],
    },
    output: {
      name: 'CampaignMetricsResult',
      fields: [
        { name: 'impressions', type: 'int', required: true, description: 'Total impressions', example: 1250 },
        { name: 'clicks', type: 'int', required: true, description: 'Total clicks', example: 87 },
        { name: 'spend_usd', type: 'float', required: true, description: 'Total spend in USD', example: 23.40 },
        { name: 'conversions', type: 'int', required: true, description: 'Conversion events', example: 3 },
        { name: 'roas', type: 'float', required: true, description: 'Return on ad spend', example: 4.2 },
      ],
    },
    exampleArgs: { campaign_id: 'camp_as-wireless', date_range: 'LAST_7_DAYS' },
  },

  // ── Fulfillment ───────────────────────────────────────────────────────────
  {
    id: 'place_supplier_order',
    groupId: 'fulfillment', groupName: 'Fulfillment Tools',
    name: 'place_supplier_order',
    description: 'Place a dropshipping order with CJ Dropshipping. Order value is checked against the $200 guardrail.',
    techIds: ['cj', 'python', 'pydantic'],
    filePath: `${BASE}/fulfillment.py`, lineNumber: 10,
    input: {
      name: 'PlaceSupplierOrderInput',
      fields: [
        { name: 'product_id', type: 'str', required: true, description: 'CJ product ID', example: 'CJ000123' },
        { name: 'quantity', type: 'int', required: true, description: 'Units to order', example: 1 },
        { name: 'shipping_address', type: 'Address', required: true, description: '{ name, address1, city, country, zip, phone }', example: null },
        { name: 'order_reference', type: 'str', required: true, description: 'Shopify order ID for audit', example: 'SH-12345' },
      ],
    },
    output: {
      name: 'SupplierOrderResult',
      fields: [
        { name: 'supplier_order_id', type: 'str', required: true, description: 'CJ order ID', example: 'CJ-SH-12345' },
        { name: 'tracking_number', type: 'str | None', required: false, description: 'Carrier tracking number (if available)', example: 'YT2498765432' },
        { name: 'estimated_delivery', type: 'str', required: true, description: 'Delivery estimate', example: '10-15 days' },
      ],
    },
    exampleArgs: { product_id: 'CJ000123', quantity: 1, shipping_address: { name: 'John Doe', address1: '123 Main St', city: 'New York', country: 'US', zip: '10001', phone: '+1555000000' }, order_reference: 'SH-12345' },
  },
  {
    id: 'fulfill_shopify_order',
    groupId: 'fulfillment', groupName: 'Fulfillment Tools',
    name: 'fulfill_shopify_order',
    description: 'Push tracking information to Shopify and mark the order as fulfilled. Triggers customer notification email.',
    techIds: ['shopify', 'python'],
    filePath: `${BASE}/fulfillment.py`, lineNumber: 52,
    input: {
      name: 'FulfillShopifyOrderInput',
      fields: [
        { name: 'shopify_order_id', type: 'str', required: true, description: 'Shopify order ID (numeric string)', example: '5554321098' },
        { name: 'tracking_number', type: 'str', required: true, description: 'Carrier tracking number', example: 'YT2498765432' },
        { name: 'carrier', type: 'str', required: true, description: 'Carrier name', example: 'CJ Packet' },
        { name: 'tracking_url', type: 'str', required: true, description: 'Full tracking URL', example: 'https://t.17track.net/en#YT2498765432' },
      ],
    },
    output: {
      name: 'FulfillmentResult',
      fields: [
        { name: 'fulfillment_id', type: 'str', required: true, description: 'Shopify fulfillment ID', example: '9876543210' },
        { name: 'status', type: 'str', required: true, description: '"success" | "pending" | "error"', example: 'success' },
      ],
    },
    exampleArgs: { shopify_order_id: '5554321098', tracking_number: 'YT2498765432', carrier: 'CJ Packet', tracking_url: 'https://t.17track.net/en#YT2498765432' },
  },
];

export const TOOL_GROUPS: ToolGroup[] = [
  { id: 'sourcing', name: 'Sourcing Tools', icon: '📦', description: 'Product discovery from CJ Dropshipping and AliExpress.', tools: MCP_TOOLS.filter(t => t.groupId === 'sourcing') },
  { id: 'market', name: 'Market Validation', icon: '📊', description: 'Price comparison and Google Trends demand validation.', tools: MCP_TOOLS.filter(t => t.groupId === 'market') },
  { id: 'shopify', name: 'Shopify Tools', icon: '🛒', description: 'Product listings and inventory via Admin GraphQL API.', tools: MCP_TOOLS.filter(t => t.groupId === 'shopify') },
  { id: 'ads', name: 'Ads Tools', icon: '📢', description: 'Google Ads campaign creation and ROAS tracking.', tools: MCP_TOOLS.filter(t => t.groupId === 'ads') },
  { id: 'fulfillment', name: 'Fulfillment Tools', icon: '🚚', description: 'Supplier order placement and Shopify tracking updates.', tools: MCP_TOOLS.filter(t => t.groupId === 'fulfillment') },
];
