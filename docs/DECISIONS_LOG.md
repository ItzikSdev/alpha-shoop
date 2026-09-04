# Decisions Log — alphaforbaby.com

Chronological record of diagnostics and fixes, kept here so the history isn't
scattered across Telegram/chat. Newest session at top. Each entry: what was
found, what was done, current status.

---

## 2026-09-04 — Agent-communication routing rework; Nora's dispatch_to_agent gap flagged (not fixed)

**Ask**: change how the org communicates — stop private DMs to Itzik, increase real inter-agent talk where a real gap exists, and make the shared Telegram channel answer questions from anyone in it, not just Itzik. Explicitly out of scope: ticket creation, real-blocker escalation to Itzik, and the merge/deploy human-review gate — none of those touched.

**Found first, before changing anything**: there was no private-DM path to begin with — `TELEGRAM_CHAT_ID` was already configured as a shared group (confirmed against the real `.env`, not just code), with per-agent Telegram Topics for organization, not privacy. That item needed no fix.

**Built** (`src/org/telegram.py`, `src/org/heartbeat.py`, `src/org/fulfillment.py`, `src/mcp_tools/support_inbox.py` — uncommitted, sitting on `inline-product-expand`, see below):
1. `_is_group_message`/`_sender_name` in `telegram.py` — plain chat messages are now answered for anyone writing inside the one configured group chat, routed through the existing `route_and_respond` triage with their real name, not hardcoded as "You". Commands (`/agents`, `/manager`, `/report`) and the media approve/reject buttons stay locked to `TELEGRAM_ALLOWED_USER_ID` — those touch production/publish state, deliberately untouched.
2. `post_escalation()` — genuine "needs a human" escalations (Nora's `needs_owner_attention`, Milo's fulfillment `_escalate`) now land in the main Telegram topic with a consistent 🚨 marker, instead of being buried in an agent's own per-agent topic alongside routine tool-narration. `flag_blocker` and the Shopify-401 escalation already posted to the main topic correctly — left alone.
3. `_sourcing_tick` now asks Kai for recent ad/Clarity signal before locking in a sourcing keyword each cycle (currently a no-op in practice — sourcing is still paused per the 2026-08-17 freeze — but wired for when it resumes).
4. `_media_sweep_tick` still opens its ticket assigned to Sol (had to keep that — `_ticket_tick` only ever works tickets assigned to Sol, the only agent with a real tool loop; reassigning would have made the ticket invisible to the one thing that works it) but now also pings Reel directly and immediately with the top gaps, instead of Reel only finding out once Sol gets to the ticket.
5. Milo's fulfillment `_escalate` now pings Nora directly the moment a fulfillment error hits, in parallel with Sol's investigation — see the gap below for the limit on what that ping actually guarantees.

**Structural gap found, not fixed — same treatment as Sol's git-tooling gap (2026-08-29 entry above)**: `dispatch_to_agent` (`src/org/conversation.py`) has no real execution path for Nora. Every other specialist role it dispatches to (Shopify doers, Product Hunter, Video Producer, Growth Marketing Analyst, Nova) hits a real handler that actually does something; Nora falls through to the generic `_agent_reply` in-persona chat branch, which only produces an LLM-narrated acknowledgment — no tool call behind it. Her real, working send mechanism is `send_reply_via_resend` (`src/mcp_tools/support_inbox.py`), a deterministic function used only by her own inbox poll (`process_central_inbox`), never wired into an LLM-callable tool or into `dispatch_to_agent`'s Nora branch.

