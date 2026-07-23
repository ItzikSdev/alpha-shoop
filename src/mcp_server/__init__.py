"""MCP servers this repo exposes to external clients (e.g. OpenClaw).

Distinct from `src/cj_mcp/` (an MCP *client* for CJ's server) and `src/mcp_tools/`
(an in-process REST-backed function registry) — this package is the *server* side,
speaking real MCP over stdio so external tools can drive this system's own agents.
"""
