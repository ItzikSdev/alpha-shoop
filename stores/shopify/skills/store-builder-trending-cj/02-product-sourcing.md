<!-- Level 2 of store-builder-trending-cj · status lives in ../store-builder-trending-cj.md (traffic lights) -->
<!-- Covers original skill section(s): 2. Section numbers inside are kept so existing references ("7.D #31", "Section 5C") still resolve. -->

# 2. PRODUCT SOURCING — CJ DROPSHIPPING (no product given yet)

Skip this section if you were already handed a specific product (Mode A).
Otherwise, this runs first — it decides WHAT you're building a store
for, and its outputs feed directly into the `store_brief.json` in
Section 4.

**Ask for a Mode B2 (2.C) or Mode B3 (2.D) hand-off before defaulting to
Mode B keyword search.** These aren't equally good options — a 2-3
minute human browse of CJ's Ad-Trends dashboard or Top Selling catalog
reliably beats autonomous keyword search on every axis that matters:
real trend signal (thousands-to-tens-of-thousands `Lists` counts vs. a
~30-40 ceiling), on-topic relevance (no keyword-pollution risk), and
video availability (a large fraction of these listings actually have
one, vs. essentially none surfaced by keyword search — see 2.A.2). Only
fall back to Mode B keyword search below when no one is available to do
that hand-off.

You already have a CJ Dropshipping MCP and the tools/gates documented in
`skills/product-sourcing.md` (`cj_search_products`,
`search_trending_products`, the CJ product-detail fields, and the
existing 3-image / margin / price gates). Reuse that plumbing — this
section only adds the selection criteria for THIS kind of build: one
standout hero product for a brand-new single-product store, not a
catalog fill.

### 2.A — Selection criteria, in priority order

1. **Trending today.** Prefer the highest `trend_score` (CJ
   `listingCount` — more stores already selling it = validated current
   demand) among your candidates. This is a single-hero-product store:
   pick the ONE best trending item, not a safe average one.
