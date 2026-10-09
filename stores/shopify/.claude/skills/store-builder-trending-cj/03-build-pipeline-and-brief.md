<!-- Level 3 of store-builder-trending-cj · status lives in ../store-builder-trending-cj.md (traffic lights) -->
<!-- Covers original skill section(s): 3, 4. Section numbers inside are kept so existing references ("7.D #31", "Section 5C") still resolve. -->

# 3. THE BUILD PIPELINE (run every step, in order)

This mirrors the two-mode loop pattern already used in Itzik's design
system (brief → JSON plan → build → checklist-gated review, max 3
iteration passes). Use it the same way here.

**MODE 1 — PLAN.** If you sourced the product yourself (Mode B/B2/B3),
Itzik must have already confirmed it per Section 2.E before you start
here — don't skip that checkpoint just because you found a candidate
you're confident in. From the sourced or given product, produce a
`store_brief.json` (schema in Section 4) before writing a word of final
copy. This is your scratchpad — get the strategy right before writing
sentences.

**MODE 2 — BUILD.** Using the brief, produce, in this order:
1. Design tokens (Section 8) — pick the bold accent color FIRST, per
   8.A; it should inform how punchy the copy and imagery feel too.
2. Page blueprint filled in (Section 5) — every section, in order
3. All copy (Section 6 formulas)
4. All image prompts (Section 7.A) — real CJ images first, AI-generated
   only to fill gaps
5. All video prompts (Section 7.B) — real CJ video first if present
6. Trust/urgency/review components (Section 7.C, respecting Section 1)
7. FAQ (Section 6.F)

**MODE 3 — SELF-CHECK.** Run the Section 11 checklist against your own
output. If any item fails, fix it and re-run the checklist. Maximum 3
passes — if it still fails after 3, ship your best version and flag the
remaining failed items explicitly at the top of the output.

---

# 4. `store_brief.json` — fill this in first

```json
{
  "source": "cj_dropshipping | cj_ad_trends_handoff | cj_top_selling_handoff | given_input",
  "cj_pid": "if sourced via Section 2, else null",
  "cj_listing_url": "if sourced via Section 2, else null",
  "trend_score": "CJ listingCount/'Lists' or equivalent, if sourced",
  "ad_trend_data": {
    "note": "fill only if source is cj_ad_trends_handoff (Section 2.C), else omit this object",
    "ad_video_url": "the real proven ad video — primary hero video, see 7.B",
    "platform": "TikTok | Facebook",
    "country_region": "as shown on the dashboard",
    "total_views": "as shown",
    "days_active": "as shown",
    "ad_spend_range": "as shown, e.g. '$4.2K-$16.8K'",
    "estimated_orders_range": "as shown, e.g. '179-2.1K'",
    "inferred_target_audience": "your inference from category + country/region + what the ad video shows — state clearly this is inferred, not exported (Section 2.C)"
  },
  "top_selling_data": {
    "note": "fill only if source is cj_top_selling_handoff (Section 2.D), else omit this object",
    "ranking_section": "Overall Most Listed | 90 Days Most Listed New Products | category top-N",
    "week_on_week_rate": "as shown, e.g. '24%', if present on this ranking",
    "category": "as shown on the page"
  },
  "product_name_working": "what the input/listing calls it",
  "brand_name_new": "an invented, ownable brand name for this store (not the product's generic name)",
  "store_mode": "single_hero_product | multi_product_niche",
  "target_customer": {
    "who": "e.g. parents of infants 0-12mo, gift-buyers for X occasion, pet owners with anxious dogs",
    "core_pain_point": "the one problem this product removes",
    "core_desire": "the one feeling/outcome they actually want (not the feature)"
  },
  "positioning_angle": "the ONE reason this product beats the obvious alternative — pick exactly one: [convenience | safety/peace-of-mind | status/gift-worthiness | novelty/fun | time-saved | money-saved]",
  "price": {
    "sell_price": "number",
    "anchor_price": "number, must be 1.8x-2.2x sell_price (matches observed 48-51% off pattern)",
    "currency": "as given, default USD"
  },
  "hero_variant_names": ["fun/descriptive variant names, NOT just 'Color A/B/C' — see 6.B"],
  "urgency_mechanism": "real_date_countdown | real_stock_count | evergreen_no_fake_urgency",
  "review_state": "app_imported_real | empty_honest | founder_claims_only",
  "real_review_count": "number, ONLY if review_state is app_imported_real (e.g. via Ali Reviews, or reviews reported from a pid's own Buyer Review tab during a 2.C/2.D hand-off) — never reachable via the REST API itself, see Section 2.A.3/2.D",
  "supplier_video_url": "if a real CJ/supplier video exists, else null",
  "supplier_image_urls": ["real CJ images, if sourced via Section 2"],
  "tone": "pick 1-2: [playful/emoji-forward | warm/reassuring | bold/energetic | bold/humorous] — avoid defaulting to 'premium/minimal' unless the product genuinely calls for restraint, see 8.A",
  "shipping_reality": {
    "processing_days": "e.g. 2-5",
    "delivery_days": "e.g. 6-10",
    "free_shipping": true
  }
}
```

