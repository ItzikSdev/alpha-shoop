# src/cj_mcp — CJ Dropshipping over REAL MCP

This package is a **genuine Model Context Protocol client** to CJ's official MCP
server. It exists to keep the naming honest and to reach CJ data our REST tools
don't.

## Why this is separate from `src/mcp_tools/`

`src/mcp_tools/` is **not** an MCP server despite the name — it's an in-process
Python function registry (`server.py` = a dict + `invoke_tool()`), and its CJ
integration (`sourcing.py`) calls CJ's **REST API v2.0** over httpx. The `mcp` in
`mcp_tools` and in the `cj_mcp_key` setting describes intent, not protocol.

This folder is the real thing: JSON-RPC 2.0 over CJ's **StreamableHTTP** endpoint.

| | `src/mcp_tools/sourcing.py` | `src/cj_mcp/` (this) |
|---|---|---|
| Protocol | REST (httpx GET) | **MCP** (JSON-RPC 2.0 / SSE) |
| Endpoint | `developers.cjdropshipping.com/api2.0/v1` | `developers.cjdropshipping.cn/mcp/<token>` |
| Auth | `CJ-Access-Token` header | same JWT, embedded in the URL path |

## REST vs MCP — the honest picture

CJ's MCP wraps the **same backend**, so it is **not** a richer source of product
*detail*: REST `product/query` already returns ~55 fields (many we currently drop
in `search_trending_products`). MCP's value is **operations the REST subset we use
doesn't expose**:

- `get_product_inventory(pid, countryCode)` — live warehouse stock by destination country
- `get_tracking_info(trackNumbers)` — live shipment tracking
- plus disputes, warehouses, private inventory, webhooks, save-to-shop

## Usage

```python
from src import cj_mcp

stock = await cj_mcp.get_product_inventory("1665261893595959296", "US")
track = await cj_mcp.get_tracking_info(["CJPACKET123456"])
tools = await cj_mcp.ping()   # connectivity check → list of MCP tool names
```

Or via the agent tool registry (delegates here):
`cj_mcp_product_inventory`, `cj_mcp_tracking_info`.

## Config

- **Token**: `settings.cj_mcp_key` (the CJ access-token JWT — verified to also
  authenticate the MCP endpoint).
- **Endpoint override**: `CJ_MCP_URL` env (default `https://developers.cjdropshipping.cn/mcp`).
  Use the `.cn` host — `.com` returns 405 for the MCP path.

## Rate limits

CJ throttles this endpoint hard: ~1 QPS and a per-IP concurrent-user cap
("Too Many Requests, one ip limit 3 users"). The client serialises calls behind a
lock with a min interval and retries on the throttle message, surfacing
`CJMCPThrottled` when it can't recover. Don't hammer it.
