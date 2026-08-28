# Decisions Log — alphaforbaby.com

Chronological record of diagnostics and fixes, kept here so the history isn't
scattered across Telegram/chat. Newest session at top. Each entry: what was
found, what was done, current status.

---

## 2026-08-17 — Full diagnostic + fix session

### 1. Checkout root cause (0/26 completions)
26 checkout attempts, 0 completions. Traced through several layers before
landing on the real cause:
- First layer: **duplicate Hyp payment providers** installed on the store —
  a native Hyp app integration *and* an offsite/redirect Hyp integration both
  active at once, which can produce an inconsistent checkout. Deduped down to
  one (the native integration).
- Real blocker, found after deduping: **Hyp clears transactions through MAX**
  (the underlying acquirer), and the MAX merchant account attached to this
  store only supports **ILS settlement** — while the store's listing/checkout
  currency is **USD**. Every USD charge attempt has nowhere valid to clear,
  so checkout fails regardless of anything else being correct.
- **Fix in progress, not yet resolved:** MAX is opening a **USD / multi-currency
  business account**. ETA ~2 business days from 2026-08-16 (i.e. around
  2026-08-18/19).
- **Status:** BLOCKED on MAX, external dependency. This is the #1 blocker to
  sale #1 — see the Advisor charter (`src/org/seed.py`) and
  `docs/VISION_ROADMAP.md`.

### 2. Catalog fixes
- Restored a variant that had reverted to a **$0 price**.
- Cleaned **supplier-leaked alt text** across 97 images (CJ warehouse/SKU
  language that had leaked into `alt` attributes instead of clean,
  customer-facing copy).
- **3 products permanently stuck** on a Shopify-side bug: the Storefront API's
  `encodedVariantAvailability` field stayed empty (version-prefix only)
  despite real CJ stock and a populated `encodedVariantExistence` — every
  size/color showed "sold out" with Add to Cart disabled, confirmed against
  the actual rendered HTML, not just the API response. A no-op
  `productVariantsBulkUpdate` re-index attempt (12 checks over ~6 minutes) did
  not clear it, and no other product in the 34-product catalog showed the same
  mismatch. Archived full product data (titles, variant SKUs, CJ ids, pricing,
  image URLs) to
  `stores/shopify/hydrogen-alphaforbaby/changelog/deleted-products-encodedVariantAvailability-2026-08-16.md`,
  then deleted all 3 via `productDelete`. Open item: worth a Shopify support
  ticket if this recurs, since it hit 3 of 34 recently-edited products with no
  clear pattern.
  (Full detail: `stores/shopify/hydrogen-alphaforbaby/changelog/CHANGELOG.md`,
  2026-08-16 09:32 entry.)

### 3. Sol reliability
- **Hardcoded 180s client timeout** was the root cause of an 83%/65% run
  timeout rate — Sol's real tool-loop calls (CJ search, Shopify pushes) often
  ran longer than that under load. Raised to **600s**
  (`src/org/agent_loop.py`, the `get_llm("shopify_dev", ...)` call).
- **Wrong Admin API version** was causing false "product doesn't exist"
  conclusions on some lookups — every run re-investigated from scratch and
  landed on the same wrong answer, because the broken lookup itself was the
  bug, not the product. Fixed; Shopify Admin calls now consistently target
  API version `2024-07` (`src/mcp_tools/shopify.py`).
- Added an **`ask_teammate` duplicate-question cooldown**: a repeated question
  about the same product/id within a 10-minute window now reuses the last
  real (non-generic) answer instead of re-asking and burning another paid
  Haiku call (`src/org/agent_loop.py`, `_recent_substantive_answer`).

### 4. Video pipeline
- Found and fixed a **dispatch bug**: `_agent_act_video` /
  `_agent_act_rotation_video` / `_agent_act_image` were not honoring an exact
  product `gid` when one was named in the request — they'd loosely pick a
  product (often `products[0]`) instead. Now requires an **exact gid match**
  when one is named, and **fails loudly** ("product not found") instead of
  silently substituting the wrong product (`src/org/conversation.py`).