Rules for filling this in: `anchor_price` must never be arbitrary — it
should look like a price this product could plausibly have sold at
before a discount, not 5x inflated (which reads as fake to buyers and
kills trust instantly). `positioning_angle` must be singular — every
reference store had exactly one emotional angle running through the
whole page, not three competing ones.

**Pricing display convention (v1.31, corrected v1.32)**: every price
the customer actually PAYS ends in **.90** — `sell_price` and every
bundle-tier's real charged total (Buy 2, Buy 3, and any add-on price).
This is an explicit Itzik instruction, not just a cosmetic rounding of
the displayed number, and it must be the real checkout amount, not a
rounded label (Rule 1).

**v1.32 correction — this does NOT apply to struck-through "was"/anchor
prices**: a real Sol build found that percentage-off discounts on a
`.90`-ending base essentially never land back on `.90` (confirmed:
`$94.90 × 2 × 0.9 = $170.82`, and there is no `.90`-ending base for
which any clean percentage produces another `.90`-ending result), and
that an honest anchor price is definitionally `qty × unit price` — if
the unit price ends in `.90`, doubling it always ends in `.80` and
tripling it always ends in `.70`. Requiring the crossed-out reference
price to ALSO end in `.90` would force one of two dishonest moves: an
anchor that isn't actually `qty × real unit price` (a fabricated
comparison, Rule 1), or a charged total that doesn't really end in
`.90` (defeats the whole point). So: **only the real charged total must
end in `.90`; the struck-through original-price line is allowed to end
in whatever an honest `qty × unit price` calculation actually produces
(`.80`, `.70`, etc.) — don't force it.** To hit a `.90` charged total
per tier while keeping the base unit price fixed and honest, use a real
fixed-amount discount (not a percentage) sized so the math resolves
exactly — e.g. `−$19.90` at qty≥2, `−$99.80` at qty≥3 against a $94.90
base, landing on $169.90 / $184.90 exactly. The displayed "SAVE X%"
badge must then show the real resulting percentage, rounded DOWN if it
must be rounded at all — never overstate the discount (Rule 2). Verify
every tier's real charged total in an actual test cart, not just the
displayed number.

