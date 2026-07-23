# RAG for CJ Product Data — Plan (not yet built)

## Problem

Sol has no reliable, searchable local copy of CJ's catalog. Today:
- `cj_search_products` (REST) works, but it's a live, on-demand call per keyword —
  no persistence, no way to browse/query past results, no semantic search ("find
  something like X we already looked at").
- CJ's MCP `search_products` is broken right now (returns 0 records for every
  keyword tested 2026-07-08 — see `STORE_MEMORY.md`), so there's no MCP-based
  catalog access either.
- Every sourcing task re-searches from scratch, re-fetches full detail per
  candidate, and repeatedly re-discovers the same off-niche junk (electronics,
  adult fashion) that a persisted, filtered corpus would let us just exclude once.

## Proposed approach

A lightweight RAG layer between CJ and the upload pipeline:

1. **Ingest**: on each `cj_search_products` call (or a scheduled batch job), persist
   the full CJ detail payload (title, description, images, variants, specs,
   category) for every candidate seen — pass or reject — into a local store.
   SQLite is enough to start; add a vector index only if semantic search ("find
   more like this one") turns out to matter.
2. **Tag at ingest time**: store the niche-guard verdict (accepted/rejected + why)
   alongside each record, so rejected junk is remembered and never re-fetched or
   re-evaluated by a future run.
3. **Query surface for Sol**: a new tool, e.g. `search_local_catalog(query, filters)`,
   that searches the persisted corpus first — only falling back to a live CJ REST
   call when nothing local matches. This cuts CJ API round-trips (a real bottleneck
   this session — repeated timeouts) and gives consistent results across runs.
4. **Embeddings (optional, phase 2)**: if keyword search proves too brittle (CJ's
   own free-text search already is), embed title+description and do semantic
   similarity search locally instead of relying on CJ's search quality at all.

## Why this isn't built yet

This is new infrastructure (a data store + ingestion path + a new tool Sol calls),
not a one-shot task. Building it during a long, budget-constrained session risks
the same class of problem already hit twice today (rushed changes, incomplete
verification). It needs a dedicated session to:
- pick the storage engine (SQLite vs. a vector DB) based on actual corpus size,
- decide retention/refresh policy (CJ prices/stock change over time),
- wire the new tool into `agent_loop.py` and test it against real sourcing runs.

## Immediate, cheap alternative (no RAG needed)

Until this is built, the guard rules already in
`docs/PRODUCT_UPLOAD_PIPELINE.md` (niche denylist/allowlist, dedup-by-SKU) are the
actual mitigation in production today — they reject bad candidates per-call, just
without persisting the rejection for next time. That's the gap RAG closes.