- Result: **9 of 10** products missing a 360° rotation video are now
  resolved — 4 by attaching an already-generated video that had silently
  landed on the wrong product, 5 by regenerating after diagnosing the real
  cause of the generation failures as a **Gemini per-minute rate limit**, not
  a daily quota (so retrying with pacing, not waiting a day, was the fix).
  (Uploads logged in
  `stores/shopify/hydrogen-alphaforbaby/changelog/CHANGELOG.md`, 2026-08-16
  14:58–15:49 entries.)

### 5. `train_agent` / `record_lesson` fix
- Root cause: `train_agent(target_role, topic)` matched **strictly** on the
  exact DB role string, but meeting/heartbeat decisions kept proposing a
  display name ("Ava", "Sol") or a retired role instead — neither ever
  matched, so the call silently failed. Of **246 historical calls**, 226
  failed this way; of those, **103** would have succeeded with loose
  matching (display name for a still-active agent), the other 123 genuinely
  targeted retired agents/roles and were correctly unresolvable.
- Fix: `resolve_agent()` in `src/org/lifecycle.py` — tries exact role, then
  case-insensitive role, then case-insensitive name; on no match, distinguishes
  "matches a departed agent" from "matches nobody" in the log instead of a
  generic silent failure. `record_lesson` (`src/org/executor.py`) extended
  with an optional `target_role` so a lesson can land on one specific agent,
  not just the company-wide pool.
- Deeper bug found while verifying: even a correctly targeted lesson never
  reached Sol's *real* working prompt — `agent.memory["lessons"]` was read by
  the meeting persona summary and the chat fallback, but not by
  `run_sol_task`'s actual system prompt. Fixed `_charter()` in
  `src/org/agent_loop.py` to include recent lessons. Verified end-to-end live
  against the DB.

### 6. Advisor agent added
- New role in `src/org/seed.py`. Single mandate: **get alphaforbaby.com to
  its first real sale**, and flag any agent activity that drifts from that.
- Authority: `create_ticket`/`close_ticket` only — no `assign`/
  `ask_teammate`/`dispatch_to_agent`; Ava still owns routing.
- Cadence: **weekly**, code-enforced via a dedicated tick
  (`_advisor_tick`, `src/org/heartbeat.py`), excluded from the general
  per-turn round robin.
- Explicit out-of-scope list (regardless of who proposes it, until sale #1):
  new marketplaces (AliExpress/Amazon/eBay), new agent roles beyond fixing
  existing ones, any "platform/architecture" work not tied to shipping the
  first sale.
- Live in the roster as of this session — 7 active agents (Ava, Sol, Reel,
  Nora, Milo, Kai, Advisor).

### 7. `sourcing_paused` enforcement gap
- Audited every timed loop in the codebase (heartbeat.py + main.py) — 12
  total. Found several that bypassed the `sourcing_paused` flag entirely:
  `_ticket_tick` (ran whatever a ticket said, unconditionally, every 15 min)
  and a disconnected legacy `_daemon_loop` (a second, orphaned work-dispatch
  path with zero coupling to `company.daemon`; currently disabled by
  default).
- Found the gap was **live**: 9 stale critical tickets, auto-opened by
  earlier `_sourcing_tick` crashes (titles like *"Error in Autonomous
  Sourcing Cycle for 'baby girl dress'"*), were sitting in the backlog and
  actively re-dispatching Sol into sourcing-flavored work through this side
  door — one closed itself mid-audit, confirming it was firing in real time.
  Closed all 9.
- Fixes: `_ticket_tick` now filters sourcing-flavored tickets out of its
  candidate queue while paused (`_is_sourcing_ticket()`,
  `src/org/heartbeat.py`); `execute_decisions` now hard-gates `build_store`
  and `boost_store` in `MARKETING` mode on the same flag
  (`src/org/executor.py`) — covers both the meeting cycle (`org_tick`) and
  the CEO's regular heartbeat decisions from one chokepoint.
- `_reel_image_scan_loop` and `_stock_watch_tick` were triaged but
  deliberately **not** touched — lower priority, already disabled or
  non-scope-expanding.

---

*Format: newest session on top. Add new entries above this line, don't edit
past ones except to correct a factual error (note the correction inline).*
