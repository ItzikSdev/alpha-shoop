---
name: shop-context
description: Load full context on a specific Shopify store in stores/shopify/ (e.g. alphaforbaby) — its docs, current state/changelog, and how the agent that runs it (Sol) actually operates it. Use before making any change to a store, before answering questions about a store's architecture/history/status, or when the user asks to "read the docs for", "onboard on", or "catch me up on" a shop.
---

# Shop context loader

This repo can host multiple Shopify stores under `stores/shopify/hydrogen-<slug>/`. The model is
**one dedicated autonomous agent per store** — today there is exactly one store
(`hydrogen-alphaforbaby`) and exactly one agent, **Sol**, who owns it end to end. Sol does NOT
own every store as a blanket rule; he owns `hydrogen-alphaforbaby` specifically because that's
currently the only store that exists. When a new store is added, the owner creates a new
dedicated agent for it (see `src/org/seed.py` for how the roster is defined) — don't assume Sol
picks up a second store automatically. Each store is self-documenting (README, changelog,
docs/, a persistent agent-memory file) so you can identify its owning agent from its own docs
(`docs/HANDOFF.md` / `docs/STORE_MEMORY.md` name the agent) rather than assuming it's Sol.

## 0. Who is responsible for what (read this before touching anything)

**The store's owning agent (Sol, for `hydrogen-alphaforbaby` today) runs it end to end — code,
build, QA, deploy.** You (the assistant) are read-only on any `stores/shopify/hydrogen-<slug>/`
folder: you investigate, diagnose, explain, and design the fix, but you do **not** edit files
under a store folder, and you never run `npm run build`, `npm run dev`, or a deploy script
against one. That line was drawn explicitly by the owner after a session where the assistant
edited store code directly — see
`~/.claude/projects/-Users-itziksavaia-Documents-git-alpha-shoop/memory/sol_owns_store_builds.md`.

When a store needs a real change:
1. **Identify the owning agent** for that store (Sol, for `hydrogen-alphaforbaby`; check the
   store's own docs if there's ever more than one store/agent).
2. **Diagnose and write up the task**, not the code. State the problem, the root cause you
   found (file/line if useful for the agent to start from), and the desired outcome — don't hand
   over a diff to paste in, hand over a brief the agent can execute end-to-end himself (he'll
   read the same skill docs listed below before acting).
3. **Hand it to the owning agent.** For Sol, either:
   - `POST /api/v1/org/sol {"task": "<brief>", "store_slug": "<slug>", "max_steps": 25}` —
     runs Sol's tool-use loop synchronously (the call blocks until his run ends), narrating
     every step to Slack as he goes. This is the "watch until Sol finishes" path: the HTTP
     response only returns once he's done (or hit max_steps/a blocker).
   - Or open a ticket for his normal queue: `POST /api/v1/org/tickets {"title", "description",
     "store_id": "<slug>"}` (auto-assigned to Sol with a priority + SLA deadline), then poll
     `GET /api/v1/org/tickets?status=doing` (or `done`) until it clears.
   - Or just post in the Slack channel Sol listens on — the informal path from `docs/HANDOFF.md`.
4. **Watch, don't assume.** Report back to the user based on what the agent actually did — the
   `/org/sol` response body, the ticket's final status, or the store's own
   `docs/STORE_MEMORY.md` "Recent changes" / `CHANGELOG.md` tail — not on what you asked for.
   If the run didn't finish or got blocked, say so plainly rather than reporting success.

The rest of this skill (reading docs, understanding the store) is exactly what you should do
regardless — you need the full picture to write a good task brief and to judge the result when
the owning agent is done.

## 1. Find the store

```bash
ls stores/shopify/                       # e.g. hydrogen-alphaforbaby
ls stores/shopify/hydrogen-<slug>/store-profiles/
```

If the user names a brand/domain instead of a slug, match it against `store-profiles/*/theme.config.json`
(`brand.name`) or the README title — don't guess the folder name.

## 2. Read in this order (skip nothing that exists)

For `stores/shopify/hydrogen-<slug>/`:

1. **`README.md`** — what the store is, architecture (Hydrogen/Oxygen, template-driven via
   `theme.config.json`), local dev, CI/CD, legal-pages setup.
2. **`docs/STORE_MEMORY.md`** — Sol's own persistent memory, injected into his prompt. This is
   the single most current source of "what's true right now" (renames, recent fixes, known gaps).
   Read it in full even though it's short.
3. **`docs/HANDOFF.md`** (if present) — snapshot of what exists, how to run Sol, open
   issues/owner-TODOs. May be stale relative to STORE_MEMORY.md — STORE_MEMORY wins on conflicts.
4. **`docs/AGENT_WORKFLOW.md`** — the exact loop Sol must run after any change (build → QA/SEO/UX
   checks → verify live → deploy → log to Slack + CHANGELOG). This is how Sol works, not just what
   the store is — read it fully.
5. **`docs/{QA,SEO,CI_CD}.md`** — the check docs Sol runs against every change, and the deploy
   mechanics (`scripts/deploy.sh <slug>`, local build + `shopify hydrogen deploy`, no GitHub Actions).
6. **`docs/PRODUCT_UPLOAD_PIPELINE.md`**, **`docs/RAG_CJ_DATA_PLAN.md`**, **`docs/sol_agent_improvement_roadmap.md`**
   — read if the question touches product sourcing/data or Sol's own roadmap; skip otherwise.
7. **`store-profiles/<slug>/theme.config.json`** — the live brand config (colors, copy, nav,
   legal). Do **not** open `store-profiles/<slug>/store.env` or `.env` — they hold live Shopify/Oxygen
   tokens; if you need a value from them, ask the user rather than printing the file.
8. **`CHANGELOG.md`** — this file gets large (100+ KB). Don't read it whole; tail the recent
   history instead:
   ```bash
   tail -n 150 stores/shopify/hydrogen-<slug>/CHANGELOG.md
   ```
   Grep for a topic if you need older history: `grep -n -i "<topic>" CHANGELOG.md`.

## 3. Read how Sol actually works (cross-store, not per-store)

- **`stores/shopify/skills/SKILLS_MAP.md`** — the routing table Sol uses to pick a skill per
  request type (product sourcing, UI/UX, store audit, Hydrogen code, Admin GraphQL, metafields,
  Liquid, Functions, CLI). Read this to know which skill governs the kind of change you're about
  to reason about, then open that specific skill file (`stores/shopify/skills/*.md` or
  `stores/shopify/skills/.claude/skills/shopify-*/SKILL.md`) — don't reload all of them.
- **`stores/shopify/CJ_AGENT_HYDROGEN_AUTOMATION_GUIDE.md`** — the bigger picture: how CJ product
  sourcing, Sol, and the Hydrogen storefront fit together end-to-end.
- If you need Sol's runtime/tool wiring rather than his docs (what tools he actually has, how the
  loop is invoked), that's code, not docs: `src/org/agent_loop.py`, `src/org/seed.py` (roster),
  `src/org/tickets.py`. Only open these if the docs above don't answer the question.

## 4. Synthesize, don't dump

After reading, give the user (or use internally before editing) a short synthesis covering:
- What the store is + current live domain/state.
- What changed recently (from the CHANGELOG tail + STORE_MEMORY.md).
- What rules/workflow govern changes to it (from AGENT_WORKFLOW.md — build/QA/SEO/deploy/log).
- Open issues/owner-TODOs still outstanding.

Don't paste full file contents back to the user — cite `file:line` and summarize. If something in
STORE_MEMORY.md or HANDOFF.md looks stale (contradicted by the changelog tail or by reading the
actual code), say so and prefer the more recent source.