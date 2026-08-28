# Vision & Assets Reference

> **STATUS: DEFERRED.** Everything in this document past the "Current Phase"
> section is explicitly **out of scope** until alphaforbaby.com has its first
> real sale. It exists so the vision and the asset inventory are written down
> somewhere durable — not as active direction. See Nova's charter
> (`src/org/seed.py`) and `docs/DECISIONS_LOG.md` for what's actually being
> worked on right now.

---

## Company

**Alpha** — an autonomous e-commerce company: a small org of AI agents
(currently 7: Ava, Sol, Reel, Nora, Milo, Kai, Nova — see
`src/org/seed.py`) that builds and runs real Shopify stores, managed by
Itzik. Owner is an Israeli **עוסק פטור** (VAT-exempt sole proprietor).

**Live product:** [alphaforbaby.com](https://alphaforbaby.com) — a baby
clothes storefront (Shopify + Hydrogen headless frontend), CJ Dropshipping
fulfillment, targeting the US/global market.

## Current Phase (the only thing in scope right now)

Single store. Zero sales to date. Checkout is blocked on MAX opening a
USD/multi-currency merchant account (root cause + status:
`docs/DECISIONS_LOG.md`, 2026-08-17 §1). The entire org's job right now is
getting to **sale #1** — nothing below this line until that happens.

---

## Long-Term Vision (deferred — gated on sale #1)

Not a roadmap to execute now — a record of the direction, so it isn't lost
and doesn't need re-deriving later:

- Prove the alphaforbaby.com funnel end-to-end (traffic → checkout → repeat
  order) before touching anything else.
- Once proven, consider replicating the same playbook (agents + Shopify +
  CJ) into additional niches/stores — not before.
- Longer-term, possible expansion to additional marketplaces (AliExpress,
  Amazon, eBay) and a second consumer app (see Assets below) — explicitly
  **not** to be pursued, discussed as active work, or greenlit by any agent
  until sale #1 is real. Nova's charter exists specifically to catch
  and redirect drift toward this list while it's premature.

---

## Asset & Infrastructure Inventory

Reference list of what's already provisioned, so nothing gets rebuilt or
forgotten. Exact account credentials/numbers live with the owner (not
duplicated here); this tracks *what exists and what it's for*.

| Asset | Purpose | Status |
|---|---|---|
| **Accountant** | Israeli bookkeeping/tax for the עוסק פטור business | Engaged (owner relationship, not tracked in this repo) |
| **Hyp (payment gateway)** | Card processing on alphaforbaby.com, clears through MAX | Live but blocked — see Current Phase above |
| **MAX (acquirer)** | Settles Hyp transactions | ILS-only account; USD/multi-currency account opening, ETA ~2026-08-18/19 |
| **Shopify (alphaforbaby.com domain)** | Storefront + Admin, primary sales channel | Live |
| **Second app's domain + Apple/Google developer accounts** | Reserved for a future consumer app (out of scope, see Vision above) | Provisioned, dormant — owner-held, not tracked in this repo |
| **GCP (`GCP_PROJECT_ID`/`GCP_REGION`)** | Google Ads reporting integration, general cloud infra hooks | Configured (`.env`) |
| **Cloudflare + Resend** | Cloudflare Email Routing forwards each store's `support@<domain>` into the shared central inbox; Resend sends outbound support replies (`RESEND_API_KEY`) | Live |
| **7-agent org system** | Ava (CEO), Sol (sourcing/copy/Shopify push), Reel (video), Nora (support), Milo (fulfillment), Kai (TikTok ads reporting), Nova (stay-on-target) — `src/org/seed.py` | Live |
| **MakeUGC videos** | External UGC-style video asset source (owner relationship, not integrated into the agent pipeline) | Available, not wired into `src/video/` |
| **TikTok page (organic)** | Social presence / organic content channel | Live (separate from the TikTok **Ads** integration Kai reports on, `src/tiktok_mcp/`) |
| **PayPal** | Business account (distinct from the Hyp/MAX store payment gateway) | Provisioned — owner-held |
| **This React admin app (`platform-app/`)** | Internal dashboard: live roster, runs, finance, tickets, agent activity | Live, dev server at `:5173`/`:3000` per `vite.config.ts` |
| **Local RAG (Redis)** | Two corpora: Sol's seen-CJ-candidates memory (`search_local_catalog`) and his playbook docs (`search_playbook`) | Live |
| **Telegram** | The org's only chat interface — per-agent bots where configured, shared channel otherwise (`src/org/telegram.py`) | Live |

---

*This file is a reference, not a task list. Updates to the vision section
should stay theoretical until the STATUS banner above is removed — which only
happens after sale #1 and an explicit decision to resume expansion work.*
