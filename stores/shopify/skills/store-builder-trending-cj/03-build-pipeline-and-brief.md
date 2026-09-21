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