**Pricing rule — market check + ~20% margin (v2.3, Itzik's decision).**
An outside review of the store found the prices far above market
(domino $53.90 vs $19.99–$25.19 for comparable 80–200-piece sets at
Walmart; matching eggs $58.90 vs $7.99 at Walmart and $39.97 at a
boutique Montessori store; hip-seat carrier $94.90 vs $25.99–$59.99,
above real brands like Momcozy at $49.99). Itzik's decision: price for
roughly **20% gross margin**. How to set every product's price:

1. **Landed cost** = the CJ item price for that variant + the real CJ
   shipping cost to the US for the shipping method actually used.
   Record both, with the date checked. Also write it into Shopify's
   "Cost per item" on every variant so Shopify shows margin itself.
2. **Payment fee** = 2.9% + $0.30 per order.
3. **20% price** = (landed cost + $0.30) / (1 − 0.029 − 0.20), rounded
   UP to the next price ending in `.90`.
4. **Market check**: collect at least 3 comparable listings for the same
   kind of product (Walmart, Amazon, Target, Temu — same piece count /
   size where possible) with prices and links. Take the median.
5. **Final price**:
   - If the 20% price is at or below the market median → price at the
     20% price, or up to just under the median (`.90` ending) if Itzik
     approves the higher margin. Never price above the median.
   - If the 20% price is ABOVE the market median → the product can't
     compete at 20%. Do not raise the price to hit 20% and do not drop
     below 20%; report it to Itzik — the product may not be viable.
6. **Buy 2 tier**: the Buy 2 charged total (ending `.90`) must also
   keep ≥ 20% on two units' landed cost. If a 10%-off Buy 2 would drop
   below 20%, use a smaller real discount rather than breaking the
   floor.
7. **Compare-at prices**: only show a struck-through price if it is an
   honest `qty × unit price` (the Buy 2 anchor) — no invented "was"
   price on single units.
8. Save the decision to
   `store-profiles/alphaforbaby/pricing/<handle>.json`:
   `{handle, variant_costs: [{variant, cj_item, cj_shipping, landed}],
   fee_model, price, buy2_total, margin_pct, buy2_margin_pct,
   market: [{source, title, price, url, checked_at}], market_median,
   approved_by_itzik: true|false}`. Nothing ships with
   `approved_by_itzik: false`.

Worked example (domino, landed ≈ $10.54): the exact 20% price is
$14.06 → $14.90 (≈ $3.63 profit, 24%). The market median is ~$22, so
$14.90 is allowed, and anything up to $19.90 (≈ $8.48, 43%) stays under
the market. **Be aware:** 20% on a $15 item is about $3 per order. That
works for free/organic traffic; if a paid ad costs more than ~$3 per
sale, every sale loses money. Know the ad cost per sale before choosing
the low end.

**Step 3b — the 20% price is a FLOOR, and it must also admit a Buy 2
(v2.5).** Step 3's `(landed + $0.30) / (1 − 0.029 − 0.20)` rounded up to
`.90` gives the *lowest* compliant unit price, not the only one. Before
settling on it, check that a compliant Buy-2 total exists at that price:

    floor_total(2 units) = (2 × landed + 0.30) / (1 − 0.029 − 0.20)
    valid Buy-2 totals   = values ending in .90, >= floor_total, < 2 × unit

If that set is empty, the unit price does not work — **step up to the
next `.90` and re-check**, because `.90`-ending totals are $1.00 apart
and a two-unit price only clears the floor by a few cents at the
minimum. Do NOT drop the bundle to make the arithmetic close: it is
required on every product (Level 06 row 9), and 7.D #34's exemption is
about the product, not the price. Worked example, the hip carrier
(landed $32.74): $42.90 is the bare 20% price and admits **no** valid
Buy 2 ($0.48 of headroom); $43.90 admits $85.90 at $1.90 off — Buy 1
21.8%, Buy 2 20.5%. See 7.D #42.

**Recording an above-median price (v2.5).** Step 5 says never price
above the market median. Itzik can override that per product, but the
override goes in the pricing record as a `market_override` block
(`approved_by_itzik`, `reason`, `approved_at`) — not as an unexplained
high price. `TestPricingRule::test_not_above_market_median` passes on a
complete override and re-emits it as a warning on every run, so the
deviation stays visible instead of quietly becoming the baseline; an
absent or partial override still fails.

