---
name: store-builder-skill
version: 3.13
description: >
  Build and verify complete, high-converting product pages for the
  alphaforbaby Shopify Hydrogen store from trending CJ Dropshipping
  products — sourcing, per-product content, page layout, reviews, pricing,
  and a pytest compliance gate. Start here, then open the level files.
audience: >
  Claude (Cowork), working directly for Itzik since 2026-09-25 — Sol and
  the other org agents are no longer part of this store's workflow. Any
  capable LLM picking this up starts at "Start here" below, then Level 17.
derived_from: >
  Structural pattern analysis of 5 live reference dropshipping stores
  (funvibeshub.com, minixmasbaby.myshopify.com, octocuddles.store,
  starnestshop.com, beelyra.com) plus littlesnugg.store — patterns and
  mechanics only, never their text, images or brand names.
---

# Store Builder — Trending CJ

This skill turns a trending CJ Dropshipping product into a complete,
honest, fully responsive product page on alphaforbaby.com, and proves it
with measurements instead of reports. The reference for "done" is the
built Ergonomic Baby Hip Carrier page: every product page must match it
component for component.

The spec lives in the `store-builder-trending-cj/` folder, split into
levels. **This file is the entry point and the status board.** It tells
you what each level covers, what state it's in right now, and in what
order to read them.

## Start here — where the project stands (2026-09-25)

Read this, then Level 17 (decisions and measured facts). It is enough to
resume without the chat history.

