<!-- Level 17 of store-builder-trending-cj · status lives in ../store-builder-trending-cj.md (traffic lights) -->

# Level 17 — Itzik's decisions and the facts behind them (v3.8)

Read this before acting. It is the short memory of the project: what Itzik
decided, when, and the measurement it rests on. A later instruction from
Itzik overrides an earlier line here; update the line, don't delete the
history.

## Who does the work

- **2026-09-25** — Itzik: Claude (Cowork) does everything directly; Sol and
  the other org agents are no longer involved in this store. *(2026-10-04: for the store build this still holds; the agents run again for the platform — Level 18 §5.)* The
  `Claude outputs/` folder is not needed.

## Goal

> **Update 2026-10-03:** paid ads are on hold — Itzik wants visitors without paid advertising (Level 18 §5). The paragraph below is the original goal.

- The store must start selling through paid ads, with **more than $12
  profit on every single sale** (Itzik runs it as an exempt dealer, עוסק
  פטור, to make money from it).
- Products: baby products, not clothing; special, trending, better priced
  than competitors, with reviews.

## Decisions

| Date | Decision | Level |
|---|---|---|
| 2026-09-21 | ~20% gross margin rule; carrier $43.90, egg $26.90, domino $24.90 approved, above-median prices recorded as owner overrides | 03 |
| 2026-09-21 | Pixel >= 1000px applies to the hero only; variant images may be 800px | 09 |
| 2026-09-25 | Domino unpublished (no usable images/video; $5.79 profit/order, verdict `no_ads`) | 02 2.H |
| 2026-09-25 | Menu is Home + Products; the account control stays in the header | 05 5B.1 |
| 2026-09-25 | Review photos must swipe (mobile) and have arrows (desktop) | 09 7.C.1 |
| 2026-09-25 | Winning-product filter (2.I) before any building | 02 |
| 2026-09-25 | Temu is not a supplier (no reseller programme, Temu-branded parcels); AliExpress allowed but not cheaper for our current products | 02 2.J |
| 2026-09-25 | Run capped ad tests (Level 16); fix honesty, pixel and first-screen issues first | 16 |
| 2026-09-25 | Budget: start with **$5**, not ILS 800; grow only on evidence. Free steps first | 16 §6 |
| 2026-09-25 | Itzik wanted "LOW STOCK" for urgency; replaced with true urgency: "Ships in 1–2 business days · Order by Nov 30 for Christmas" (`holidayCutoff` in theme.config.json; disappears after the date, never moved later) | 01 rule 10 |
| 2026-09-25 | No Buy 2 discount on the egg, but keep the card look: a single selected "Buy 1" card with the price, and under it the choice row with the chosen variant's small image (`PdpQuantityTiers` single-purchase card). Deployed | 04 / 7.D #59 |

## Facts measured, with dates

- **CJ shipping floor to the US** (2026-09-25): ~$4.75 at 40 g, $6.53-7.90
  at ~200-235 g, $7.74-11.50 at 300-430 g, $19.52 at 750 g (LuWei, 5-11
  days). A US-lane quote is meaningless without US stock
  (`product/stock/queryByVid`); the carrier has none.
- **CJ reviews are nearly empty**: candidates returned 0-19 reviews in total.
- **AliExpress, ship-to US** (2026-09-25): 12-egg set $11.94-12.88
  delivered, 6-13 days — the same as CJ. First-visit prices are new-shopper
  promos, not what a dropshipping account pays.
- **Walmart price anchors** (2026-09-25): electric baby nail files $9.88-
  16.99 generic, Momcozy $24.99, Frida $34.99; water doodle mats $13.99-
  27.99; baby care kits $4.78-19.94; portable bottle warmers $13-16 generic,
  $40-80 branded; sound machines $6-26 generic, $20-40 branded.
- **Fulfilment**: storefront variants carry the CJ vid as SKU; only 9 old
  clothing products are in CJ's connection list; our webhook service places
  CJ orders with default line "CJPacket Ordinary".