Net effect: the new Milo→Nora ping (#5 above) is a genuine, real communication link — Nora is now actually informed the moment an order fails, instead of finding out later or not at all. But her response in that flow is **narrated, not verified** — a "on it, I'll email them" reply does not confirm `send_reply_via_resend` (or any send) actually fired. Nobody should read a Nora reply in this flow as confirmation the customer was actually emailed until this gap is closed.

**What would be needed to close it**: give Nora a real execution branch in `dispatch_to_agent` (mirroring `_agent_act_video`/`_agent_act_growth`) that can actually call `send_reply_via_resend` for a customer-facing task like this. **Not built today** — out of scope for a communication-routing session, deserves its own scoped pass same as Sol's git/PR tooling still does.

**Verified**: `py_compile` clean on all four touched files. Nothing in this session's changes reaches ticket-status transitions, escalation-to-Itzik-for-real-blockers, or the merge/deploy gate — all three confirmed unchanged.

**Not committed** — sitting as uncommitted local changes on `inline-product-expand` (a branch unrelated to this work by name/purpose), same "real but uncommitted local work" situation flagged in the 2026-08-30 PR-merge-notify entry below for other in-progress work. Committing/branching this is Itzik's call, not made unilaterally here.

---

## 2026-09-02 — Kai can now actually pull and report real Clarity data

**Ask**: Kai should get real Clarity data (not just know it's installed) and be able to understand/post about it — upgrading the "ANALYTICS AWARENESS, no API access" note added 2026-08-28.

**Built**:
- `src/mcp_tools/clarity.py` — real client for Clarity's Data Export API (`GET /export-data/api/v1/project-live-insights`, Bearer token). Same honesty convention as `finance.py`: no token → `status="not_connected"` with the exact setup step (Clarity dashboard → Settings → Data Export → Add API token → `CLARITY_API_TOKEN` in `.env`); a real API failure → `status="error"` with detail; a real number only on `status="ok"`. Never a mock (deliberately not following `src/mcp_tools/ads.py`'s pattern, which still returns fabricated placeholder metrics). Field-name extraction (`_summarize()`) is defensive/best-effort — Clarity's exact response schema hasn't been confirmed against a live payload this session (no token exists yet), so it's built from documented API shape and degrades to "field not found" rather than crashing or guessing on a mismatch. `raw` always carries the untouched response through regardless.
- `src/org/conversation.py` — new `_agent_act_analytics` (mirrors the existing `_agent_act_ads`) and a small `_agent_act_growth` dispatcher in front of both: keyword-routes a message to Clarity (traffic/UX/heatmap/rage-click/etc. — see `_CLARITY_KEYWORDS`) or falls through to the existing TikTok ads path by default. Both of Kai's chat dispatch sites now call `_agent_act_growth` instead of `_agent_act_ads` directly. Also extended the routing-classifier prompt so a Clarity/UX-flavored message actually gets assigned to Kai in the first place.
- `src/org/heartbeat.py::_clarity_report_tick` — the "post" half: a real code-driven cron (same pattern as `_stock_watch_tick`, not an LLM narrating an unchecked update) that posts a real summary to Telegram as Kai. Daily by default, deliberately conservative given Clarity's own 10-requests/project/day cap on the Data Export API. Silently no-ops (not a Telegram spam) while `CLARITY_API_TOKEN` is unset — starts posting the moment the token exists, no code change needed then.
- `src/org/tool_catalog.py` / `src/org/seed.py` — Kai's tool list and charter updated to describe the real capability (replacing the old "no API access" caveat) and its real constraints (rate limit, needs the token, read-only/no site edits from a UX finding).
- `.env.example` — documented `CLARITY_API_TOKEN` next to the existing TikTok section.

**Verified without a live token** (matches this session's own status-honesty rule): a dry-run test confirmed the not-connected path returns the real setup string rather than a guessed number; `_summarize()` correctly extracts fields from a realistic mocked response and never crashes on malformed/unexpected input (4 assertions); a second dry-run confirmed `_agent_act_growth`'s keyword router correctly sends all 14 Clarity keywords to the analytics path and leaves ads-flavored messages on the existing TikTok path unchanged (3 assertions). All 7 pass. `py_compile` clean on every touched file.

**Structural note, surfaced not fixed**: none of this — nor the Kai/TikTok integration it builds on (`src/tiktok_mcp/`, `_agent_act_ads`, Kai's whole tool_catalog/seed.py entry) — exists in `origin/main` at all; it's all uncommitted local work (confirmed: `src/tiktok_mcp/` doesn't exist on `origin/main`, zero references to `_agent_act_ads`/Kai in `origin/main`'s `conversation.py`/`tool_catalog.py`/`seed.py`). The org backend runs locally from the working directory with no git-triggered deploy, so this still works today — but a large amount of real, working functionality currently exists only on one machine. Committing it is a separate, deliberate decision for Itzik to make (spans far more than this Clarity change — bundling it in unasked would mix unrelated work into one commit), not something done unilaterally here.

**Waiting on Itzik**: generate a Clarity Data Export API token (clarity.microsoft.com → Settings → Data Export → Add API token) and add it to `.env` as `CLARITY_API_TOKEN`. Everything else is ready to go the moment that's set — no restart-triggering code change needed, `_clarity_report_tick` picks it up on its next interval check.

---

## 2026-08-30 (later) — alphaforbaby migrated to a dedicated production branch

Executed in 4 gated steps, reporting back after each (per instruction), holding both PRs unmerged throughout.

**Step 1 — fixed the real, independent `storefront-theme.yml` bug first**, since it was blocking PR #5's checks regardless of the branch-strategy question. Root cause: unscoped `paths: ['stores/shopify/**']` plus a hardcoded `SLUG: lumibud-dev` default that doesn't correspond to any directory in this repo (`stores/shopify/` only has `hydrogen-alphaforbaby/` and `skills/`) — every push touching any store file tried to push a nonexistent theme and failed. Fixed (`b6f66eb`, PR #5's branch): `paths:` now excludes `hydrogen-*/`/`skills/`, and the hardcoded default is gone — a push-triggered run now diffs which classic-theme directory actually changed and only proceeds on an unambiguous single match. **Live-verified, not assumed**: pushed a follow-up commit touching only `hydrogen-alphaforbaby/**` (`aa4281c`) — before the fix this reliably triggered and failed the check in ~15s every time; after, no "Push Shopify Theme" run queued at all. `actionlint`: 0 findings.

**Step 2 — branch migration**. Corrected the original premise first: there's no `.github/workflows/oxygen-deploy-alphaforbaby.yml` file — the real Oxygen trigger is Shopify's own GitHub-App-injected workflow, bound to a branch via the Hydrogen storefront's Production environment setting in Admin, not a YAML `branches:` filter. `alphaforbaby/production` branch exists on GitHub pointing at `91309a6` — not created by this session directly; almost certainly auto-created by Shopify's GitHub App when Itzik saved the new binding in Admin (worth remembering as a general fact: saving a new branch name there may create it on GitHub, not just fail). **Verified the binding actually took effect, not assumed**: `npx shopify hydrogen env list` (worked non-interactively this time — didn't earlier this session from an isolated worktree, needs a real terminal session with cached CLI auth) confirmed live: `Production (handle: production, branch: alphaforbaby/production) → https://alphaforbaby.com` — the custom domain still correctly maps to Production, unaffected by the branch swap.

**Step 3 — retargeted PRs**: `gh pr edit 5 --base alphaforbaby/production` (clean, `MERGEABLE`, no diff bloat — both branches shared the same base commit). PR #6 confirmed already correctly on `main` (doesn't touch `stores/shopify/**` at all — org infra, not store code), no change needed.

**Step 4 — documented the convention** in `docs/DEV_WORKFLOW.md` (new section 2, existing sections renumbered 3-7) and `CONTRIBUTING.md`'s summary list, on PR #5's branch (`689f7d5`) since `DEV_WORKFLOW.md` itself doesn't exist yet on `main`/`alphaforbaby/production` — no point creating a separate branch to add a section to a file that isn't there yet. Documents: the real motivation is rollback isolation, not deploy-trigger collision (deploys are already directory-scoped per store, confirmed empirically — two stores on shared `main` wouldn't actually fight over *triggering*, but rolling a shared branch pointer back to undo one store's deploy would also revert any other store's unrelated commits sitting on it); the verified-safe migration order; and `main`'s ongoing role as the default/non-store-work branch, no longer alphaforbaby's production trigger.

**Both PRs still unmerged**, holding for Itzik's final review as instructed.

---

## 2026-08-30 — PR-merge notification pipeline (Telegram + follow-up ticket, no new authority)

**Ask**: the org should know immediately when a PR merges — Telegram notification + a ticket in the existing system — without giving any agent new merge/deploy authority. Built on its own branch (`pr-merge-notify`, off `main` — not store-specific, so no `<store-slug>/` prefix per `docs/DEV_WORKFLOW.md`), PR #6 (draft, not merged).

**Real constraint found, drove the design**: `data/traces.db` (the ticket system) has no public endpoint a GitHub-hosted Actions runner could reach — it only exists on whatever machine runs the heartbeat. Confirmed this isn't just "not configured yet": the `Deploy → GCP Cloud Run` workflow that would expose this backend publicly has **never once succeeded** (`gh run list` — every run fails at the WIF auth step in under 15s, missing `GCP_WIF_PROVIDER`/`GCP_SERVICE_ACCOUNT` secrets, which don't exist in this repo's secret store either). So a straightforward "CI calls `POST /org/tickets`" design would have silently failed 100% of the time — exactly the kind of looks-done-but-isn't-real deliverable `DEV_WORKFLOW.md` rule #6 exists to prevent.

**Design, split by what's actually reachable**:
1. `.github/workflows/pr-merged-notify.yml` — fires on `pull_request` closed+merged, posts to the org's existing shared Telegram channel (same bot/chat already used everywhere else, not a new one). PR-supplied values (title, branch) passed via `env:`, never spliced directly into the `run:` script — avoids the standard GH Actions shell-injection hole where a crafted PR title with `$(...)`/backticks would execute in the runner.
2. `src/org/heartbeat.py::_pr_merge_watch_tick` — pulls newly-merged PRs from GitHub (public repo, `gh pr list`, no token needed) every 5 minutes and opens a ticket per PR via the existing `open_ticket()` — same auto-assignment (Sol), same `dedupe_key` idempotency every other ticket source uses. No new authority: it only ever creates a normal ticket, picked up on a later heartbeat tick like any other.

**Also found while doing this**: `origin/main`'s `src/org/heartbeat.py` is significantly behind the local working copy — it's missing `_stock_watch_tick`, `_ticket_tick`, `_media_sweep_tick`, `_order_poll_tick`, `_nova_tick`, and the `sourcing_paused` enforcement fixes (all real, already-done work per earlier entries in this log), and still has the old competing `_poll_inboxes` that was supposed to be removed 2026-08-14. That work exists only as **uncommitted local changes** in the main working directory — never pushed. Did not touch or commit any of it (not this task's call to make), but flagging it: if that machine is lost before it's committed, all of that is gone, and `origin/main` is not an accurate picture of the real system right now.

**Verified, not just asserted** (task explicitly said: don't test by merging a real PR):
- `actionlint` (installed via `brew install actionlint`, includes embedded-script shellcheck) on the new workflow: **0 findings**. Ran it against the existing workflows too as a sanity check on the tool itself — it correctly flagged a real, pre-existing, unrelated quoting issue in `deploy.yml`, confirming it isn't just passing everything.
- `python3 -m py_compile` on the modified `heartbeat.py`: clean.
- A standalone dry-run script (mocked `subprocess.run` with fake `gh pr list` output, `TRACES_DB_PATH` pointed at a throwaway SQLite file, `save_company` no-op'd — no network, no real ticket-board writes) called `_pr_merge_watch_tick` directly four times and asserted: first run opens exactly one ticket per new PR; an immediate second run is blocked by the interval gate; forcing the gate open again doesn't re-ticket already-seen PRs (`dedupe_key`); a genuinely new PR opens exactly one new ticket and advances the cursor. All four passed.

**Two things blocked by this session's own permission classifier, not worked around**: sending a real test Telegram message (curl with the bot token), and adding `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` as repo secrets (`gh secret set`) — both flagged as external-service/credential actions needing explicit confirmation. **Until Itzik runs those two `gh secret set` commands himself (in PR #6's description), the workflow safely no-ops** (checks for the secrets, logs and exits 0 rather than failing) — it doesn't block anything by being unconfigured.

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