- **Goal (Itzik's words, 2026-09-25):** a store that sells through paid
  ads with more than **$12 profit on every sale**. Baby products, not
  clothing. He runs it as an exempt dealer (עוסק פטור) to make money; so
  far there has not been a single sale.
- **Live on alphaforbaby.com:** 2 products — Ergonomic Baby Hip Carrier
  ($43.90) and Montessori Shape Sorting Egg ($26.90). The domino is
  unpublished. Six others are hidden by the review gate.
- **Hard numbers that shape everything** (Level 17): CJ's cheapest US
  shipping is ~$7.60 for a ~220 g parcel and $19.52 for the 750 g carrier;
  CJ has almost no reviews; Walmart sells generic versions of our kind of
  products for $10-20; AliExpress is no cheaper than CJ for our items.
  Temu is not usable as a supplier.
- **Profit per order (updated 2026-09-28, later same day — price
  change, full detail in Level 17):** egg price lowered $26.90 ->
  **$23.90** after a real competitor-pricing check (was priced above
  several market alternatives); landed cost $11.10 -> profit
  **$12.80/order** (still clears the $12 floor, no longer clears the
  $15 target — re-evaluate the running ad test with this number).
  Carrier stays at $43.90; landed cost $31.88 -> profit
  **~$12.02/order, right at the $12 floor, zero room to cut price** —
  needs a cheaper supplier, not a discount.
- **The plan Itzik approved:** capped ad tests (Level 16) on 2-3 products
  whose profit per order is >= $12 — after the pre-flight in Level 16 §1
  passes. Candidate new product: electric baby nail file set (CJ pid
  BC4566AA-DB0F-4C3A-B118-015B1858791D, ~234 g, item $2.88-3.76, landed
  ~$10.5-11.7, test price $24.90 → ~$12 profit; Walmart anchors $9.88-
  34.99).
- **Waiting on Itzik:** Meta pixel id; Facebook & Instagram channel data
  sharing set to Maximum; one real test order (then refund); approval of
  any new price; ordering samples. Budget: $5 to start (Level 16 §6).
- **How Claude reaches things:** repo at `~/Documents/git/alpha-shoop`
  (connected folder). CJ API through the repo's own settings
  (`src/config.get_settings()`, run from the repo root so `.env` loads) —
  never print or copy the key. Live checks: `https://kgg8n0-k0.myshopify.com/products/<handle>.js`
  (Shopify's own data) and the rendered page on alphaforbaby.com. A change
  isn't live until it's committed, pushed to `alphaforbaby/production` and
  Oxygen shows a new deployment.

## How to use the levels

1. **Always read Level 01 first** (role and non-negotiable honesty
   rules). Nothing in any other level overrides it.
2. **For a new product, work the levels in order**, 02 → 14, then
   Level 15 and Level 16 §1 before any paid ads. For a fix,
   read the level that owns it **plus** Level 10 (known bugs), and still
   finish with Levels 13 and 14.
3. **Read a whole level, not a grep of it.** Most repeated misses in this
   project came from fixing the named symptom without reading the spec
   around it.
4. **Nothing is done until Level 14's suite has actually run** and its
   real `pytest -v` output is pasted in the report — failures included.
5. **Section numbers still work.** Levels keep the original section
   headings, so a reference like "7.D #31" or "Section 5C" resolves
   through the map in the table below.

## Traffic lights — what's developed and finished, and what isn't

🟢 **Done** — developed, finished, verified on the live store · 🟡 **In
progress** — partly developed, still open work · 🔴 **Not done** — not
developed yet, or broken · ⚪ reference only (nothing to develop)

| Level | File | Old section | Status | Where it stands |
|---|---|---|---|---|
| 00 | [00-changelog.md](store-builder-trending-cj/00-changelog.md) | changelog | ⚪ | History v1.1 -> v3.1. |
| 01 | [01-role-and-rules.md](store-builder-trending-cj/01-role-and-rules.md) | ROLE, 1 | 🟢 Done | Rules in force across the whole store: rule 7 (15 photo reviews or hidden), 8 (CJ-only images), 9 (picture matches the choice), 10 (honest social proof, v3.8). |
| 02 | [02-product-sourcing.md](store-builder-trending-cj/02-product-sourcing.md) | 2 | 🟡 In progress | Reviews imported on 8, crib's 23 restored. New review gate (2.G): only 3 of 9 pass (carrier, sorting egg, domino) — the other 6 must be hidden. v3.1 adds the 2.H price reality gate - not yet run on any product. v3.6 adds 2.I, the winning-product filter: eight hard gates before anything is built. v3.7 adds 2.J: a full CJ scan found no product that passes 2.I; model decision pending. |
| 03 | [03-build-pipeline-and-brief.md](store-builder-trending-cj/03-build-pipeline-and-brief.md) | 3, 4 | 🟢 Done | v2.3 pricing applied to all 3 live products: domino $24.90, egg $26.90, carrier $43.90 — each with a compliant Buy 2 and `approved_by_itzik: true`. Above-median prices on carrier and egg carry a recorded `market_override` that the suite re-warns on every run. v2.5 added step 3b: the unit price must admit a valid Buy-2 total. |
| 04 | [04-product-page-blueprint.md](store-builder-trending-cj/04-product-page-blueprint.md) | 5 | 🟡 In progress | 5.E applied: every section carries `data-pdp-section` and TestSectionDepth measures the characters inside. Open: the domino has no demo video and CJ has none. |
| 05 | [05-homepage-blueprint.md](store-builder-trending-cj/05-homepage-blueprint.md) | 5B | 🟢 Done | Pixel budgets pass at 375px. 5B.1 applied: nav is Home / Shop All / Contact, no empty categories, no Sign In in the menu or header; footer Shop column follows the same `nav`; the homepage category tiles were dead config. |
| 06 | [06-pdp-parity-gate.md](store-builder-trending-cj/06-pdp-parity-gate.md) | 5C | 🟡 In progress | 1 of 9 product pages matches the carrier (the carrier itself). |
| 07 | [07-per-product-content-contract.md](store-builder-trending-cj/07-per-product-content-contract.md) | 5D | 🟡 In progress | Content written for 7 products. Open: tier bundle on 8 products, "How to use" on 8. |
| 08 | [08-copywriting.md](store-builder-trending-cj/08-copywriting.md) | 6 | 🟢 Done | |
| 09 | [09-assets-video-reviews-trust.md](store-builder-trending-cj/09-assets-video-reviews-trust.md) | 7.A–7.C, 7.E | 🟡 In progress | 7.C.1 done: review photos swipe, snap, have 44px arrows and a tap-to-enlarge view with the reviewer beside it. Open: hero resolution, and the domino video. |
| 10 | [10-known-bugs.md](store-builder-trending-cj/10-known-bugs.md) | 7.D | 🔴 Not done | Open: #58 fulfilment path unverified (test order needed). Fixed in v3.8 code, pending deploy: #59-#62. |
| 11 | [11-design-system-and-responsive.md](store-builder-trending-cj/11-design-system-and-responsive.md) | 8, 9 | 🟡 In progress | Open: the webfont is blocked by CSP (#28). |
| 12 | [12-technical-implementation.md](store-builder-trending-cj/12-technical-implementation.md) | 10 | 🟢 Done | |
| 13 | [13-final-self-check.md](store-builder-trending-cj/13-final-self-check.md) | 11 | 🟡 In progress | Checklist written; production gates still open. |
| 14 | [14-automated-tests.md](store-builder-trending-cj/14-automated-tests.md) | 12 | 🔴 Not done | 71 tests written, not yet running in the repo; `conftest.py` still stale. v2.6 adds TestVariantImages (4 tests). v3.1 adds TestSupplyPriceGate (3 tests). v3.2 adds TestNavMatchesCatalog (4 tests). v3.3 adds TestSectionDepth and TestReviewPhotosAreBrowsable (5 tests). v3.6 adds TestWinningProductFilter (2 tests). |
| 15 | [15-owner-audit-before-ads.md](store-builder-trending-cj/15-owner-audit-before-ads.md) | new | 🔴 Not done | Written in v2.6, never run. Run after Level 14 passes, before any ad spend. |
| 16 | [16-ad-test-playbook.md](store-builder-trending-cj/16-ad-test-playbook.md) | new | 🔴 Not done | Written v3.8. Pre-flight (§1) not yet passed: pixel id, test order, deploy of v3.8 fixes. |
| 17 | [17-decisions-log.md](store-builder-trending-cj/17-decisions-log.md) | new | ⚪ | Itzik's decisions and the measured facts. Read second, after "Start here". |

## Top blockers right now, in order

1. ~~Deploy the v3.8 fixes~~ — live since 2026-09-25 (Level 17). The code
   is deployed but still uncommitted in `stores/shopify/hydrogen-alphaforbaby`.
2. **Prove an order reaches CJ** — one real test order by Itzik, refunded
   after (Level 16 §1.1-1.2, 7.D #58).
3. ~~Turn the pixel on~~ — `metaPixelId` 2246132889517820, live. Still to
   confirm: data sharing Maximum in Shopify's Facebook & Instagram channel
   (Purchase from checkout) (7.D #61).
4. **Build the test product(s)** with profit >= $12 at the test price —
   first candidate: electric baby nail file set (see "Start here").
   Note (2026-09-28): the egg, already live and already running an ad
   test, now clears $12 on its own real numbers ($15.80/order) without
   needing a new product — worth Itzik weighing before spending more
   effort sourcing/building the nail file set.
5. **Run the first $5** per Level 16 §6 (Traffic, $1/day × 5 days, one
   product, one video) — after the free steps — and log it in Level 17.

Closed or superseded (kept in the changelog, not here): the picture/variant
work (v2.6), domino restore and menu (v3.2), section depth and review swipe
(v3.3), the business-model question (answered by Level 16/17).

## Maintaining this skill

- Change the level file that owns the rule — never add rules to this
  file.
- In the same edit: add an entry at the bottom of `00-changelog.md`,
  bump `version` above, and update the traffic light for that level.
- A level turns 🟢 **Done** only when everything in it is developed,
  verified on the rendered store, **and** its Level 14 tests pass. A
  "done" report is not verification. If a finished level breaks again,
  it goes back to 🔴 — lights move both ways.
- Every new bug in Level 10 gets a matching test in Level 14 the same
  day.
