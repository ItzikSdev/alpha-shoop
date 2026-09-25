<!-- Level 13 of store-builder-trending-cj · status lives in ../store-builder-trending-cj.md (traffic lights) -->
<!-- Covers original skill section(s): 11. Section numbers inside are kept so existing references ("7.D #31", "Section 5C") still resolve. -->

# 11. FINAL SELF-CHECK (run before shipping any store)

Go through this list literally, item by item. Fix and re-check (max 3
passes total per Section 3).

- [ ] If Mode B: the product was actually scored against Section 2.A.1-6, not just the first thing that cleared the gates
- [ ] If Mode B: every candidate's real category/title was checked against the target niche before scoring — CJ keyword search is known to surface off-topic results (2.A)
- [ ] A 2.C or 2.D hand-off was asked for/considered before defaulting to Mode B keyword search (Section 2 intro)
- [ ] Video came from a real 2.C/2.D source where possible; generation was only used if actually asked for or a real option was genuinely ruled out — not run automatically by default (7.B)
- [ ] If video generation was used: the owner's cost-approval gate for the video tool was actually gone through, not bypassed (7.B)
- [ ] The three known recurring bugs in Section 7.D were explicitly checked for, whichever fork/template this build started from
- [ ] If Mode B2 (ad-trends hand-off): the real ad video is the primary hero video (7.B priority 1), and `inferred_target_audience` is clearly labeled as inferred, not an exported CJ field (2.C)
- [ ] Mode B2/B3 was actually attempted autonomously first (checked for a stored session, tried obtaining a credential) before any human hand-off was requested (2.C/2.D) — a hand-off request names the specific missing credential/blocker, never a generic "no tooling" claim
- [ ] Real CJ images/video are used as primary assets where available; AI generation only fills genuine gaps (7.A, 7.B)
- [ ] If asked for a product with real/many reviews during Mode B keyword search: the output explicitly states the REST API has no review data (Section 2.A.3) instead of silently ignoring the ask; for a 2.C/2.D hand-off, the pid's own Buyer Review tab was actually checked/reported rather than assumed empty
- [ ] No video presence was inferred from a catalog "Video Gallery" badge — the specific pid's actual `productVideo` field was checked directly (2.A.2, 2.D)
- [ ] No reviews are claimed as "from CJ" or otherwise fabricated — only real app-imported reviews or an honest empty state (Rule 1, 7.C)
- [ ] Every Section 5 blueprint section is present and in the specified order
- [ ] Every benefit bullet follows the 6.C formula (micro-headline + outcome, not just feature)
- [ ] No fabricated named customer reviews with invented photos (Rule 1)
- [ ] No countdown timer without a real backing date/value (Rule 2)
- [ ] No unverifiable medical/health claims (Rule 3)
- [ ] Anchor price is 1.8-2.2x sell price, not arbitrarily inflated
- [ ] All copy is original — zero sentences reused from any reference store
- [ ] Variant names are descriptive/fun, not "Color 1/2/3"
- [ ] The accent color is bold/saturated and passes the 8.A.3 "pop test" — not a muted/pastel default
- [ ] The accent color repeats across CTA and badges (8.A.4), not confined to one button — **exception (v1.31): rating stars are gold/amber, not necessarily the accent color**, per the confirmed littlesnugg convention (Section 5 item 3) — **checked on a real screenshot of the live page (v1.38), not just confirmed as a prop/class in the code**, since this has been reported as still not matching more than once
- [ ] Product title actually renders BELOW the gallery/urgency-ticker/avatar-strip block on the real live page (v1.35) — **checked on a real screenshot (v1.38), not assumed correct because the spec says so**, since this has also been reported as still not matching after the spec was already updated
- [ ] Image prompts specify consistent lighting/background/color grade across the set, matched to any real CJ photos used
- [ ] At least one real or generated product video is used in the gallery (7.B Slot 2) — a Mode B build with no video at all there is a flagged gap, not silently skipped
- [ ] A hero background video is present (7.B Slot 1) — generated if no real option exists; if generation genuinely wasn't available, a static hero image was used AND the gap was stated, not silently skipped
- [ ] Mobile layout checklist (Section 9) fully passes at 375px, AND any screenshots sent to Itzik are captured at a phone viewport (~390×844, `is_mobile`/`has_touch` set) by default, not desktop — he asked for this explicitly (v1.16); send desktop only if he asks for it
- [ ] ~~Sticky bottom mini-cart bar is present~~ — **v1.33: REMOVED for alphaforbaby**, don't check for this, check instead that no leftover floating CTA remains (Section 5 item 18)
- [ ] Exactly one Add to Cart control exists on the page, tied to the currently-selected tier — no leftover floating/duplicate CTA (7.D bug #13, v1.33 — this now includes the removed sticky bar itself as one of the things to check isn't still lingering)
- [ ] Bundle tier cards behave as a true accordion — selecting a tier's radio expands only that tier's per-unit selects and collapses any other expanded tier (v1.33, Section 5 item 3) — verified by actually clicking between tiers, not by a static screenshot
- [ ] No standalone Color/Size selector exists outside the bundle tier cards — exactly one place to pick a variant, per unit, inside the selected tier (v1.33, Section 5 item 3)
- [ ] Each per-unit row inside an expanded tier shows a live preview image matching that unit's selected variant (v1.33, Section 5 item 3)
- [ ] Product title sits above the gallery for alphaforbaby specifically (v1.33 override — do not "correct" this back to match littlesnugg's own after-the-gallery order)
- [ ] The gallery/hero video has no `controls` attribute and cannot be paused or scrubbed by tapping it (7.B Slot 2, v1.33; Section 12 `test_gallery_video_autoplay_muted_loop`)
- [ ] A bundle/quantity tier block is present with the exact confirmed shape — named badges ("Most Popular" / "Best Deal!"), nested add-on checkboxes, and pricing math that actually matches checkout (Section 5, item 3)
- [ ] Review cards include a real customer photo and a "✓ Verified buyer" badge, not just star + quote + name (Section 5 item 14 as of v1.30, was item 8, 7.C) — at least several of the shown reviews (not zero, not all) carry a photo, since a real product's reviews are a genuine mix (v1.17)
- [ ] If the review count exceeds what fits in one initial grid, a "View all N reviews" (or equivalent) expansion is present rather than silently truncating the list with no way to see the rest (v1.17, `ReviewsSection.tsx`'s `showAll`/`INITIAL_VISIBLE` pattern)
- [ ] A request that needs infrastructure this template's frontend doesn't own (order/fulfillment tracking, transactional email, a backend, auth, payments) is surfaced to Itzik plainly rather than silently shipped as inert-looking frontend code that can't actually do the thing — AND Shopify's own native/first-party feature is checked and offered FIRST before recommending a paid third-party app (v1.17 correction): e.g. post-purchase review-request emails are natively free via the Shopify **Shop channel** (1-180 days after delivery, set in Shop settings) once the store is actually live on Shopify — a dedicated app (Loox/Judge.me) is worth suggesting only as an addition for photo-incentivized reviews specifically, not as the default first answer
- [ ] At least one SVG wave/curve section divider and at least one soft blob/gradient background shape are present (8.C) — the page doesn't sit on flat white for more than one section in a row
- [ ] Motion reads as varied, not one effect copy-pasted everywhere (8.C/v1.16) — at minimum a scroll-reveal on card grids (`ScrollReveal.tsx`), plus a second decorative-background pattern (`GradientBlobs` and/or `FloatingSparkles`) beyond the hero; every `GradientBlobs`/`FloatingSparkles` wrapper has `isolate` or it silently renders nothing (7.D bug #5)
- [ ] Gallery/slider arrows use `--color-accent`, not neutral black/gray (8.C)
- [ ] The 24/7 support widget (Nora) is present on every page; its support email is either the real address Itzik provided or a clearly-labeled placeholder — never a fabricated working-looking address (7.E)
- [ ] If Mode B/B2/B3: the sourced product was confirmed with Itzik per Section 2.E before Mode 1 started — the summary named the real cost, the actual price/margin you're setting, and demand/video/review status
- [ ] The price actually being charged targets real profit (≈3-4x landed cost / ~65-75% margin per 2.E), not just the 30% sourcing-gate minimum from 2.A.5
- [ ] Built from `react-store-template`'s existing components (Section 10) — no hand-rolled bundle/review/background-effect component that duplicates one already in `src/components/`
- [ ] If new/changed components were added to the template: `npx tsc -b --noEmit` was actually run and passed, and a real visual check (`npm run dev`, on the actual machine, not just a type-check) was done before calling it shipped
- [ ] Guarantee/shipping copy matches the real values in `store_brief.json`, not generic filler
- [ ] FAQ covers safety, sizing, shipping, and care at minimum
- [ ] Footer includes payment icons + all four policy links
- [ ] The single positioning angle from the brief is consistent end-to-end (not diluted by competing angles)
- [ ] No supplier/sourcing identity is visible anywhere: checked rendered `document.body.innerText` for the supplier's name, every `img`/`video` `src` domain, `<head>` meta, and JSON-LD (7.D bug #6)
- [ ] Any real review whose date predates the store's own launch has that exact date hidden, not fabricated into a different one (7.C, 7.D)
- [ ] No "Write a review" form renders unless it actually persists somewhere real (7.C, 7.D)
- [ ] Every review photo opens in a click-to-enlarge lightbox, closable via X / click-outside / Escape (7.C)
- [ ] Rendered page text contains no leftover markdown syntax (check the DOM's actual text, not the source) (7.D bug #7)
- [ ] Every mapped spec/detail field was checked against what it actually says on the real source page, not assumed from its field name (7.D bug #8)
- [ ] If this build adapted an existing template for a different product category, a pass was made to remove (not conditionally hide) UI elements that no longer apply (7.D bug #9)
- [ ] ~~The bundle block matches the store's actual `store_mode`~~ — **superseded by v1.29, do not apply this item**: every product now uses the same-SKU quantity-tier shape regardless of `store_mode` (see the next item); kept here struck through only so old reports referencing bug #10's original wording aren't misread as still-current
- [ ] The bundle block is a same-SKU quantity tier (Buy 1 / Buy 2 −10% / Buy 3 −35%, "BEST VALUE" on the top tier) regardless of `store_mode` (v1.29 — replaces the v1.24-v1.27 `store_mode`-branched design); real margin at each tier computed against real landed cost and flagged if below the 30% floor; nested add-ons (Priority Delivery, Shipping Protection, etc.) are real and functional, never decorative; the actual tier applied at quantity 2 and 3 confirmed with a real test cart, not just Admin discount config
- [ ] Gallery slide 1 is a single, clean, edited shot — not a raw supplier multi-inset composite (v1.29, 7.D bug #12); the header/chrome above the gallery is minimal enough that the hero image, not the header, dominates the first mobile viewport
- [ ] Every removable/toggleable control in the bundle is visually distinguishable, at rest, from any adjacent non-interactive marker (v1.28, 7.D bug #11) — check this by looking at a real screenshot, not by confirming the click handler/role works; a control that behaves correctly but looks identical to inert decoration fails this item even if every other test passes
- [ ] Every field defined in `store_brief.json`'s schema was checked for at least one real downstream usage, not just its declaration (7.D bug #10)
- [ ] Color/Size variant pickers are real native `<select>` elements — checked directly in the DOM, not just visually — not a styled `<div>`/button-group made to look like a dropdown (v1.30, Section 5 item 3)
- [ ] Reviews are displayed via the **AG Product Reviews** app (or whichever real, free, already-installed review app is on file), not the retired hand-rolled `ReviewsSection.tsx`/`MiniReviewCarousel.tsx` components — AND it was actually confirmed, not assumed, whether the app's review data is reachable from Hydrogen's Storefront API (a metafield or public API) or is Liquid-theme-only; if it's Liquid-only, that's a real headless-integration gap and must be reported as such, not silently worked around by re-adding the old custom components with the app's data hand-copied in once (7.C, v1.30)
- [ ] The 24/7 support widget uses the real inbox `support@alphaforbaby.com`, not a placeholder address (7.E, v1.30)
- [ ] Old, no-longer-sold catalog products (the prior clothing catalog, where applicable) are actually removed/unpublished from the store, not just absent from navigation while still live at their URLs (v1.30) — **confirmed plan (v1.42, Section 2.F)**: archive (not delete) every product ID NOT in the 9-product trending table, matched by product ID since titles are still actively changing on their own
- [ ] Each of the 8 remaining trending products (Section 2.F table) gets its own real reviews/video check before a full build pass — being on the confirmed table means "trending" is settled, not that reviews or video are automatically present (v1.42)
- [ ] Every product's real sourced videos/images (per its own hand-off data, e.g. the compiled real-video-URL list) are the ones actually used on its page — no placeholder/generic asset left in a slot a real one exists for (v1.30)
- [ ] The video-gallery section (Section 5 item 11) is honestly sized to the number of REAL video assets actually available for this product — never a duplicated or fabricated clip used to pad the count to match a reference store (v1.30, Rule 1)
- [ ] FAQ questions (Section 5 item 13) each carry a genuinely relevant emoji, not the same one repeated or omitted (v1.30)
- [ ] The final reviews grid (Section 5 item 14) uses full-size, non-compressed real photos and a clearly legible, high-contrast star row — checked on a real screenshot, not just confirmed present in the DOM (v1.30)
- [ ] The "purchase options" row under the primary CTA uses real data (real accepted payment methods) — not a decorative placeholder (v1.30)
- [ ] For alphaforbaby specifically: item 4 (mini review carousel) is ON, positioned AFTER the full buy-box block (primary CTA + purchase-options row + trust row), NOT between the price and the bundle block (v1.36 — v1.35 removed it from the price/bundle gap specifically, not from the page entirely); real reviewer photo, name, quote, and gold star row per card, with dot pagination; product title sits BELOW the gallery per item 3's littlesnugg-matched order, not above it (v1.33's above-gallery override is rescinded, v1.35)
- [ ] Header wordmark ("ALPHA FOR BABY") is centered in the header row, the hamburger icon sits flush against the LEFT edge with real computed spacing checked, not just relative position (7.D bug #15, precision-tightened v1.40) and the cart icon flush against the RIGHT edge (not next to the wordmark), the announcement ticker sits above the header row as its own strip, and no sign-in ICON appears in the header row itself (v1.36, re-confirmed v1.37 as littlesnugg's own real default)
- [ ] A "Sign In" button/menu item exists INSIDE the hamburger's slide-out drawer content (v1.40) — this is a normal nav item in the drawer, distinct from (and not a reversal of) the header-row sign-in icon that was removed
- [ ] No standalone price renders outside a bundle-tier card (7.D bug #17, v1.40) — every price on the page lives inside a Buy 1/2/3 card; spacing around that area re-checked after removal
- [ ] **PRODUCTION GATE**: the "Sign in / 10% off" popup (7.D bug #18) is gone or deliberately rebuilt, with a real root-cause explanation, not just silenced — checked on a real screenshot with the page freshly loaded (v1.41)
- [ ] **PRODUCTION GATE**: the final reviews grid (Section 5 item 14) shows large, photo-forward cards (real photo filling the top of each card), not small inline thumbnails — checked on a real screenshot (v1.41)
- [ ] Before any production deploy: confirm which branch is actually being merged/pushed to `alphaforbaby/production` (Shopify Oxygen's production environment tracks this branch specifically, not `main` or any preview branch) — verify in Shopify Admin's Hydrogen page that a NEW production deployment actually appears after pushing, don't assume a push succeeded (v1.41)
- [ ] The urgency ticker ("SELLING QUICK, LOW STOCK" style, or whatever real claim applies) AND the buyer-avatar strip with real photos actually render on the live page, below the gallery and above the title — 7.D bug #16, confirmed via direct screenshot (v1.39) that this section is entirely absent from the DOM, not a positioning issue; do not mark this done without a screenshot showing it rendering
- [x] Product title renders below the gallery/urgency/avatar block — confirmed fixed via direct screenshot, v1.39
- [x] Star rating renders in genuine gold with review count — confirmed fixed via direct screenshot, v1.39
- [ ] Gallery has no duplicate images — each slide is a distinct real shot (v1.36)
- [x] Homepage hero image slider (dot pagination) is fully removed, with the all-products grid taking its place directly after the hero buttons/stat — confirmed directly (Section 5B, v1.43)
- [ ] **STILL FAILING, checked directly (v1.46)**: homepage product grid must pull the real ACTIVE catalog live, not a hardcoded list — it currently shows the exact same fixed 3 products the old "Shop All" section had, and one uses a raw un-edited supplier photo (7.D bug #26, Section 5B, v1.43/v1.46)
- [x] Homepage trust-bar, "Shop by category," the old "Shop All" grid, and the 6-card testimonial grid are all fully removed from the homepage — confirmed directly (Section 5B, v1.43)
- [x] Homepage footer renders immediately after the product grid with nothing else in between — confirmed directly (Section 5B, v1.43)
- [ ] **STILL FAILING, checked directly (v1.46)**: homepage general spacing/density pass — reported done in v1.44, but the real page still reads generously spaced around the stat line and footer; re-verify with real computed padding values, not just "rules changed" (Section 5B, v1.44/v1.46)
- [ ] **STILL NOT STARTED, re-confirmed v1.47**: none of the 8 remaining trending products (Section 2.F) have actually been through a Section 3 build pass. v1.46 flagged this on Glow Whale Bath Buddy; the very next commit touched that exact product but only patched the two cosmetic symptoms named (markdown-fence text gone, two spec-field labels reworded) — gallery is still blank, still no bundle/buy-box, no urgency/avatar strip, no mini carousel, still zero reviews. Cosmetic patches on a broken default page are not a build pass — this needs the actual Section 3 pipeline run, not more spot-fixes to whatever gets named in a prompt.
- [ ] Homepage footer's combined top padding+margin is down to roughly 24-32px (currently ~68px, was ~132px before v1.46's fix) — measure with computed styles, don't eyeball a screenshot (Section 5B, v1.47)
- [x] **Foldable Portable Baby Crib** has real CJ reviews imported via AG Product Reviews (Section 7.C Method 2) — confirmed on the real page: "4.8 out of 5 · 23 reviews", real reviewer names/flags/quotes (v1.48, verified v1.49)
- [x] Carrier page shows real imported reviews — confirmed "4.8 out of 5 · 60 reviews · 60 with photos" on the real page (v1.49)
- [ ] **PRODUCTION GATE (v1.49)**: all 9 trending products return 200 at `/products/<handle>` — 6 currently 404 (`automatic-domino-train-set`, `montessori-shape-sorting-egg`, `toddler-sensory-learning-board`, `baby-beach-sun-shelter`, `foldable-baby-bed-canopy-set`, `cozy-portable-baby-nest`) and `/collections/all` returns only 3 (7.D bug #30). Verify by loading each of the six URLs, not by checking Admin status
- [ ] **PRODUCTION GATE (v1.49)**: every product page renders a working buy box — real price, real variant `<select>` per unit, and an "ADD [N] TO CART" button that actually adds to cart. Currently absent entirely on the crib and Glow Whale pages while the carrier has it (7.D bug #29); check the rendered DOM (`select` count > 0, a CTA element matching /add .* to cart/i, a `$` price), not the component source
- [ ] **Star rating renders as ONE clean row (v1.49)**: the fractional-fill overlay and the base row have identical star size and pitch — measure every star's x and width in both layers and confirm they match to the pixel (currently 20px/pitch-20 base vs 19.1px/pitch-19.1 overlay, drifting to a ~3.5px offset by star 5 — 7.D bug #27)
- [ ] **The webfont actually loads (v1.49)**: `document.fonts.size > 0` at runtime AND a rendered-width test of a test string in the intended family differs from the same string in `system-ui`; the CSP allows `fonts.googleapis.com` in `style-src` and `fonts.gstatic.com` in a real `font-src` (or the font is self-hosted via local `@font-face`), in BOTH preview and production; the family stack leads with the webfont, not with the local-only `FbTubicSans-*` names (7.D bug #28)
- [ ] **Section 5C parity gate** was reported row by row for every non-carrier product page, measured on the rendered page at 375px width (v1.49)
- [ ] **DEFINITION OF DONE per product (v1.50)**: that product's `custom.pdp_content` metafield is authored against the Section 5D.3 schema (all 11 keys considered, `quantityTiers: []` allowed only as a deliberate, stated choice per 5D.4 step 4), the metafield is actually written to Shopify (not just drafted in a file), and the page re-rendered afterwards to confirm each section appears
- [ ] **DEFINITION OF DONE for the suite (v1.50)**: `pytest tests/test_pdp_compliance.py -v --base-url <real dev URL>` was actually RUN and its real output pasted into the report — not summarised, not assumed. If it can't run (e.g. `playwright install chromium` was never done), say so explicitly instead of reporting the checklist as passing
- [ ] `PRODUCT_HANDLES` is derived from `/collections/all`, not a hand-typed list, and `TestCatalogCoverage` passes — i.e. all 9 trending products are served and no unexpected product is (v1.50, 7.D #26/#30)
- [ ] **PRODUCTION GATE (v1.51)**: every variant of every product reports `available: true` in Shopify's own `/products/<handle>.js` — six products currently report 0-of-N and render "sold out" with no Add to Cart (7.D #31). Check Shopify's JSON, not the rendered page, because the page is rendering the bad data correctly
- [ ] **PRODUCTION GATE (v1.51)**: each product carries ONE approved retail price across its variants, ending in `.90`, with the real landed cost (CJ item + real shipping) and resulting margin reported to Itzik for approval — the Domino Train Set currently sells at $4.90 against a ~$10.54 landed cost (7.D #32, Section 2.E)
- [ ] **No test in the suite `pytest.skip()`s on a missing required element (v1.52, 7.D #36)** — skip is only for "not applicable to this product"; the tier-bundle and cross-sell skips are converted to failures, and `conftest.py`'s retired `multi_product_niche` default and its contradicting docstring are removed
- [ ] Bundle tiers (`quantityTiers` + `tierBenefits`) authored per product, each `amountOff` matched to a real Shopify automatic discount and each tier total landing on `.90` — or `quantityTiers: []` stated as a deliberate choice with the reason (7.D #34, Section 5D.3)
- [ ] "Join [N] verified buyers" renders on every product page — it needs the AG app's own `air_reviews_product.data.reviewSummary` approved count (currently 0 on every product but the carrier, which is why the strip shows avatars with no headline) (Section 5C row 5)
- [ ] No product page serves an image from a supplier/AliCDN host, and every rendered review photo has `naturalWidth > 0` — currently 0 of 16 supplier-hosted photos load on the reference carrier page alone (7.D #35/#6)
- [ ] Review count per product never decreases between rounds without a stated reason — the crib went from 23 real reviews to "Be the first to review this product" (7.D #33)
- [ ] Every product has a real demo video, or the gap is stated per product — the six newest products currently render zero `<video>` elements (Section 7.B)
- [ ] Per-product content authored from that product's OWN real data — CJ listing specs, its own imported reviews, its own gallery order for every `imageIndex` — never another product's `pdp_content` with nouns swapped (Section 5D.3/5D.4, Rule 1)
- [ ] Homepage hero block is under ~400px tall at 375px width (currently 555px) and the footer block under ~420px (currently 760px) — the footer's own top gap is already at 32px combined and is DONE, don't re-cut it (Section 5B, v1.49)
- [ ] Gallery dot pagination is windowed/capped, not one dot per image — the crib page currently prints ~21 dots in a full-width band at 375px (Section 5C, v1.49)
- [ ] The other 6 unblocked trending products (Automatic Domino Train Set, Montessori Shape Sorting Egg, Toddler Sensory Learning Board, Baby Beach Sun Shelter, Foldable Baby Bed Canopy Set, Cozy Portable Baby Nest) each have their own real CJ source confirmed and reviews imported via Method 2 — this can happen ahead of each product's full Section 3 build pass, it doesn't need to wait (Section 2.F, v1.48)
- [x] Contact page's "Business details" text no longer says "registered in Israel" — confirmed directly on the real v1.44 deployment (`01m2a9acp...myshopify.dev`), rest of that section unchanged (v1.44)
- [x] Top announcement ticker: no spelled-out payment-brand-name item, back to a short rotation (confirmed 4 items: free shipping / 30-day returns / designed for little ones / secure checkout), speed genuinely slowed — confirmed directly (v1.44)
- [x] Product page: the sub-header trust row above the gallery is actually gone — confirmed directly on the real deployment, not just spec'd to be (7.D bug #19, v1.44 — this was already asked for in v1.31, took until this round to actually land)
- [ ] Urgency-banner slot shows the literal "SELLING QUICK, LOW STOCK" wording (or equivalent) — Itzik's explicit v1.45 decision, overriding the aggregate-honesty concern for this one line specifically (7.D bug #20, Section 5 item 3's v1.45 note) — not yet re-checked on a live deployment since the decision was made
- [x] Avatar-strip photos each show a real checkmark badge overlay — confirmed directly on the real deployment (7.D bug #21, v1.44)
- [x] Star rating glyphs are bigger and spacing down to "Buy more, save more" is visibly tighter — confirmed directly (v1.44)
- [x] Bundle shows only Buy 1 and Buy 2 — confirmed directly, no Buy 3 anywhere in the DOM (7.D bug #22, v1.44). **Note**: the old Buy-3 quantity discount (−$99.80 at qty≥3) is still configured in Shopify Discounts — harmless (an honest better deal for anyone who manually adds 3), but flag to Itzik whether to delete it too.
- [x] Mini review carousel cards (item 4) render with no border — confirmed directly (7.D bug #23, v1.44)
- [x] Product-demo video (item 10) renders immediately after the mini review carousel (item 4), before "Why parents choose it" — confirmed directly by scrolling the real page (7.D bug #24, v1.44)
- [x] The text-only trust block under Add to Cart is gone; the real payment-icon row above it stays — confirmed directly (7.D bug #25, v1.44)
- [~] General compactness pass — visibly tighter in the areas checked (star/bundle gap, mini-carousel-to-video transition); not independently measured everywhere (v1.44)
- [ ] **STILL OPEN, 4th round flagged (v1.35, v1.37, v1.41 gate, v1.44)**: the "Sign in / 10% off" popup (7.D bug #18) is still live on the real page, still covering the bundle area, still with no root-cause explanation given. This stays a hard production gate — do not merge to `alphaforbaby/production` with this still unexplained.

If everything passes: ship it. If something still fails after 3 passes:
ship anyway but list the exact failing items at the top of your output
so a human reviews just those before launch.

**Report format (v1.23, updated v1.25):** whenever you report a build or
a fix round as done: for every item Section 12's pytest suite covers,
run it and paste the real `pytest -v` output (not a paraphrase) — that
output IS the report for those items. For everything Section 12 doesn't
cover (visual/subjective calls: color pop, motion variety, section
order, copy quality), reproduce the relevant Section 11 items literally
with each marked done/failed/n-a and a one-line note on how it was
verified (a live screenshot, an element's computed properties, actually
reading the rendered page — not "read the code" or "should work"). A
prose summary claiming things are fixed, without either the pytest
output or the itemized list, is not an acceptable report — this exact
gap (reporting "done" without showing the evidence) is what forced
repeated correction rounds on the first real build.
- [ ] **REVIEW GATE (v2.1, Level 01 rule 7)**: every product that is live has ≥ 15 reviews with a real photo that is on Shopify's CDN and loads — read the "N reviews · M with photos" line on the rendered page. Every product under 15 is hidden (Draft / unpublished, never deleted) and appears nowhere: its URL 404s, and it's absent from the homepage grid, collections, search and sitemap (Level 02, 2.G)
- [ ] **PRODUCT IMAGES + HERO (v2.2, Level 01 rule 8)**: the gallery and hero use ONLY images from the product's own CJ listing — no review photo anywhere outside the reviews sections; every uploaded image passed markitdown + OCR stage 1 (short side ≥ 1000px, Laplacian ≥ 100, zero Chinese characters) and failing images were never uploaded; the hero is the best stage-1 image, preferring a person using the product; recorded in `store-profiles/alphaforbaby/hero-selection/<handle>.json` with `"source": "cj"` on every entry
- [ ] **VARIANT IMAGES (v2.6, Level 01 rule 9)**: every variant has its own CJ image that passed stage 1 and a vision check that it shows THAT variant (colour, pattern, contents); no two visually different variants share an image; variant and option names are human-readable; choosing a variant in Buy 1 or for any Buy 2 unit moves the main gallery to its image, and each Buy 2 unit row shows its own image (never a grey box); recorded in `store-profiles/alphaforbaby/variant-images/<handle>.json`
- [ ] **PRICE REALITY GATE (v3.1, Level 02 2.H)**: every live product's pricing record carries a `supply_check` block — cheapest compliant CJ shipping method with the alternatives considered, the regular Temu AND AliExpress consumer price for the same item with URLs and dates, and a verdict of `sell` / `no_ads` / `drop` that Itzik confirmed; nothing live is bought for more than the customer pays elsewhere, and nothing under $12 profit per order carries ad budget
- [ ] **MENU MATCHES THE CATALOG (v3.2, Level 05 5B.1)**: every nav item resolves to a collection with at least one published product, no category nav while fewer than ~6 products are live, no "Sign in" item, and every product with an approved pricing record is actually live (a missing one is restored from the repo records, not written off)
- [ ] **SECTION DEPTH + BROWSABLE REVIEW PHOTOS (v3.3, Level 04 5.E / Level 09 7.C.1)**: every section wrapper carries `data-pdp-section`, every live product has a real demo video, each section meets its minimum length measured against the carrier page (character counts stated in the report, not "all sections present"), and the review photos scroll-snap and swipe on mobile with 44px arrows on desktop
- [ ] **OWNER AUDIT (v2.6, Level 15)** run before any paid ads, report saved, zero 🔴
- [ ] **PRICING (v2.3)**: every live product has `store-profiles/alphaforbaby/pricing/<handle>.json` with real CJ item + shipping cost per variant, ≥ 3 market comparables with links and dates, a price at or below the market median, ≥ 20% margin on Buy 1 AND Buy 2 after the 2.9% + $0.30 payment fee, "Cost per item" filled in Shopify, and `approved_by_itzik: true` (Level 03, pricing rule)

## The push gate (v2.5, Itzik's instruction)

**A green suite is a precondition for pushing to production, not a
report you file afterwards.** Itzik, after the carrier shipped without
its bundle: *"make sure it not happens again — you have rule in skill,
use the skill and make all passed before you push to prd."*

Before `git push` to `alphaforbaby/production`, in this order:

1. Restart the dev server so it is serving current Shopify data — a
   metafield or price write does not reach a running dev server (7.D's
   caching note, and Level 07's "writing the metafield is not shipping
   it").
2. Run the full suite at `-n 4` against it.
3. **Zero failures.** Not "two expected failures" — if a check is red
   because of a real decision, encode the decision (a recorded override,
   `PAUSED_HANDLES`) so the check passes *and* keeps announcing itself;
   if it is red because something is broken, fix the thing. A red run is
   never a thing to explain in the hand-off message and push anyway.
4. Read the skip list (`-rs`). Every skip must name a recorded reason.
5. Only then commit and push.

The failure this rule comes from is instructive: the suite was red on two
`test_not_above_market_median` checks, the redness was explained at
length in the hand-off as "expected", and the genuinely broken thing —
a required bundle deleted from a live product — sat in the same push
unnoticed, because a run that is already red hides the next red thing.
Green runs are what make new failures visible.

