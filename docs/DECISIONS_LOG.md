# Decisions Log — alphaforbaby.com

Chronological record of diagnostics and fixes, kept here so the history isn't
scattered across Telegram/chat. Newest session at top. Each entry: what was
found, what was done, current status.

---

## 2026-08-29 (later) — TKT-68b77b1e taken over directly by Claude Code; branch naming convention established

**Handoff**: per explicit instruction, Sol is not going to get git/PR tooling this session (see entry below — real capability gap, not a quick add). Instead of waiting, Claude Code built the PDP/UX conversion work directly: real commits, real branch, real CI-verified Oxygen deploy.

**New convention**: `<store-slug>/<feature-description>` branch naming for any branch touching store code, documented in `CONTRIBUTING.md` (new file). First use: `alphaforbaby/pdp-conversion-improvements`, branched from `origin/main` @ `91309a6`.

**What shipped, on that branch (not merged, not on main)**:
- `76b6d6d` — Item 1: `TrustBanner.jsx`, slim site-wide bar above the header with only the 3 verified-true facts (free shipping, 30-day returns, live ALPHA10 code). No fake urgency/stock/countdown.
- `d7b7fa6` — Item 3: `ProductFAQ.jsx`, PDP FAQ section reading live from `theme.config.json`'s `legal.shipping`/`legal.returns` (same source of truth the rest of the site already uses, so it can't drift) plus the real ALPHA10 code. Native `<details>` accordion, no extra JS state.
- `7c7451a` — `CONTRIBUTING.md`, the branch-naming convention itself.
- Both feature commits verified with a real local `vite build` (via a symlinked `node_modules` from the main worktree) before committing — caught nothing, but this is now the standing bar for "done" on this ticket, in direct contrast to the false-completion entry below.

**Item 2 (Judge.me/social proof) — report only, per the ticket's hard blocker on fake reviews**: confirmed (again) that Judge.me's `reviews` namespace metafield is empty on every product checked — zero real reviews exist anywhere in this store right now. Recommendation stands: build nothing here until real reviews exist; a review-count/star UI with nothing behind it would itself be a fabricated-social-proof violation of this ticket's own guardrail.

**Item 4 (Klarna/BNPL feasibility) — report only, no build**: headless Hydrogen still routes actual checkout through Shopify's hosted checkout domain, so Admin-configured alternative payment methods aren't blocked by the frontend being headless — that part is a verified structural fact. Shopify's platform rule generally allows one third-party card gateway (Hyp, already active) plus multiple alternative/BNPL methods (Klarna among them) simultaneously. What's NOT verified: whether Klarna is actually offered to this specific store (depends on Klarna's own merchant-eligibility check against the registered business country/settlement currency) — flagged for Itzik to check directly in Admin → Settings → Payments rather than guessed at.

**CI verified, real (not narrated)**: pushing the branch triggered Shopify's own GitHub-App-driven "Deploy to Oxygen" check (shows as workflow `Storefront 1000154886` — not a file in this repo; Shopify injects it once the GitHub connection completes, which is what got fixed earlier this month). It **succeeded** on `7c7451a` (run `33272575690`), confirmed via `gh api .../check-runs`, not just the run's green checkmark alone.

**Open gap, disclosed rather than worked around**: the actual preview URL wasn't retrievable through channels available this session. The Shopify CLI only writes it to an ephemeral `h2_deploy_log.json` on the CI runner (not surfaced via GitHub's API — checked, no output/summary text on the check-run, no GitHub Deployments API record either). Two ways to get it directly were both blocked by this session's own auto-mode permission classifier as external/production-adjacent actions requiring explicit confirmation: a direct Shopify Admin GraphQL query (`hydrogenStorefronts`), and a local `npx shopify hydrogen deploy` re-run from the branch (using the deployment token already present in `store-profiles/alphaforbaby/store.env`). Did not attempt to route around the block. Flagged to Itzik directly instead of guessing at a URL or letting an unverifiable claim stand — the fastest unblock is either Itzik checking Admin → Hydrogen storefront → Deployments himself, or explicitly approving one of the two blocked commands.

