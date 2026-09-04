# src/tiktok_mcp — TikTok Ads over REAL MCP

A **genuine Model Context Protocol** server + client pair for read-only TikTok
Ads reporting (spend, impressions, clicks, CTR, conversions). Built as our own
code — not a vendored third-party repo, not a paid third-party relay — so the
only parties in the data path are this process and TikTok's own API.

## Why this is separate from `src/mcp_tools/`

`src/mcp_tools/` is **not** an MCP server despite the name — it's an in-process
Python function registry (`server.py` = a dict + `invoke_tool()`) that calls
vendor REST APIs directly over httpx. `src/cj_mcp/` and this package are the
real thing: actual JSON-RPC 2.0, spoken over an actual MCP transport.

| | `src/mcp_tools/*` | `src/cj_mcp/` | `src/tiktok_mcp/` (this) |
|---|---|---|---|
| Protocol | REST (httpx) | **MCP** (JSON-RPC / SSE) | **MCP** (JSON-RPC / stdio) |
| Server | vendor's own REST API | CJ's **remote** MCP endpoint | **our own** local MCP server |
| Transport | HTTP GET/POST | StreamableHTTP | stdio subprocess |

`server.py` is a small FastMCP server that wraps TikTok's documented Marketing
API v1.3 (`business-api.tiktok.com/open_api/v1.3/...`) as MCP tools. `client.py`
spawns it as a subprocess (`python -m src.tiktok_mcp.server`) per call and
talks to it over stdio using the official `mcp` SDK — same shape as talking to
any external MCP server, except this one runs on your own machine.

## One-time setup (the owner does this — can't be automated)

1. Go to `business-api.tiktok.com/portal` → create a Developer app → add the
   **Marketing API** product → request read-only **Reporting** + **Ad Account**
   scopes. Note the App ID and App Secret.
2. Set `TIKTOK_APP_ID` / `TIKTOK_APP_SECRET` in `.env`.
3. In chat, ask Kai (or call `tiktok_ads_login` directly) — it returns an
   authorize URL. Open it, log in, approve access.
4. TikTok redirects to `TIKTOK_OAUTH_REDIRECT` (default
   `https://alphaforbaby.com/tiktok/callback` — a real domain, since TikTok
   rejects localhost/loopback redirect URIs outright; it doesn't need to be a
   live server) with an `auth_code` query param. Copy that value and send it
   back to Kai, or call `tiktok_ads_complete_auth(auth_code=...)` directly.
5. The access token + advertiser id are persisted to `.env` — every future
   process picks them up automatically, same "one source of truth" convention
   as `src/mcp_tools/shopify_auth.py`'s `persist_shopify_token`.

## Usage

```python
from src import tiktok_mcp

status = await tiktok_mcp.auth_status()
report = await tiktok_mcp.get_ads_report("2026-08-01", "2026-08-07")
tools = await tiktok_mcp.ping()   # connectivity check → list of MCP tool names
```

Or via the agent tool registry (delegates here): `tiktok_ads_login`,
`tiktok_ads_complete_auth`, `tiktok_ads_auth_status`, `tiktok_ads_campaigns`,
`tiktok_ads_report`.

## Scope

Read-only reporting only. There is no create/edit/pause-campaign tool here —
any real spend/campaign change stays a human decision, made directly in TikTok
Ads Manager.

## Config

- `TIKTOK_APP_ID` / `TIKTOK_APP_SECRET` — the Developer app credentials.
- `TIKTOK_ACCESS_TOKEN` / `TIKTOK_ADVERTISER_ID` — minted by
  `tiktok_ads_complete_auth`, persisted to `.env` automatically.
- `TIKTOK_OAUTH_REDIRECT` — optional override of the OAuth redirect URI
  (default `https://alphaforbaby.com/tiktok/callback`; must be a real domain —
  TikTok rejects localhost/loopback — and must match what's registered on the
  Developer app exactly).
