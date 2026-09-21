---
name: store-builder-skill
version: 2.4
description: >
  Build and verify complete, high-converting product pages for the
  alphaforbaby Shopify Hydrogen store from trending CJ Dropshipping
  products — sourcing, per-product content, page layout, reviews, pricing,
  and a pytest compliance gate. Start here, then open the level files.
audience: >
  Sol (alpha-shoop's autonomous store-building agent). Runnable on local
  qwen3-14B for routine builds, or on Opus when a launch needs higher
  creative and visual quality. The rigid templates exist to keep a small
  model on-track — a stronger model spends its extra headroom on bolder
  execution WITHIN this spec, never on loosening Level 1.
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

## How to use the levels

1. **Always read Level 01 first** (role and non-negotiable honesty
   rules). Nothing in any other level overrides it.
2. **For a new product, work the levels in order**, 02 → 14. For a fix,
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
| 00 | [00-changelog.md](store-builder-trending-cj/00-changelog.md) | changelog | ⚪ | History v1.1 → v2.3. |
| 01 | [01-role-and-rules.md](store-builder-trending-cj/01-role-and-rules.md) | ROLE, 1 | 🟢 Done | Rules in force across the whole store. New in v2.1: rule 7 (15 photo reviews or hidden) and rule 8 (product images only from CJ, checked before upload; v2.2). |
| 02 | [02-product-sourcing.md](store-builder-trending-cj/02-product-sourcing.md) | 2 | 🟡 In progress | Reviews imported on 8, crib's 23 restored. New review gate (2.G): only 3 of 9 pass (carrier, sorting egg, domino) — the other 6 must be hidden. |
| 03 | [03-build-pipeline-and-brief.md](store-builder-trending-cj/03-build-pipeline-and-brief.md) | 3, 4 | 🟡 In progress | v2.3 pricing rule applied to all 3 live products (landed cost, market check, `approved_by_itzik: true`). Domino ($24.90) is within its median; carrier ($42.90) and egg ($26.90) are above their medians by Itzik's explicit override — `TestPricingRule::test_not_above_market_median` correctly fails red on both as the recorded signal of that override, not a bug. |
| 04 | [04-product-page-blueprint.md](store-builder-trending-cj/04-product-page-blueprint.md) | 5 | 🟡 In progress | Built on the carrier page. Open: move Ratings & Reviews under the video (v1.53). |
| 05 | [05-homepage-blueprint.md](store-builder-trending-cj/05-homepage-blueprint.md) | 5B | 🟡 In progress | Grid + footer gap done. Open: hero 555px and footer 760px at 375px width. |
| 06 | [06-pdp-parity-gate.md](store-builder-trending-cj/06-pdp-parity-gate.md) | 5C | 🟡 In progress | 1 of 9 product pages matches the carrier (the carrier itself). |
| 07 | [07-per-product-content-contract.md](store-builder-trending-cj/07-per-product-content-contract.md) | 5D | 🟡 In progress | Content written for 7 products. Open: tier bundle on 8 products, "How to use" on 8. |
| 08 | [08-copywriting.md](store-builder-trending-cj/08-copywriting.md) | 6 | 🟢 Done | |
| 09 | [09-assets-video-reviews-trust.md](store-builder-trending-cj/09-assets-video-reviews-trust.md) | 7.A–7.C, 7.E | 🟡 In progress | Review photos now re-hosted on Shopify's CDN. Open: all 3 live heroes are review photos — must be redone from CJ images only (7.A.1, v2.2); no video on 6 products. |
| 10 | [10-known-bugs.md](store-builder-trending-cj/10-known-bugs.md) | 7.D | 🔴 Not done | Open: #31 unbuyable variants, #32 pricing below cost, #34 bundle, #36 skipped tests. #33 and #35 now fixed (crib reviews back, photos re-hosted). |
| 11 | [11-design-system-and-responsive.md](store-builder-trending-cj/11-design-system-and-responsive.md) | 8, 9 | 🟡 In progress | Open: the webfont is blocked by CSP (#28). |
| 12 | [12-technical-implementation.md](store-builder-trending-cj/12-technical-implementation.md) | 10 | 🟢 Done | |
| 13 | [13-final-self-check.md](store-builder-trending-cj/13-final-self-check.md) | 11 | 🟡 In progress | Checklist written; production gates still open. |
| 14 | [14-automated-tests.md](store-builder-trending-cj/14-automated-tests.md) | 12 | 🔴 Not done | 71 tests written, not yet running in the repo; `conftest.py` still stale. |

## Top blockers right now, in order

1. **Root-cause the auto-republish gap (Level 02, v2.4).** Something in
   the org's automation — most likely the CJ stock sweep — republished 3
   gated products the same day they were hidden, with no awareness of
   the review gate. Re-hidden, not yet fixed at the source; the live
   catalog can't be trusted stable until it is.
2. **Two live products are priced above their market median by explicit
   owner override (Level 03, v2.4).** Carrier $42.90 vs $29.99 median;
   egg $26.90 vs $15.49 median. This is a real, recorded decision, not
   a gap — `TestPricingRule::test_not_above_market_median` is meant to
   stay red on these two.
3. **Hero images blocked on 2 of 3 live products (Level 09, 7.A.1 v2.2).**
   No CJ image on the carrier or the domino clears both hard checks —
   `hero-selection/<handle>.json` records `status:
   blocked_no_compliant_image` for both. The egg has a compliant hero.
4. **Deploy the code changes.** The pricing/hero/gate DATA changes are
   already live in Shopify (prices, discounts, publications — those
   apply instantly). The CODE changes this round — `TestPricingRule`,
   the `TestHeroImage` null-hero fix, `NO_BUNDLE_HANDLES` in
   `conftest.py` — still need committing and pushing to
   `alphaforbaby/production`.

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