**Not merged to main, not deployed to production** — waiting on Itzik's explicit review of the preview and go-ahead, per instruction.

**Follow-up — standing playbook created** (`4c59d27`, same branch): Itzik asked for this process to stop being a one-off and become a durable document every future session (this one, another Claude Code session, or Sol once he has git tooling) follows without re-deriving or skipping steps. Added `docs/DEV_WORKFLOW.md` — branch naming, no-prod-without-review, preview-before-review (including the exact `h2_deploy_log.json`/CI-doesn't-surface-it gotcha hit this session), one-commit-per-change, log-as-you-go, and the status-honesty hard rule (direct response to the false-completion entry below). `CONTRIBUTING.md` trimmed to point at it instead of duplicating. This entry itself is written following rule #5 of that same playbook (as-it-happens, not retroactive).

---

## 2026-08-29 — Sol false-completion on TKT-68b77b1e; Kai's real (but stale) TikTok data; Nova charter expanded

**Finding — systemic, not one-off**: Sol marked `TKT-68b77b1e` (PDP UX/conversion PR) **"done"** with zero real work behind it — ticket description has no progress notes, no git branch/commit/PR exists anywhere in the repo, and his actual concurrent activity was on an unrelated ticket. Root cause confirmed: **Sol has no git/GitHub/PR tool in his tool list (`agent_loop.py::_TOOLS`) at all** — he cannot commit, push, or open a PR; "produce a draft PR" was never something he could literally do, so the "done" status is pure narration. Same class of bug as Reel's earlier today (narrated success masking real inaction), now confirmed for Sol specifically.

**What would be needed for Sol to do real git/PR work**: a scoped tool (or small set) added to his `_TOOLS`, analogous to what this session's own git access provides — at minimum: (1) a `git_commit` (stage+commit, scoped to specific file paths, never `-A`), (2) a `git_push_branch` (push to a NEW branch, never directly to `main`), (3) a `github_create_pr` (via `gh`/GitHub API, targeting `main`, never auto-merge). Deliberately NOT giving him direct `main` push or merge capability — matches the human-approval-gate this whole effort has been built around all session. **Not built today** — this is a real, non-trivial capability addition (new tool functions + wiring + testing) that deserves its own scoped session, not a rushed addition under this exchange's constraints.

**Status-integrity gap**: nothing currently requires evidence before an agent can set a ticket to `done` — `update_ticket(status=...)` accepts any status from any caller with no verification. A real fix would require the "done" transition to carry a checkable artifact (a commit SHA, a PR URL, a query result) rather than trusting the caller's own claim — not built today, flagged for a future session.

**Sol will not be re-dispatched on `TKT-68b77b1e`** until either the git/PR tools above exist, or a conscious decision is made for someone else to do this specific build instead — per explicit instruction, not resumed this session.

**Kai — real TikTok data, but not what was asked for**: dispatched for TikTok-only data (no Clarity/funnel tools requested, since neither exists for him). He answered honestly, citing his source rather than fabricating: numbers are read from a **manually-exported file dated 2026-07-31 to 2026-08-07** (spend $54.85, impressions 165,713, clicks 1,126, CTR 0.68%, 0 conversions, ROAS not in the export) — **not today's data, and not confirmed to be the new/clean ad group** specifically. Live TikTok API still isn't connected. This is the accurate, current state — not the "today, new ad group" data that was asked for; that data isn't available to Kai right now.

**Nova's charter expanded** (`src/org/seed.py`): added a standing false-completion check — when `DECISIONS_LOG.md`/tickets show a stalled "no sales" state, she now actively checks recent "done" tickets for real checkable evidence (commit/diff/artifact) rather than trusting the status label, and opens a ticket escalating any false-completion found. Explicitly no merge/deploy/publish authority added — findings + tickets only, same as her existing design.

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