2. **Within Mode B keyword search specifically, do NOT rank or break ties
   on `productVideo` — assume it will be empty.** Confirmed empirically
   across two separate builds and 294 keyword-search candidates spanning
   unrelated categories (pet grooming, watches, humidifiers, drones,
   massage guns, electric toothbrushes, vacuums, hair dryers, blenders,
   cameras, speakers), checked two independent ways (the raw REST payload
   and the CJ MCP's own `get_product_detail` call): `productVideo` was
   `null` on every single one, 294/294. This is specific to what
   `search_trending_products` surfaces (it calls `product/list` with only
   a keyword/categoryId + pagination — no sort-by-popularity parameter
   exists in that call, confirmed by reading `src/mcp_tools/sourcing.py`
   directly) — it is NOT true of CJ's catalog in general: real video does
   exist on CJ for at least some genuinely popular items. The conclusion
   isn't "CJ never has video," it's "keyword search never reaches the CJ
   items that do" — which is exactly why 2.C/2.D are the preferred
   sourcing path (see this section's intro). **Caveat, checked directly:
   the Top Selling catalog's "Video Gallery" badge is NOT a reliable
   video signal** — a Lists:6747 candidate carrying that badge still had
   `productVideo: null` and no video hiding in its image set either.
   Never infer video presence from a catalog badge; always check the
   specific pid's actual `productVideo` field (2.D step 3).
3. **Reviews are not reachable via the REST API at all, but they DO
   sometimes exist on CJ's own product page — not a signal you can rank
   or filter by during Mode B keyword search either way.** CJ's REST
   endpoints (`product/list`, `product/query` in
   `src/mcp_tools/sourcing.py`) return catalog data only — no review
   count, rating, or comment field anywhere in that API, confirmed by
   reading it directly, and this can't change no matter which product you
   pick via keyword search. But the human-facing product page has a
   separate "Buyer Review" tab that is sometimes genuinely populated
   (real text, ratings, dates, and photos) for at least some listings —
   confirmed directly: two lower-demand items showed "Buyer Review (0)",
   a Lists:6747 item showed "Buyer Review (5)" with real customer photos.
   Since this is only visible on the authenticated page, it's invisible
   to Mode B keyword search regardless — but worth asking about during a
   2.C/2.D hand-off (2.D step 4). If you were asked for "a product with
   lots of real reviews" during Mode B keyword search specifically,
   **say so explicitly in your output** — e.g. "CJ's REST API has no
   review data; ranked by trend_score + video instead; a 2.D hand-off can
   check the product page's own Buyer Review tab, or reviews can come
   from a post-launch app per Section 7.C" — rather than silently picking
   a product as if the requirement were satisfied. Use `trend_score`
   (below) as your actual demand/social-proof proxy instead.
4. **Images ≥ 3** (hard gate, already enforced by `min_images=3` in your
   sourcing tools) — ideally 5+ covering front/back/detail/lifestyle, so
   Section 7.A has real material to work with instead of generating
   everything from scratch.
5. **Margin ≥ 30%, retail ≤ $50** — same economics gate as your existing
   sourcing pipeline; an impulse-buy price point matters as much here as
   it does for catalog sourcing.
6. **On-niche & safe** — no choking-hazard framing for toys, no adult/
   irrelevant listings, honest sizing (check the real variant chart, not
   the title — CJ titles lie, see `product-sourcing.md` §5).

Search broad trending keywords for this task (not narrowed to baby/
alphaforbaby unless told otherwise) — the point of this build is one
standalone new store around whatever is genuinely trending right now.
Run a few keyword rounds, score every candidate against 2.A.1-6, and
commit to the single best one rather than the first one that clears the
gates.

**Known tool limitation — verify relevance before scoring, don't trust
keyword search rankings blindly.** CJ's keyword search itself has been
confirmed to return off-topic results for perfectly reasonable queries —
`"neck massager"` surfaced women's dresses, `"led strip light"` surfaced
trousers. This is a real gap in `src/mcp_tools/sourcing.py` (worth fixing
at the source as a separate engineering task), not something you can
search around — so for every candidate, check that its actual category
and title genuinely match the niche you searched for BEFORE scoring it
against 2.A.1-6. Discard mismatches first; do not let a high `trend_score`
on an irrelevant item pull it to the top of your ranking.

**Decide your hero-video plan up front, before scoring candidates — don't
discover "no video" partway through and react to it.** Given the 294/294
null result above, a Mode B keyword-search winner will essentially never
have real video. Before running the sweep, prefer to instead do a 2.C or
2.D hand-off, where real video is genuinely available. If you are doing
Mode B keyword search anyway (no hand-off available), that's a known,
accepted trade-off, not a problem to solve mid-build — Section 7.B
covers what to do about hero video in that case, and generating one is a
fallback there, not something to default to automatically right now (see
7.B).

### 2.B — What to carry forward into `store_brief.json`

From the winning CJ listing, extract:
- `cj_pid`, `cj_listing_url` — for traceability and for connecting
  fulfillment later (per `product-sourcing.md` §6).
- `trend_score` and the keyword/category that found it.
- The full real image set (`productImageSet`) — these become your
  primary Section 7.A assets; only generate AI images to fill genuine
  gaps (e.g. an infographic overlay CJ doesn't provide).
- `supplier_video_url` if present — this becomes your primary Section
  7.B asset; still generate a 360° spin/UGC clip as a supplement, not a
  replacement, if you have the tooling for it.
- No review data is reachable via the REST API regardless of which
  product you picked (Section 2.A.3) — for a Mode B keyword-search build,
  set `real_reviews_available: false` unless a legitimate review app has
  already been wired up separately. For a 2.C/2.D hand-off, check with
  whoever did the hand-off whether the product page's own "Buyer Review"
  tab was non-zero (2.D step 4) — if so, carry the actual reported
  reviews forward instead.
- The real variant/size chart, to keep 5.B (variant names) and the FAQ
  sizing answer (5.F) honest.

### 2.C — Sourcing from CJ's Ad-Trends intelligence dashboard (Mode B2)

CJ has a separate, richer intelligence tool at
`cjdropshipping.com/intelligence/ad-trends` ("Advertising Trends" in the
left nav under Source → Products). Confirmed directly (logged-in browser
session) — it shows, per trending ad:

- A live feed of currently-hot ads ("Today's Recommended Hot Ads"),
  each tagged by platform (TikTok/Facebook), category, and rough
  engagement counts, with a **Play Video** button.
- Click into one for the full picture: the real ad video itself
  (playable, embedded — this is real ad creative, not something to
  regenerate), the brand/seller name, Ad Type (platform), Country/
  Region, **Total Views**, **Days Active**, **Comments**, **Ad Spend**
  (an estimated range, e.g. "$4.2K–$16.8K"), **Estimated Orders** (an
  estimated range, e.g. "179–2.1K"), and E-commerce System (e.g.
  "shopify"). This is a materially stronger validation signal than
  `trend_score` alone — it's an estimate of what a competitor has
  already spent and sold with this exact creative, not just "other
  stores list this."
- A **"CJ Similar Product Recommendations"** button on that detail page
  — an AI visual-match search that returns real, sourceable CJ catalog
  products (with price and a "Lists" count, CJ's UI name for the same
  demand signal as `listingCount`) that match the ad's product. This is
  the bridge from "here's a proven ad" to an actual pid you can run
  through your normal `product/query` pipeline (images, variants, margin
  gate, etc., same as Section 2.A/2.B).
- Platform and Region filters on the dashboard, if a specific market is
  wanted.

**No literal "target audience" field is exported anywhere in this tool.**
Infer it yourself from: the product category, the Country/Region shown,
and what the ad video itself actually depicts (who's on camera, the
tone/energy, the pain point being dramatized) — then write that inferred
persona straight into `store_brief.json`'s `target_customer`. That's
still much less guesswork than Section 2.A gives you, because you're
reverse-engineering a persona from creative that's already proven to
convert, not inventing one from a bare product listing.

**What to do with a Mode B2 hand-off:**
1. Take the given CJ pid to your normal `product/query` call for the
   full image set, variants, and price — same as any other sourced
   product.
2. Treat the real ad video as your PRIMARY hero video in Section 7.B —
   rank it above even a plain CJ `productVideo`, since it comes with
   proof (views/spend/orders) that it already works. Still generate a
   360°/supplementary clip if you have the tooling, but don't bury the
   proven creative under it.
3. Let the ad's own visual energy inform Section 8's color/tone choice —
   if the winning ad is bright and punchy, that's real evidence of what
   converts for this exact product, not just a stylistic preference.
4. Fill `target_customer` in the brief from your Country/Region +
   category + video inference (above), and note in your output that it's
   an inference from ad data, not an exported field — keep that
   distinction visible per the honesty standard in Section 1.
5. Carry the real stats (views/spend/orders/days-active) into your build
   notes — they're useful context for Itzik even though they don't
   belong on the storefront itself (don't put a competitor's ad-spend
   numbers on your own product page).

**Attempt this yourself first — here's exactly what to check.**
`src/mcp_tools/sourcing.py` only calls CJ's REST catalog API
(`product/list`, `product/query`, `product/getCategory`) — it has no
access to `/intelligence/ad-trends`, which is a logged-in web dashboard
feature, not part of that API. But you have real browser-automation
capability (your own tool access — e.g. a Playwright-driven browser, or
whatever's available to you), so don't stop at "the API can't do this":
1. Check whether you already have a usable, authenticated CJ web
   session (a stored cookie/session from a prior login). If so, just
   navigate to `/intelligence/ad-trends` and read it directly.
2. If not, check whether you can log in yourself: `.env` has
   `CJ_EMAIL` but, as of this writing, no CJ password/cookie/session
   token anywhere in the repo. If a password/API token for the CJ web
   login is available to you some other way (a secrets manager, an
   MCP tool, or Itzik provides one when asked), use it to establish a
   session, then proceed as in step 1.
3. Note the CAPTCHA/login-wall redirect documented above was only
   confirmed on anonymous, cookie-less requests — it has not actually
   been tested against a real authenticated browser session. Don't
   assume it blocks you too; try it.
4. Only if you're genuinely blocked — no credential exists anywhere and
   you have no way to obtain one, or CAPTCHA actually does appear even
   while authenticated — fall back to a human hand-off: tell Itzik
   specifically what's missing (e.g. "no CJ web-session credential
   available — can you provide a login, or hand me a pid + video +
   stats directly?"), rather than reporting a generic "no tooling"
   gap. Getting a durable stored CJ session provisioned is a one-time
   fix, not a per-product ask — flag it as worth doing once rather than
   requesting a hand-off on every build.

### 2.D — Sourcing from CJ's Top Selling catalog (Mode B3)

CJ has a second real, human-facing ranking page at
`cjdropshipping.com/top-selling`, confirmed directly (logged-in browser
session). It's a different view of demand than Ad-Trends — not ad
performance, but CJ's own cross-platform bestseller ranking — organized
as:

- **Overall Most Listed** — top items by current `Lists` count, each
  with a **Week-On-Week Rate** (e.g. "24%") showing whether demand is
  still rising.
- **90 Days Most Listed New Products** — newer items already gaining
  real traction, useful when "trending" should mean recent, not
  long-established.
- **Per-category Top N** (Consumer Electronics, Women's Clothing, etc.)
  — the same ranking narrowed to one niche.

`Lists` counts here run into the thousands to tens of thousands (a
label-printer example was seen at 38,139) — far above the ~30-40 ceiling
Mode B keyword search ever reaches. This is exactly the correction to
Section 2.A.2: keyword search doesn't surface CJ's genuinely popular
items at all. Confirmed this page requires an authenticated session
exactly like 2.C: an anonymous fetch redirects through a CAPTCHA/login
wall before reaching any content.

**Correction, checked directly — the catalog's "Video Gallery" badge is
NOT a reliable video signal, don't treat it as one.** It was assumed to
correlate with a real `productVideo`; direct verification on a real
Lists:6747, "Video Gallery"-badged candidate found `productVideo: null`
AND confirmed none of its 17 `productImageSet` entries were secretly a
video file either (all `.jpg`). The badge appears to just mean "has a
large image gallery," not "has an actual video." **Always check the
`product/query` response's actual `productVideo` field for the specific
pid — never infer video presence from a catalog-page badge, on this page
or any other.**

**Second correction, also checked directly on the same candidate — real
buyer reviews with photos and text DO exist on CJ, just not
predictably.** The sunrise-clock and LED-lamp products checked earlier
(Section 1, Rule 1 background) both showed "Buyer Review (0)," which is
where "CJ has no review data" came from — but this Lists:6747 candidate
showed **"Buyer Review (5)"**: real 5-star ratings, dated entries,
written text, and one review with 3 real customer photos, all labeled
"From third-party" (CJ appears to match some listings to an equivalent
third-party — likely AliExpress — listing's existing reviews). The page
also has a native **"Export Reviews"** button next to "Check Tutorial"
for pushing these into a connected Shopify store. **Caveat: this is
NOT exposed anywhere in the REST detail payload** (confirmed — no
review/rating/comment field exists there, same as before) — it is only
visible on the authenticated product page itself, so whoever does the
2.C/2.D hand-off should also glance at the "Buyer Review" tab count while
they're already on the page and report it, rather than Sol assuming
either zero or nonzero without being told.

**What to do with a Mode B3 hand-off:**
1. Take the given CJ pid to your normal `product/query` call for the
   full image set, variants, and price — same as any other sourced
   product.
2. Use the page's own `Lists` number directly as `trend_score` — it's
   already a stronger, more current signal than anything a keyword sweep
   would compute, no need to re-derive it.
3. Check the detail response's actual `productVideo` field — do not
   infer this from any catalog badge (see correction above). If it's
   genuinely populated, treat it per Section 7.B's priority order.
4. If the human doing the hand-off can report the pid's `Buyer Review`
   count from the product page (not available via API — see correction
   above), and it's nonzero, that's real, reusable review content: pull
   the actual text/photos/ratings shown and use them via Section 7.C the
   same way an Ali Reviews import would be used, since they are exactly
   that — real third-party buyer reviews for this item. If it's zero (as
   it often is), fall back to the honest empty state as usual.
5. If the item appeared in **90 Days Most Listed New Products**, note
   that in your output — "recently trending" is a more honest and
   specific claim than a bare `trend_score` number, and can inform 6.D's
   urgency line (still never fabricate a countdown from it — Rule 2).

**Attempt this yourself first — same shape as 2.C.**
`src/mcp_tools/sourcing.py` has no access to `/top-selling`, and no
access to the `Buyer Review` tab's actual content either — neither is
part of the REST catalog API, both are logged-in web page content. But
same as 2.C: use your own browser-automation capability before asking
for a hand-off. Check for a usable stored CJ session first; if none
exists, check whether you can obtain CJ web-login credentials (a
secrets manager, an MCP tool, or asking Itzik once) — `.env` currently
has `CJ_EMAIL` but no password/cookie/token for the CJ website itself.
The CAPTCHA/login-wall behavior documented above was confirmed only on
anonymous requests, not on an authenticated session, so don't assume
it blocks you without trying. Once you have a session, navigate to
`/top-selling`, and to the specific product page's `Buyer Review` tab,
and read them directly — both are ordinary logged-in pages once you
have a valid session, nothing more exotic than that. Only fall back to
a human hand-off (Itzik browses the page, gives you the pid, and
ideally the Buyer Review count/content too) if you're genuinely blocked
— name the specific missing piece (credential, or an authenticated
CAPTCHA you actually hit) rather than a generic "no tooling" claim.

### 2.E — Confirm the product with Itzik before building (required checkpoint)

This is a different kind of checkpoint from the autonomy described
above — browsing CJ's dashboards yourself needs no permission (Section
2.C/2.D, ROLE), but **committing a full build pass to a specific
product does.** A wrong sourcing call wastes an entire Section 3 build
(real tokens, real time) on the wrong thing, which is exactly the
recurring complaint that led to this skill's corrections so far — so
once you've scored and picked a candidate (Mode B, B2, or B3), stop
before Mode 1/store_brief and post a short, concrete summary, then wait
for an explicit go-ahead:
- Product name/category, and the CJ pid/listing URL.
- Real cost from CJ (`sellPrice`/`supplierPrice`) and your proposed
  actual retail price with the resulting margin (see the pricing note
  below — this is the real number, not the sourcing-gate minimum).
- Demand signal: `trend_score`/Lists count, and which mode found it.
- Video and review status, stated plainly (e.g. "no real product video
  found; a generated hero background video will cover Slot 1" / "5 real
  Buyer Reviews confirmed on the product page").
- One sentence on the target customer/angle.
Ask directly: "Is this a good product to build?" — using the ROLE
section's "How to ask Itzik for a decision" rule (an interactive
question tool if one's available, disciplined top/bottom-of-message
plain text otherwise), not a question buried inside this summary. Only
proceed to Mode 1 once Itzik confirms — if he says no or asks for
another candidate, return to Section 2 rather than defaulting back to
the first option.

**Pricing — set a real profit margin, not just the sourcing-gate
minimum.** The "Margin ≥ 30%" rule in 2.A.5 is a candidate FILTER (rules
out products with no realistic path to profit) — it is not the target
you should actually price at. 30% gross margin gets consumed fast by ad
spend (CAC), payment processing fees, and returns, leaving little to no
real profit even on a store that's genuinely selling. When you set the
actual `price.sell` for the product you're building (not the sourcing
filter), target a real markup over landed cost (product cost +
shipping) — a common, defensible starting point for paid-traffic
dropshipping is roughly **3-4x landed cost (≈65-75% gross margin)**,
adjusted down for genuinely premium/high-ticket items where a lower
percentage margin still nets more real profit, or up for cheap impulse
items where absolute margin matters more than the percentage. State the
landed cost, the price you chose, and the resulting margin explicitly
in `store_brief.json` and in your Section 2.E summary — this is a
business decision Itzik should be able to see and correct, not a number
buried in the build. This is separate from, and comes before, the
psychological "anchor"/compare-at price (1.8-2.2x the sell price,
Section 11) — that multiplier is about the displayed "SAVE X%" framing,
not the actual profit margin.

### 2.F — Catalog cleanup and the confirmed multi-product rollout (v1.42)

Up to this version, every section above was about sourcing and building
ONE product at a time (the baby carrier). Itzik has now confirmed the
next phase: alphaforbaby's live catalog has two clearly distinct groups
of products, and both a cleanup and a rollout plan are now confirmed —
this is not exploratory anymore, it's a checked, approved plan.

**The legacy catalog (~90 products) — CONFIRMED for archiving, not
deletion.** Checked directly in Shopify Admin: roughly 90 old clothing
SKUs (rompers, dresses, onesies, etc. — e.g. "Cozy Cotton Baby Romper,"
"Girls Lace Trim Dress") with `Inventory not tracked`, no real stock,
and no evidence of real reviews. One of them was also observed changing
its own title between two page loads seconds apart (same product ID,
different name) — some background process appears to still be
regenerating names on these old items; that's a live artifact of the
old catalog, not a reason to keep any of them. Itzik confirmed: **use
Shopify's Archive action, not permanent delete** — archived products
keep their data and can be restored if something is found to be
mismatched, permanent delete cannot be undone. Identify every product
NOT in the confirmed keep-list below and archive it. Given names are
actively shifting, match by product ID (the `gid://shopify/Product/...`
number), never by title text.

**The confirmed trending shortlist (9 products) — these are the ones
that stay, and the ones to run through this skill next.** All 9 share
a tight, consecutive product-ID range (created together, distinct from
the scattered legacy IDs), have real CJ-sourced stock quantities (tens
of thousands to hundreds of thousands of units) and multiple real
variants — confirmed directly in Shopify Admin, then confirmed with
Itzik as the intended trending set:

| Product | Shopify Product ID |
|---|---|
| Ergonomic Baby Hip Carrier | 7655347159111 |
| Foldable Portable Baby Crib | 7655354105927 |
| Glow Whale Bath Buddy | 7655350304839 |
| Automatic Domino Train Set | 7655348633671 |
| Montessori Shape Sorting Egg | 7655345651783 |
| Toddler Sensory Learning Board | 7655357644871 |
| Baby Beach Sun Shelter | 7655356203079 |
| Foldable Baby Bed Canopy Set | 7655352172615 |
| Cozy Portable Baby Nest | 7655287062599 |

The Ergonomic Baby Hip Carrier is the one already built (v1.30-v1.41).
**Before starting a full Section 3 build pass on any of the other 8**,
confirm per-product that Itzik's actual stated criteria are met —
trending (already satisfied, per the table above), REAL reviews (check
whether AG Product Reviews / CJ's Buyer Review tab has real data for
that specific CJ pid, same as 2.A.3/7.C — don't assume it's there just
because the carrier's was), and REAL video (check the product's actual
CJ listing for a real demo video, 7.B). A product in this table that
turns out to lack real reviews or real video is not automatically
disqualified — surface that gap plainly (Section 2.E-style summary) so
Itzik can decide whether to source reviews/video for it first or drop
it, rather than silently skipping it or silently building it without
the honest badge it wouldn't earn (Rule 1).

Work through the remaining 8 one at a time, each getting its own full
Section 3 build pass and its own Section 11/12 checklist pass — don't
batch multiple products into one pass, for the same reason a single
product build isn't rushed: a landing page built carelessly to hit a
count target fails Itzik's actual goal (a genuinely converting page per
product) even if the count is technically satisfied.

**v1.46 — checked directly: this hasn't started yet, and it shows.**
All of the v1.35-v1.45 effort went into fixing the carrier page; none
of the other 8 products in the table above have been through a Section
3 build pass at all. Confirmed by opening Glow Whale Bath Buddy's real
live product page directly: broken/blank gallery images, the payment-
icon row floating above the title with no buy-box around it at all, no
bundle/quantity-tier block, no urgency ticker or avatar strip, no mini
review carousel, "Ratings & Reviews: Be the first to review this
product" even though this is one of the 9 confirmed-trending products,
and — worse — the raw description literally renders the markdown code
fence syntax as visible page text ("` ```html `" and the closing
fence, 7.D bug #7, supposedly already fixed) plus unmapped raw CJ spec
fields shown verbatim ("Package contents: Plastic bags", "Features:
HAVE_MAGNETISM"). This is not a partially-built page with a few rough
edges — it's the default Shopify template, unbuilt. Now that the
carrier page is in a genuinely good state, this is the priority: start
the per-product reviews/video check and Section 3 build pass on the
remaining 8, actually one at a time, and don't let a new round of
carrier micro-fixes displace it again.

**v1.51 — full 9-product audit, measured page by page on the real dev
build (375px mobile). Reachability is FIXED — all 9 return 200 now.
Two new blockers replaced it, and both are Shopify-data problems, not
code.**

| Item | Carrier (ref) | Crib | Whale | Domino | Egg | Board | Shelter | Canopy | Nest |
|---|---|---|---|---|---|---|---|---|---|
| URL 200 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Price shown | $94.90 | $152.90 | $40.90 | $4.90 | $11.90 | $14.90 | $20.90 | $13.90 | $18.90 |
| Variants available for sale | 12/12 | 20/20 | 2/2 | **0/6** | **0/10** | **0/30** | **0/8** | **0/8** | **0/16** |
| Add to Cart | ✓ (ADD 2) | ✓ | ✓ | **✗ sold out** | **✗** | **✗** | **✗** | **✗** | **✗** |
| Bundle tiers (`quantityTiers`) | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Urgency line | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| "Join N verified buyers" | ✓ (20) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Real reviews | 60 | **0 (was 23 — regressed)** | 0 | 60 | 60 | 9 | 18 | 49 | 27 |
| Review photos actually load | **0/16** | — | — | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Benefits grid | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| How to use | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Why it works | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| FAQ | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Guarantee | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Real video | 1 | 1 | 1 | **0** | **0** | **0** | **0** | **0** | **0** |
| SSR page weight | 227kb | 107kb | 46kb | 187kb | 187kb | 188kb | 146kb | 169kb | 168kb |

Credit where due, all verified: the star row is fixed (one row,
per-star fill), the buy-box fallback works, the gallery dots are now a
windowed 5-dot group with a "1 / 17" counter, every URL resolves, and
`urgencyLine`/`benefits`/`whyItWorks`/`faq`/`guarantee` were authored
for six products. That's real progress — do not re-open those.

What the table says is still wrong, in priority order: 7.D #31 (six
products are unbuyable), #32 (their prices look like raw CJ
per-variant costs, one of them below landed cost), #33 (the crib's
reviews regressed to zero), #34 (no `quantityTiers` on any product but
the carrier — this is what Itzik noticed as "the bundle is missing"),
#35 (every review photo on every page is a broken hotlink), plus the
avatar-strip headline and the missing videos.

