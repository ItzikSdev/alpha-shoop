<!-- Level 16 of store-builder-trending-cj · status lives in ../store-builder-trending-cj.md (traffic lights) -->

# Level 16 — The paid-ad test playbook (v3.8)

Why this level exists: after three built products and a full supplier scan
(Level 02 2.I/2.J), no product could be shown on paper to be a winner.
In dropshipping a winner is found by small, capped ad tests — research only
decides what is worth testing. This level is how a test is run so it costs
a known amount and ends in a clear answer. Itzik approved the approach on
2026-09-25 (see Level 17).

## 1. Nothing is spent until all of these are true

Each is checked on the live site, not assumed. A failing one is fixed
first; it is not "noted".

| # | Must be true | How to check |
|---|---|---|
| 1 | An order actually gets to CJ and ships on a line inside the promised time | One real test order placed by Itzik, then refunded. Watch it reach CJ, note the line and the days. The storefront products are NOT in CJ's "connection" list (checked 2026-09-25: only 9 old clothing products are), so the path is our own webhook → `createOrderV2`, whose default line is "CJPacket Ordinary". If that service isn't running, orders sit unfulfilled. |
| 2 | The shipping line matches the policy page | Policy says 7-14 business days. Never let fulfilment pick the cheapest line blindly: for the carrier the cheapest is CJPacket Eub at 12-50 days. |
| 3 | Meta sees the funnel | Storefront: `metaPixelId` set in `app/theme.config.json` → PageView, ViewContent, AddToCart fire (`app/components/MetaPixel.jsx`). Checkout: Purchase comes from Shopify's Facebook & Instagram channel with data sharing on Maximum (Conversions API). Verify both in Events Manager → Test events. |
| 4 | The page is honest | Level 01 rule 10: no "Verified buyer" on imported reviews, no invented testimonials, no unprovable scarcity, no token "Buy 2" under 10% saving. |
| 5 | The first screen shows the product | Hero image loaded without scrolling on a 375px phone, including when the URL carries a variant. |
| 6 | Profit per order at the test price is known and >= $12 | From the pricing record: price x 0.971 - $0.30 - landed (item + the real fulfilment line). |

## 2. What gets tested

- At most **2-3 products at a time**, each with profit per order >= $12 at
  the test price. A product that can't reach $12 at any believable price
  is not tested.
- Prefer light parcels (<= 250 g): CJ's cheapest US shipping is ~$4.75 at
  40 g, ~$7.60-7.90 at ~220-235 g, ~$9 at 300-420 g, and $19.52 at 750 g
  (5-11 days).
- A real 5-second hook that a phone video can show.

## 3. Budget and kill rules

- Budget per product: about **ILS 400**; total for a round: the sum Itzik
  approved, never more. Campaign type: Meta **Sales** (Advantage+), not
  Traffic or Engagement.
- **Kill an ad set** that has spent ~2x the product's profit per order
  (about ILS 80-100 for a $12-15 product) with no purchase.
- **Kill a product** that has spent its ILS 400 with cost per purchase above
  its profit per order.
- **Keep and grow slowly** (+20% budget every 2-3 days) only when cost per
  purchase is under profit per order over at least 3 purchases.
- Never raise a budget to "rescue" a failing ad set.

## 4. Creative

- Video, 9:16, 15-30 seconds, the hook in the first 3 seconds.
- Best source: our own footage of the real product in use (order one sample
  per test product — it is also the quality check).
- Supplier videos only if they carry no Chinese text or watermark
  (Level 09 7.A.1).

## 5. Reading the result

- Report daily: spend, clicks, add-to-carts, purchases, cost per purchase,
  profit per order, per product. Numbers from Ads Manager and Shopify, not
  estimates.
- **Clicks but no add-to-cart** → the page or the price. **Add-to-carts but
  no purchases** → checkout, shipping cost/time, or trust. **No clicks** →
  the creative.
- The result of a failed test is written into Level 17 with the numbers,
  so the next round doesn't retest the same thing.

## 6. Micro budget: the first $5 (Itzik's decision, 2026-09-25)

Itzik starts with **$5**, not ILS 800, and wants no avoidable mistakes.
$5 cannot tell whether a product sells — at typical costs it buys a few
hundred impressions and a handful of clicks, and a first purchase would
be luck. So the first $5 answers only questions that $5 *can* answer:

1. **Do people stop for the video?** CTR (link) and cost per click.
2. **Does the page hold them?** Add-to-carts, time on page (Clarity
   recordings).
3. **Does the tracking work?** The pixel events arrive in Events Manager.

How: one product (the one with the best profit per order), one video, one
ad set, **$1 a day for 5 days**, objective **Traffic → landing page
views** (a Sales campaign cannot learn anything from $5), audience broad
US parents, automatic placements. Nothing else is changed during the 5
days.

Before the $5, all the free steps are done first (they cost nothing and
remove most of the risk): v3.8 fixes deployed, pixel id set, one test
order placed and refunded, Google & YouTube channel free listings on,
the same video posted organically on TikTok / Instagram Reels / Facebook.

Reading the $5: CTR above ~1% and a few add-to-carts → the product and
creative deserve the next $20-30. CTR under ~0.5% → change the video, not
the budget. Clicks with zero add-to-carts → the page or price. Every result
goes into Level 17's ad-test log.
