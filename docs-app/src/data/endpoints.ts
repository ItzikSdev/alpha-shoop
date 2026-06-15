import type { APIEndpoint } from '../types';

export const ENDPOINTS: APIEndpoint[] = [
  {
    id: 'health',
    method: 'GET', path: '/api/v1/health',
    description: 'Health check — returns status of FastAPI + downstream services (DB, Redis, Anthropic).',
    handlerFn: 'health_check',
    filePath: 'src/api/routes/health.py', lineNumber: 16,
    techIds: ['fastapi', 'python'],
    tags: ['Health'],
    requiresAuth: false,
    response: {
      name: 'HealthResponse',
      fields: [
        { name: 'status', type: 'str', required: true, description: '"ok" | "degraded"', example: 'ok' },
        { name: 'version', type: 'str', required: true, description: 'App version', example: '1.0.0' },
        { name: 'environment', type: 'str', required: true, description: '"development" | "production"', example: 'development' },
        { name: 'services', type: 'dict[str, str]', required: true, description: 'Downstream service statuses', example: null },
      ],
    },
  },
  {
    id: 'run_agent',
    method: 'POST', path: '/api/v1/run',
    description: 'Trigger the LangGraph multi-agent graph. Returns a thread_id to poll with GET /status/{thread_id}. Blocked when kill-switch is active.',
    handlerFn: 'trigger_run',
    filePath: 'src/api/routes/agents.py', lineNumber: 33,
    techIds: ['fastapi', 'langgraph', 'claude', 'redis', 'arq', 'pydantic'],
    tags: ['Agents'],
    requiresAuth: true,
    requestBody: {
      name: 'RunAgentRequest',
      fields: [
        { name: 'task', type: 'str', required: true, description: 'Natural-language arbitrage task (10–1000 chars)', example: 'Find trending electronics under $50 with 30% margin' },
        { name: 'thread_id', type: 'str | None', required: false, description: 'Resume an existing LangGraph thread', example: null },
        { name: 'max_budget_usd', type: 'float', required: false, description: 'Max ad spend (0–500 USD)', example: 100.0 },
        { name: 'target_categories', type: 'list[str]', required: false, description: 'Product categories to search', example: null },
        { name: 'dry_run', type: 'bool', required: false, description: 'Simulate without placing real orders', example: false },
      ],
    },
    response: {
      name: 'AgentRunResponse',
      fields: [
        { name: 'thread_id', type: 'str', required: true, description: 'LangGraph thread ID — use to poll status', example: 'f47ac10b-58cc-4372-a567-0e02b2c3d479' },
        { name: 'status', type: 'RunStatus', required: true, description: '"pending" | "running" | "completed" | "failed" | "killed"', example: 'pending' },
        { name: 'message', type: 'str', required: true, description: 'Human-readable status', example: 'Agent graph started' },
      ],
    },
  },
  {
    id: 'run_status',
    method: 'GET', path: '/api/v1/status/{thread_id}',
    description: 'Poll the status of a running agent thread. Returns current node, products found, ad spend, and final result when complete.',
    handlerFn: 'get_run_status',
    filePath: 'src/api/routes/agents.py', lineNumber: 57,
    techIds: ['fastapi', 'redis', 'langgraph'],
    tags: ['Agents'],
    requiresAuth: false,
    response: {
      name: 'RunStatusResponse',
      fields: [
        { name: 'thread_id', type: 'str', required: true, description: 'Thread identifier', example: 'f47ac10b-...' },
        { name: 'status', type: 'RunStatus', required: true, description: '"pending" | "running" | "completed" | "failed" | "killed"', example: 'running' },
        { name: 'current_node', type: 'str | None', required: false, description: 'Active LangGraph node', example: 'ecommerce_manager' },
        { name: 'products_found', type: 'int', required: true, description: 'Products discovered so far', example: 12 },
        { name: 'orders_placed', type: 'int', required: true, description: 'Supplier orders placed', example: 0 },
        { name: 'ad_spend_usd', type: 'float', required: true, description: 'Total ad spend this run', example: 47.20 },
        { name: 'error', type: 'str | None', required: false, description: 'Error message if failed', example: null },
        { name: 'result', type: 'dict | None', required: false, description: 'Final output when completed', example: null },
      ],
    },
  },
  {
    id: 'kill_switch',
    method: 'POST', path: '/api/v1/kill-switch',
    description: 'Emergency stop. Immediately halts all running agent threads, sets kill-switch flag. Fully audit-logged. Requires JWT auth.',
    handlerFn: 'activate_kill_switch',
    filePath: 'src/api/routes/agents.py', lineNumber: 66,
    techIds: ['fastapi', 'python', 'pydantic'],
    tags: ['Agents'],
    requiresAuth: true,
    requestBody: {
      name: 'KillSwitchRequest',
      fields: [
        { name: 'reason', type: 'str', required: true, description: 'Reason for emergency stop (min 5 chars)', example: 'Unexpected spend spike detected' },
        { name: 'operator', type: 'str', required: true, description: 'Operator name or email for audit log', example: 'itzik@example.com' },
      ],
    },
    response: {
      name: 'KillSwitchResponse',
      fields: [
        { name: 'killed', type: 'bool', required: true, description: 'Always true on success', example: true },
        { name: 'threads_stopped', type: 'int', required: true, description: 'Number of running threads halted', example: 2 },
        { name: 'message', type: 'str', required: true, description: 'Audit message', example: 'Kill-switch activated by itzik@example.com' },
      ],
    },
  },
  {
    id: 'invoke_tool',
    method: 'POST', path: '/api/v1/tools/invoke',
    description: 'Invoke any MCP tool directly by name (dev/test only). Useful for manual testing without running the full graph.',
    handlerFn: 'invoke_tool',
    filePath: 'src/api/routes/agents.py', lineNumber: 81,
    techIds: ['fastapi', 'mcp', 'python'],
    tags: ['Agents'],
    requiresAuth: true,
    requestBody: {
      name: 'TestToolRequest',
      fields: [
        { name: 'tool_name', type: 'str', required: true, description: 'MCP tool name', example: 'search_trending_products' },
        { name: 'arguments', type: 'dict', required: false, description: 'Tool keyword arguments', example: null },
      ],
    },
    response: {
      name: 'ToolCallResponse',
      fields: [
        { name: 'tool_name', type: 'str', required: true, description: 'Echoed tool name', example: 'search_trending_products' },
        { name: 'success', type: 'bool', required: true, description: 'True if no exception', example: true },
        { name: 'result', type: 'Any | None', required: false, description: 'Tool return value', example: null },
        { name: 'error', type: 'str | None', required: false, description: 'Exception message if failed', example: null },
        { name: 'duration_ms', type: 'float', required: true, description: 'Execution time in milliseconds', example: 234.5 },
      ],
    },
  },
  {
    id: 'shopify_order_webhook',
    method: 'POST', path: '/webhook/shopify/order',
    description: 'Shopify orders/create webhook. Validates HMAC-SHA256 signature, enforces order-value guardrail, enqueues fulfillment task.',
    handlerFn: 'shopify_order_created',
    filePath: 'src/api/routes/webhooks.py', lineNumber: 31,
    techIds: ['fastapi', 'shopify', 'arq', 'python'],
    tags: ['Webhooks'],
    requiresAuth: false,
    requestBody: {
      name: 'ShopifyOrderWebhook',
      fields: [
        { name: 'id', type: 'int', required: true, description: 'Shopify order ID', example: 12345 },
        { name: 'email', type: 'str', required: true, description: 'Customer email', example: 'customer@example.com' },
        { name: 'financial_status', type: 'str', required: true, description: '"paid" | "pending" | "refunded"', example: 'paid' },
        { name: 'total_price', type: 'str', required: true, description: 'Total price as numeric string', example: '49.99' },
        { name: 'line_items', type: 'list[dict]', required: true, description: 'Ordered items', example: null },
      ],
    },
    response: {
      name: 'WebhookAck',
      fields: [
        { name: 'received', type: 'bool', required: true, description: 'Always true on success', example: true },
        { name: 'order_id', type: 'int | None', required: false, description: 'Echoed order ID', example: 12345 },
        { name: 'queued_for', type: 'str | None', required: false, description: '"fulfillment_agent" | "manual_review"', example: 'fulfillment_agent' },
      ],
    },
  },
];
