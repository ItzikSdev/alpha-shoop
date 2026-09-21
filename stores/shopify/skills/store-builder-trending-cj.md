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
| 01 | [01-role-and-rules.md](store-builder-trending-cj/01-role-and-rules.md) | ROLE, 1 | 🟢 Done | All 8 rules in force and now actually applied. Read to the END — rules 7 and 8 sit past the six older ones. |
| 02 | [02-product-sourcing.md](store-builder-trending-cj/02-product-sourcing.md) | 2 | 🟢 Done | Review gate applied: 3 products live, 6 unpublished from all 4 channels and returning 404, nothing deleted. Counts confirmed at CJ's ceiling — alternative CJ listings checked for the canopy and nest, none better. |
| 03 | [03-build-pipeline-and-brief.md](store-builder-trending-cj/03-build-pipeline-and-brief.md) | 3, 4 | 🟢 Done | |
| 04 | [04-product-page-blueprint.md](store-builder-trending-cj/04-product-page-blueprint.md) | 5 | 🟢 Done | v1.53 shipped: Ratings & Reviews sits directly under the video, verified by byte offset in the served HTML. |
| 05 | [05-homepage-blueprint.md](store-builder-trending-cj/05-homepage-blueprint.md) | 5B | 🟢 Done | Pixel budgets pass at 375px; grid is live-derived and now shows the 3 gate-passing products. |
| 06 | [06-pdp-parity-gate.md](store-builder-trending-cj/06-pdp-parity-gate.md) | 5C | 🟢 Done | All 3 live pages render every component the carrier renders. |
| 07 | [07-per-product-content-contract.md](store-builder-trending-cj/07-per-product-content-contract.md) | 5D | 🟢 Done | Every `pdp_content` key renders on all live products, tier bundle included, each backed by a real Shopify automatic discount. |
| 08 | [08-copywriting.md](store-builder-trending-cj/08-copywriting.md) | 6 | 🟢 Done | |
| 09 | [09-assets-video-reviews-trust.md](store-builder-trending-cj/09-assets-video-reviews-trust.md) | 7.A–7.C, 7.E | 🟢 Done | Photos 297/297 on Shopify CDN; video on every product; **hero-image procedure run for all 3 live products** and recorded. 7.A.1's bytes/pixel threshold and its single-pass OCR were both corrected from the first real run. |
| 10 | [10-known-bugs.md](store-builder-trending-cj/10-known-bugs.md) | 7.D | 🟢 Done | #31–#36 fixed and verified; #37–#40 found and fixed. Read #38 before trusting any parallel test run. |
| 11 | [11-design-system-and-responsive.md](store-builder-trending-cj/11-design-system-and-responsive.md) | 8, 9 | 🟢 Done | #28 resolved: 3 webfont faces load, Assistant ≠ system-ui. No horizontal scroll at 375px. |
| 12 | [12-technical-implementation.md](store-builder-trending-cj/12-technical-implementation.md) | 10 | 🟢 Done | |
| 13 | [13-final-self-check.md](store-builder-trending-cj/13-final-self-check.md) | 11 | 🟡 In progress | Everything is verified on the **dev build** (`localhost:3001`). Shopify-side changes (gate, prices, heroes) are live now; the code changes are not deployed to Oxygen. |
| 14 | [14-automated-tests.md](store-builder-trending-cj/14-automated-tests.md) | 12 | 🟢 Done | **148 passed, 3 skipped, 0 failed in 1:17** at `-n 4` (12 classes / 151 tests). Run it the way Level 14 documents — `-n 4`, `PDP_HANDLES` pinned. |

## Top blockers right now, in order

1. **Deploy to Oxygen.** The reviews-under-video move, the supplier-blob
   strip and the honest buyer count are verified on the dev build only;
   production still renders the old page order. Everything done in
   Shopify (the gate, the prices, the heroes) is already live.
2. **Decide what a 3-product store should do next** — the gate leaves
   the carrier, the sorting egg and the Domino. Either source new
   products that can clear 15 photo reviews at import time (Level 02,
   2.G says to check the count BEFORE building), or find a second real
   review source for the canopy set (13) and the nest (11), which are
   the two closest and whose pages are already fully built.
3. **Glow Whale's 16%-defect decision** is still open and independent of
   the gate — it now has 27 photo reviews available on CJ, so it would
   pass rule 7 if the defect question is ever resolved.

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