- **Tracking**: no Meta pixel on the storefront until v3.8 (code added,
  inert until `metaPixelId` is set).

- **Deploying** (2026-09-25): build and deploy run from a copy of the app in
  the Linux VM with the store's own deploy token (`store-profiles/alphaforbaby/store.env`,
  never printed). Preview deployments are private (Shopify login); a local
  `npx shopify hydrogen preview` against the real Storefront API is how the
  rendered HTML is checked before production. Production = `shopify
  hydrogen deploy --no-lockfile-check --force --env-branch alphaforbaby/production`
  (NOT `--env-branch main` — that deploys to a non-production environment
  and the live site doesn't change; `scripts/deploy.sh` still has `main`),
  only with Itzik's explicit yes. `app/theme.config.json` is the source of truth; the
  profile copy must be kept identical (7.D #63).

- **Meta** (2026-09-25): ad account act_1396567725974888, page "ALPHA for BABY",
  dataset "My Business's pixel" id 2246132889517820 (now `metaPixelId`).
  Before any ad can publish Meta requires a verified phone number on the ad
  account and the account details in Account Overview — Itzik's own steps.
  The older draft campaign "5$" (Sales, $20/day) was deleted on Itzik's
  instruction (2026-09-25): "not more than $5 on advertising".

- **2026-09-25 deployed to production** (Itzik: "תעלה"): honest social proof,
  true urgency line, token Buy 2 hidden, single Home, eager hero, Meta pixel.
  Verified on alphaforbaby.com: no "Verified buyer"/"LOW STOCK"/"save 1%",
  hero loads without scrolling, nav Home · Products. Pixel verified in a
  clean headless Chromium (fbq instance + signals config for
  2246132889517820); in Itzik's own Chrome fbevents.js is blocked
  (status 0 — a blocker extension), so his visits won't count.

## Ad-test log

- 2026-09-25 — drafted, not published: campaign `egg-traffic-5usd-test`
  (Traffic, recommended setup) → ad set `US-broad-1usd-day-5days` (US only,
  Advantage+ audience, landing-page views, **$5 lifetime**, ends Sep 30) →
  ad `egg-video-20s-v1` → https://alphaforbaby.com/products/montessori-shape-sorting-egg?utm_source=meta&utm_medium=paid&utm_campaign=egg_5usd
  Video: store-profiles/alphaforbaby/ads/egg-ad-20s.mp4 (20 s, 9:16, no text, no audio).
  Copy: "Match the shape, open the egg, find the color. A calm, screen-free puzzle
  toddlers can do on their own. Free US shipping. Order by Nov 30 for Christmas." ·
  headline "Montessori Shape Sorting Eggs" · "Free US shipping · 30-day returns" ·
  CTA Shop now. Meta AI images/enhancements left OFF (generated product
  images don't match what ships). Blocked only by: verified phone on the ad
  account (Itzik), and deploying the v3.8 page fixes.
  Update: Itzik published it; status "Preparing". Sep 25: the egg's URL
  params were moved by Meta into Tracking → URL parameters (check there, not in the URL).
- 2026-09-25 — drafted, not published: campaign `carrier-traffic-5usd-test`
  (duplicate of the egg campaign; "Add an image" and "show existing reactions"
  unticked) → ad set `US-broad-1usd-day-5days-carrier` (same: US, Advantage+,
  landing-page views, $5 lifetime, ends Sep 30) → ad `carrier-video-20s-v1` →
  https://alphaforbaby.com/products/ergonomic-baby-hip-carrier + Tracking URL params
  `utm_source=meta&utm_medium=paid&utm_campaign=carrier_5usd`.
  Video: store-profiles/alphaforbaby/ads/carrier-ad-20s.mp4 (20 s, 1:1, no text,
  no audio) — Itzik uploads it (native file dialog). Copy: "A padded hip seat
  takes your baby's weight, so your arms get a break. One carrier from newborn to
  4 years, with 15 ways to carry. Free US shipping. Order by Nov 30 for Christmas." ·
  headline "Ergonomic Hip Seat Baby Carrier" · "Free US shipping · 30-day returns" ·
  Shop now. Both tests together: $10 over ~5 days (~$2/day, under the $5/day cap).
  Economics caveat: carrier ≈$9 profit/order at $43.90 (landed ≈$33, LuWei $19.52,
  no US stock) — below the $12 floor; this is a traffic/interest test, not a scale candidate.

(Empty — no test has run yet. Each round adds: dates, products, price,
profit/order, spend, purchases, cost per purchase, verdict.)

- 2026-09-25 — 1688 direct-sourcing research (real listings, browsed live, no
  account needed for pricing on air.1688.com "1688 Global"):
  - **Carrier**: factory price $7.45–$8.20/unit dropship-ready (vs CJ item
    $11.50–$13.90). https://detail.1688.com/offer/650546455142.html — 0.7kg,
    23x18x28cm. Direct sourcing looks like a real win here: est. landed
    $22–$29 vs CJ's current $32.74, est. profit $12–$19/order at $43.90
    (vs $9.59 today).
  - **Egg**: same commodity PLASTIC egg direct is $0.73–$1.95/unit but doesn't
    help much — shipping, not item cost, was always the real expense
    (est. landed $11–13 vs CJ's $13.86, barely better, still undercut by
    AliExpress at $9.05). The real fix: a WOODEN, CPC/CE-certified matching-egg
    toy, $3.58/unit dropship-ready, private-label available, already sells to
    Amazon/eBay/independent sites in North America —
    https://detail.1688.com/offer/1057616555495.html. This is a different,
    brandable product, not the same commodity AliExpress undercuts. Proposed
    reprice ~$32.90, est. landed $13-15, est. profit $17-19/order. AWAITING
    ITZIK'S DECISION — this is a full product swap (new photos/video/copy),
    flagged as an open question in the doc, not yet actioned.
  - Sourcing agent recommendation: **SourcinBox** (free app, no MOQ, per-order
    fee, native Shopify order sync, includes QC + private label) — best fit
    while pre-revenue. Yakkyofy ($79/mo Premium) is the upgrade once volume
    justifies it. NicheDropshipping needs ~10 orders/day, not a fit yet.
  - 1688 Global (air.1688.com) has a native "Dropshipping" filter: factories
    accepting single-unit orders, USD pricing shown directly, no agent needed
    just to see prices — worth Itzik browsing directly too.
  - Full writeup incl. sourcing-request message drafts and QC/packaging
    checklist: doc at https://claude.ai/code/artifact/666c7bca-7b58-4948-8c56-0d32dcee01cc
  - Next: Itzik installs SourcinBox (account creation isn't something Claude
    does on his behalf), sends the sourcing requests, and shares back real
    quotes before either product's supplier is switched.

## 2026-09-25 (cont.) — Higher-margin 1688 product candidates researched

Itzik asked for products he can profit "much more" on than the carrier/egg. Searched 1688 Global for new, differentiated baby-product categories (not just re-sourcing existing SKUs):

- **Baby sound machine + night light** (white noise, some with cry-detection/projector, CE-certified, private-label available) — factory $9-$18, ships light (~400g). US retail comps: Momcozy $24.99, Yogasleep Hushh $29.89, Hatch Go $39.99, Nanit $84.94 (babylist.com). Est. landed cost $13-$24 -> est. profit/order before ads $11-$24. **Strongest candidate found this session.**
- **Portable folding travel high chair / booster seat** — factory $7.63-$19, several Dropshipping-tagged 5.0-rated suppliers. US retail comps: Bright Starts Pop 'N Sit $29.97, Hiccapop OmniBoost $30.99, Chicco Bento 3-in-1 $34.99, OXO Perch $44.99 (thebump.com). Est. landed cost $15-$30 (bulkier, real shipping quote needed) -> est. profit/order before ads $5-$20.
- Checked silicone baby-led-weaning feeding/bowl sets (factory $0.60-$4.58/piece) — too close to complete sets AliExpress already sells $12-$18, skipped unless bundled into a $25+ differentiated kit.

Added as new "1b. New candidates" section in the 1688 Direct Sourcing Plan doc (https://claude.ai/code/artifact/666c7bca-7b58-4948-8c56-0d32dcee01cc). Numbers are 1688 catalog prices, not confirmed landed cost — next step is a real SourcinBox quote on 2-3 specific sound-machine units before committing budget.

## 2026-09-28 — SourcinBox quotes came back real; checkout domain set up; one data bug found and fixed

**SourcinBox sourcing requests resolved to real quotes** (both were "In
Progress" as of 09-25, now "Succeed"):
- **Montessori Shape Sorting Egg** (Sourcing ID 2103734290727731202) →
  SourcinBox Product ID 1584464495785402368: factory $3.08/unit +
  $8.02 shipping (single-unit "D&S Express" to US) = **$11.10 landed**.
  This lands right at the low end of the 09-25 estimate ($11-13) — now
  confirmed, not guessed. **Shopify's "Cost per item" was updated on all
  3 variants (Green Carton / Shapes & Colours / Matching Eggs) from
  $13.86 (stale CJ figure) to $11.10.** New profit/order at the live
  $26.90 price: **$15.80** — clears the $15 target from the winning-
  product filter (02 §2.I), not just the $12 floor. The egg's active ad
  test (`egg-traffic-5usd-test`, see Ad-test log above) is running on
  economics meaningfully better than what was assumed when it was
  approved.
- **Ergonomic Baby Hip Carrier** (Sourcing ID 2103734212378132481) →
  SourcinBox Product ID 1682294906922106880: factory $8.14-9.95/unit +
  $22.29 shipping = **$31.88 landed**. This is NOT the "real win" the
  09-25 estimate hoped for ($22-29) — it lands almost exactly where CJ
  already was ($32.74). Shopify's existing Cost per item ($31.73) was
  already close to this and was left as-is (no meaningful change to make).
  New profit/order at $43.90: **~$12.02** — clears the $12 floor by a
  hair, still well under the $15 target. Direct-sourcing the carrier is
  a wash, not a win; don't spend more time chasing a better carrier
  quote from SourcinBox specifically — if a $15+ carrier profit matters,
  it needs either a price increase or a different supplier/agent search.
- **SourcinBox's QC + private-label capability directly answers Itzik's
  wife's product-safety question** (raised 2026-09-28, "she wouldn't buy
  because there's no quality control on baby products"): SourcinBox was
  already the recommended agent for exactly this reason (09-25 note:
  "includes QC + private label"). No CPC/CE certificate request has
  actually been sent to SourcinBox for either live product yet — this
  is still an open action, not done. Whoever picks this up next should
  message SourcinBox (chat panel, "Yviette") asking for the existing
  factory's safety certification docs for the current plastic egg,
  since a full product swap to the wooden CPC/CE version (09-25 note
  above) is a bigger, separate decision Itzik hasn't made yet.

**checkout.{domain}.com is now set up and verified working**, done the
right way for a headless Hydrogen store — worth recording since it's not
obvious and easy to get wrong:
- Shopify's checkout for a Hydrogen storefront is served through
  whichever domain is the **Primary domain of the "Online Store"**
  sales-channel target — a completely separate domain group from
  Hydrogen's own Production domain (`alphaforbaby (Production)` group,
  untouched by this change). Settings → Domains → "Connect existing" →
  `checkout.alphaforbaby.com` → Next (this immediately registers the
  domain, not a preview) → the existing Cloudflare wildcard
  `*.alphaforbaby.com` A record already covered it, so DNS auto-verified
  with zero manual Cloudflare change → domain detail page → Type →
  **Primary domain**.
- Verified two ways before calling it done: (1) Settings → Domains shows
  every domain, including the Hydrogen Production group, as green
  "Connected" with no warning flag; (2) a real live checkout run — add
  to cart → Continue to Checkout on alphaforbaby.com → lands on
  `checkout.alphaforbaby.com/checkouts/...`, renders clean (PayPal
  express, pre-filled contact, correct total), no certificate warnings.

**Data bug found and fixed**: the egg's `Product specs` metafield had
`"Recommended age": "18 months and up"`, contradicting the product's own
description ("aged 3 to 6") and its own FAQ (which already warns it's "a
small-parts toy once opened" under 3) — a real compliance risk given US
toy-safety rules on small parts under 3. Fixed to "3 years and up" (that
one field only, rest of the JSON array untouched), verified live on
alphaforbaby.com after a cache refresh. This was a live-store bug, not
caught by Level 14's suite — Level 10 wasn't touched for it (no matching
pytest test added the same day, per this skill's own rule); whoever next
opens Level 10/14 should either add one (check `Product specs` age value
is consistent with the description/FAQ ages) or explicitly decide it's
out of scope for the automated suite.

## 2026-09-28 (later) — Egg price lowered to be more competitive vs market

Itzik pushed back on the earlier "don't lower prices" call — correctly: that call only checked our internal profit floor, not what competitors actually charge. Did real competitor research this time:

- **Egg market check**: MOONTOY 6/12-pack matching eggs $13.99 (Walmart); Montessori Vision egg sets $13.99-$68.99, flagship set $32.99 on sale (regular $64.99). Our $26.90 sat mid-pack but had room to come down without violating the $12 floor.
- **Carrier market check**: Infantino Flip 4-in-1 $31.99, AGUDAN $25.99, Regalo $27.99, GROWNSY $34.99, Momcozy $49.99, Bc Babycare CocoonGo $59.99 (all Walmart/brand listings). Our carrier at $43.90 is priced above most direct competitors, but landed cost ($31.88) leaves only $12.02/order — there is NO room to cut price without going below the floor. The real problem is sourcing cost, not retail price; needs a cheaper supplier before touching the sale price.

**Action taken**: lowered the egg's price from $26.90 to **$23.90** on all 3 variants (Green Carton, Shapes & Colours, Matching Eggs). New profit/order: $23.90 - $11.10 = **$12.80** — still clears the $12 floor, more competitive against the market, though it no longer clears the $15 target on its own (ad-test economics should be re-evaluated with this new number). Did NOT touch the carrier price — flagged instead that a cheaper carrier supplier is the actual lever, not a price cut.

Note: the egg has an ad test running (see Level 16) — changing price mid-test affects the test's cost/conversion data going forward from today.

## 2026-10-03 / 04 — Platform, visitors and organic social (see Level 18)

| Date | Decision / fact | Level |
|---|---|---|
| 2026-10-03 | **No paid advertising for now** — get visitors organically; Lia (social agent) runs it. Level 16 ad test on hold | 18 §5 |
| 2026-10-03 | Agents must not change store design (`design_lock.py`, "שלא ישנו עיצוב של חנות") | 18 §6 |
| 2026-10-03 | Live visitors shown in the 3D Office via public beacon `beacon.alpha-tech.live` (Cloudflare Tunnel `alpha-beacon`) | 18 §3 |
| 2026-10-03 | No cookie banner / "בלי עוגיות": Shopify custom pixel Permission set to "Not required"; visitor id is a per-session random id, no cookie, no PII | 18 §3 |
| 2026-10-03 | Fact: custom pixels don't run on the Hydrogen storefront, only on checkout → visitor events sent from Hydrogen code (`VisitorBeacon.jsx`, Option 1, approved by Itzik) | 18 §3 |
| 2026-10-03 | Reel-from-video is Lia's job (take the product's existing store video, never generate video); Reel the agent is not used for it | 18 §4 |
| 2026-10-04 | Fact: Instagram not linked to the Facebook Page (personal account); TikTok not connected | 18 §4 |
| 2026-10-04 | Level 17 "Sol and the other agents no longer involved" (2026-09-25) is superseded for the platform; store building stays with Claude | 18 §5 |