**v1.49 — reviews landed, pages did not, and 6 of the 9 have no page
at all.** Checked the real dev build directly. Good news, genuinely:
the review import worked — the carrier shows **4.8 out of 5 · 60
reviews**, the crib **4.8 out of 5 · 23 reviews**, both with real
third-party reviewer names/flags/quotes and photo counts, and the
reviews render in the mini carousel AND the bottom grid. That part is
done and should not be re-done. But: (1) only **3 of the 9** products
resolve on the storefront at all — the other 6 return 404 (7.D bug
#30), so "reviews imported for 7 products" cannot be seen by a shopper
on 6 of them; (2) of the 3 that do resolve, only the carrier has a buy
box — the crib and Glow Whale render no price, no variant picker and
no Add to Cart (7.D bug #29). Order of work, and it is not negotiable
this round: fix reachability (#30) → fix the buy box so it renders for
any product, not just the carrier (#29) → then run the Section 5C
parity gate product by product. Reviews are ahead of the pages now, not
behind them.

**v1.48 — reviews-import for the unblocked 7 is now an explicit,
standalone task, separate from waiting on a full Section 3 build pass.**
Cowork already confirmed a real, image-matched CJ source (21 real
reviews, all positive) for the **Foldable Portable Baby Crib** — run
Section 7.C Method 2 on it now with the URL given in this version's
changelog entry above, no further sourcing needed for this one. For the
other 6 (Automatic Domino Train Set, Montessori Shape Sorting Egg,
Toddler Sensory Learning Board, Baby Beach Sun Shelter, Foldable Baby
Bed Canopy Set, Cozy Portable Baby Nest), do your own CJ source-and-
review check (2.D) and then the same Method 2 import — this can and
should happen as soon as each product's real CJ pid/reviews are
confirmed, rather than waiting for that product's full Section 3 build
pass to be scheduled. Glow Whale Bath Buddy stays excluded from this
until Itzik decides what to do about its real 16%-defect finding.

### 2.G — The review gate: 15 reviews with photos, or the product stays hidden (v2.1)

Itzik's rule, non-negotiable (Level 01, rule 7): **a product is uploaded
to the store and displayed only if it has at least 15 real reviews that
each carry a real photo.** Fewer than that and the page cannot carry the
social proof the whole layout is built around — the avatar strip, the
mini carousel and the photo-forward review grid all read as empty.

**How to count — the only count that matters:**
1. Import the product's real reviews first (Level 09, Section 7.C,
   Method 2).
2. Re-host every review photo on Shopify's CDN (7.D #35). A review whose
   photo couldn't be re-hosted is a text-only review for this count.
3. Count the reviews whose photo is on `cdn.shopify.com` **and** loads
   (`naturalWidth > 0` on the rendered page). The storefront's own
   summary line — "4.8 out of 5 · N reviews · **M with photos**" — shows
   M; M must be **≥ 15**.
4. Never pad the count: no duplicated reviews, no reviews borrowed from
   a different product, no generated photos (Level 01, rule 1). If CJ's
   listing is short, the only legitimate way up is importing more real
   reviews of the same product from another real source (7.C step 2).

**What happens below 15:**
- **New product:** stop before Section 3. Report the count to Itzik as
  part of the 2.E confirmation; don't build it.
- **Already in the store:** set it to **Draft** (or unpublish it from
  the `alphaforbaby` Hydrogen channel *and* Online Store). Never delete
  it — the page, its `pdp_content` and its reviews stay intact so it can
  be re-published the moment it passes. A hidden product must not
  appear anywhere: product URL, homepage grid, collections, search,
  sitemap, or cart recommendations.
- Re-check each round; a product that passes is re-published and gets
  its normal Level 06 parity pass.

**Current count, measured on the dev build (v2.1):**

| Product | Reviews | With photos | Gate |
|---|---|---|---|
| Ergonomic Baby Hip Carrier | 60 | 60 | ✅ stays |
| Montessori Shape Sorting Egg | 60 | 36 | ✅ stays |
| Automatic Domino Train Set | 60 | 19 | ✅ stays |
| Foldable Baby Bed Canopy Set | 49 | 13 | ❌ hide (2 short) |
| Cozy Portable Baby Nest | 27 | 11 | ❌ hide (4 short) |
| Toddler Sensory Learning Board | 9 | 4 | ❌ hide |
| Baby Beach Sun Shelter | 18 | 3 | ❌ hide |
| Foldable Portable Baby Crib | 23 | 1 | ❌ hide |
| Glow Whale Bath Buddy | 0 | 0 | ❌ hide (also paused on its defect finding) |

So under this rule **3 of the 9 products stay live** today. The Canopy
Set (13) and the Nest (11) are close — look for more real photo reviews
of the same item before giving up on them. Enforced by
`TestReviewGate` (Level 14).

**v2.2 re-measure (2026-09-21) — the counts above are confirmed, and they
are at CJ's ceiling.** Every product's full review list was pulled from
CJ's own `product/productComments` (paging to `total`), and the count of
reviews carrying a photo is:

| Product | CJ reviews available | With photos (CJ ceiling) | In store now | Gate |
|---|---|---|---|---|
| Ergonomic Baby Hip Carrier | 413 | 111 | 60 / 60 with photos | ✅ stays |
| Montessori Shape Sorting Egg | 149 | 36 | 60 / 36 | ✅ stays |
| Automatic Domino Train Set | 121 | 19 | 60 / 19 | ✅ stays |
| Foldable Baby Bed Canopy Set | 49 | 13 | 49 / 13 | ❌ hide |
| Cozy Portable Baby Nest | 27 | 11 | 27 / 11 | ❌ hide |
| Toddler Sensory Learning Board | 9 | 4 | 9 / 4 | ❌ hide |
| Baby Beach Sun Shelter | 18 | 3 | 18 / 3 | ❌ hide |
| Foldable Portable Baby Crib | 23 | 1 | 23 / 1 | ❌ hide |
| Glow Whale Bath Buddy | 120 | 27 | 0 / 0 | ❌ hide (paused) |

Two things this measurement settles, so no future round re-opens them:
- **The crib is restored and still fails.** Its 23 real reviews (avg 4.78)
  are back in `custom.reviews` with both photos re-hosted (7.D #33) — but
  only 1 carries a photo, so it is still under the gate. Restoring reviews
  and passing the gate are different problems.
- **Importing more will not save five of them.** CJ has no further reviews
  of the Canopy, Nest, Board, Shelter or Crib to import — the "with photos"
  column IS the ceiling, so 2.G step 4's escape hatch ("import more real
  reviews of the same product") is closed for those five from this source.
  Either a second real source is found, or they stay hidden. Do not
  re-attempt a CJ import for them expecting a different number.
- **Glow Whale would pass the review gate** (27 photo reviews available)
  and is hidden only because of its unrelated 16%-defect pause. If that
  pause is lifted, import its reviews before re-publishing.

## v2.4 — the gate can be silently undone by other automation (2026-09-21)

Found while verifying a pricing deploy, not looking for it: three gated
products (Cozy Portable Baby Nest, Foldable Baby Bed Canopy Set, Glow
Whale Bath Buddy) had been **re-published** to Online Store and the
alphaforbaby Hydrogen channel — all four sales channels showing
`isPublished: true` — despite being correctly unpublished earlier the
same day. Re-hidden; not yet root-caused, but the leading suspect is the
**CJ stock sweep** (`Level 06` / `[[cj_stock_and_media_gate]]`-style daily
job that republishes a product once it's back in stock at the supplier),
which predates the v2.1 review gate and has no reason to know about it —
a product coming back in stock is exactly the trigger that job watches
for, and the gate's hidden state and CJ's stock state are two independent
facts about the same product with no shared source of truth.

**This needs a real fix, not a re-hide-when-noticed habit**: whatever
process republishes on a stock change must check `REVIEW_GATE_HIDDEN` (or
re-run the photo-review count) before publishing, or every future stock
sweep silently undoes this section's work. Until that's wired in,
treat the live catalog as unverified until re-checked, even right after a
round that hid the right six.

