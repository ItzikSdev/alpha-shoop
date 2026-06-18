# Alpha Shoop — Status & Next Steps

You are the project intelligence for **Alpha Shoop**.
When invoked, read the project state and report exactly where we stopped and what to do next.

## Step 1 — Read these files

Read all of them before responding:

**Changelog & architecture**
- `CHANGELOG.md` — source of truth for what's done (newest first)
- `docs-app/public/mcp.mmd` — MCP layer diagram
- `docs-app/src/pages/Architecture.tsx` — full system diagram (SYSTEM_MERMAID constant)

**Agents & tech stack**
- `docs-app/src/pages/Agents.tsx` — all AI agents, their models and responsibilities
- `docs-app/src/pages/Technologies.tsx` — full tech stack

**Core source**
- `src/agents/director.py`
- `src/agents/workers/store_setup.py`
- `src/mcp_tools/shopify_theme.py`
- `src/mcp_tools/shopify.py`
- `src/mcp_tools/sourcing.py`
- `src/api/routes/auth.py`

## Step 2 — Report

Structure your response exactly like this:

### Completed (last session)
Pull from CHANGELOG — last 3–5 entries, one line each.

### Open issues
Each with severity:
- 🔴 blocking — pipeline can't run
- 🟡 important — pipeline runs but output is wrong/incomplete  
- 🟢 nice-to-have

### Recommended next step
One task. Name the exact files and functions to change.

### Backlog
Everything else, ordered by impact.

## Step 3 — After completing any task

Append to the **top** of `CHANGELOG.md` (below the `# Changelog` header):

```
## [YYYY-MM-DD HH:MM] — Title

What was done, which files changed, what problem it solved, any caveats.
```
