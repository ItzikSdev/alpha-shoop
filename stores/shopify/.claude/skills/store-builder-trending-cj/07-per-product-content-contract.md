<!-- Level 7 of store-builder-trending-cj · status lives in ../store-builder-trending-cj.md (traffic lights) -->
<!-- Covers original skill section(s): 5D. Section numbers inside are kept so existing references ("7.D #31", "Section 5C") still resolve. -->

# 5D. THE PER-PRODUCT CONTENT CONTRACT — `custom.pdp_content`

**Read this before building any product page. This section is the
answer to the question that has come up every round since v1.42: "why
do the other product pages keep missing elements when the carrier page
was built properly?"**

The answer, found by reading the actual codebase (v1.50, not inferred):
**there is exactly ONE product-page template — `app/routes/
products.$handle.jsx` — and it is already complete and generic. It is
not carrier-specific. What makes the carrier page look built and the
others look empty is a single per-product Shopify metafield:
`custom.pdp_content` (a JSON blob).** The route loads it as
`content: safeJson(product.pdpContent?.value)` and then every
persuasion section on the page is rendered from one of its keys. Every
one of those components is written to return `null` when its key is
absent — deliberately, so a missing metafield degrades instead of
crashing. The effect is that a product with no `pdp_content` renders a
technically-valid page with the gallery, title, price, variant picker,
Add to Cart, description, specs and reviews… and none of the
persuasion: no urgency line, no avatar strip headline, no bundle tiers,
no benefits, no how-to-use, no comparison, no FAQ, no guarantee.

So: **for every product after the first, the build work is almost
entirely DATA AUTHORING, not coding.** The template is done. Writing
this one metafield IS "building the product page." A build report that
says the page is done because the components exist is describing the
template, which was already true before the round started.

## 5D.1 — What you get for free (no metafield needed)

These come straight from Shopify product data and always render:
gallery images, title, price + compare-at price, variant `<select>`,
Add to Cart (the simple single-purchase box — v1.49's #29 fallback),
`descriptionHtml` under "Full description", `custom.specs`, the video
from `media`, and both review blocks (mini carousel + bottom grid) from
the AG Product Reviews metafield `air_reviews_product.data` plus
`custom.reviews`.

## 5D.2 — What ONLY `custom.pdp_content` can give you

| `pdp_content` key | Renders | If the key is missing |
|---|---|---|
| `urgencyLine` | The urgency ticker above the avatar strip | no urgency line at all |
| `quantityTiers` | The whole Buy 1 / Buy 2 tier block with per-unit variant selects and "ADD N TO CART" | falls back to a plain single-item buy box (price + one select + Add to Cart) — a working page, but no bundle, no "MOST POPULAR", no per-unit pickers |
| `tierBenefits` | The one-line reason under each tier ("One for each caregiver…") | tiers render with no reason copy |
| `benefits` | The "Why parents choose it" icon grid | section absent |
| `sizeAndShipping` | "Size guide & shipping" accordion | section absent |
| `howToUse` | "How to use it" numbered steps with images | section absent |
| `whyItWorks` | "Why it works" explainer + points | section absent |
| `lifestyle` | Full-bleed lifestyle image with headline overlay | section absent |
| `comparison` | The two-column with/without comparison | section absent |
| `faq` | "Frequently asked questions" accordion | section absent |
| `guarantee` | "30 days to change your mind" block | section absent |

## 5D.3 — The exact schema, with the carrier's real values as the reference

Copy this shape. Field names are not negotiable — they are read
literally by the components listed above.

```json
{
  "urgencyLine": "SELLING QUICK, LOW STOCK 🚨",

  "quantityTiers": [
    {"qty": 2, "amountOff": 19.9}
  ],
  "tierBenefits": {
    "2": "One for each caregiver — keep a carrier at grandma's or in the second car."
  },

  "benefits": [
    {"icon": "baby", "title": "Grows with your baby", "text": "One sentence, concrete, no superlatives."}
  ],

  "sizeAndShipping": [
    {"question": "What size is it?", "answer": "Real dimensions from the CJ listing."}
  ],

  "howToUse": {
    "heading": "How to use it",
    "intro": "One optional sentence.",
    "steps": [
      {"n": 1, "title": "Step title", "text": "What the parent actually does.", "imageIndex": 3}
    ]
  },

  "whyItWorks": {
    "heading": "Why it works",
    "text": "One paragraph on the mechanism, not the feeling.",
    "points": ["short point", "short point"]
  },

  "lifestyle": {
    "imageIndex": 5,
    "headline": "Overlay headline",
    "text": "Optional supporting line."
  },

  "comparison": {
    "heading": "Compare",
    "without": {"title": "Without it", "items": ["real drawback", "real drawback"]},
    "with": {"title": "With it", "items": ["real benefit", "real benefit"]}
  },

  "faq": [
    {"question": "How do I clean it?", "answer": "Spot-clean with mild soap and cool water…"}
  ],

  "guarantee": {
    "heading": "30 days to change your mind",
    "text": "If the fit isn't right… support@alphaforbaby.com."
  }
}
```

Field notes that matter, all of them learned the hard way:
- `quantityTiers[].amountOff` is a **real fixed-amount discount in
  store currency**, not a percentage — it exists so the charged total
  lands exactly on a `.90` ending (Section 4's pricing convention), and
  it must match a real Shopify automatic discount scoped to that
  product. The carrier's `19.9` against a `$94.90` unit gives
  `$169.90` for two. Do not invent a tier whose discount doesn't exist
  in Shopify Discounts — that's a Rule 1 violation that a shopper hits
  at checkout.
- `tierBenefits` keys are **strings** of the qty (`"2"`), not numbers.
- `benefits[].icon` must be one of the five names the component maps:
  `baby`, `repeat`, `shield`, `umbrella`, `zap`. Anything else silently
  falls back to a check mark.
- `howToUse.steps[].imageIndex` and `lifestyle.imageIndex` are indexes
  into that product's own `images.nodes` array — count the real gallery
  order for THAT product; a copied index from another product points at
  an unrelated photo.
- `sizeAndShipping` and `faq` share the same `{question, answer}` shape
  (both render through the accordion component).
- `comparison` renders only when **both** `with` and `without` exist,
  each with a `title` and an `items` array. Half a comparison renders
  nothing at all.
- `whyItWorks` and `guarantee` render only when `text` is present; a
  heading alone renders nothing.
- Every string here is customer-facing copy and is bound by Section 1:
  the FAQ answers, the comparison items and the guarantee text must
  describe this store's real policies and this product's real
  properties (sourced from the CJ listing, the real reviews, and the
  real shipping/returns pages) — never copied from another product's
  metafield with the noun swapped.

## 5D.4 — How to write it for a new product (the actual per-product recipe)

1. Pull that product's real CJ listing data (2.D) and its imported
   reviews (7.C) — these are the raw material for every field.
2. Read the product's own `descriptionHtml` and `custom.specs` in
   Admin: real dimensions, materials, care instructions, package
   contents. `sizeAndShipping` and most `faq` answers come from here.
3. Count the real gallery order in Admin to pick `imageIndex` values.
4. Decide the tier: is there a genuine reason to own two? If not,
   ship `quantityTiers: []` deliberately and let the simple buy box
   render — an invented "buy 2" reason for a product nobody needs two
   of is worse than one honest price.
5. Mine the real reviews for the `benefits`, `whyItWorks` and
   `comparison` content — what buyers actually say the product solved
   is more convincing and more honest than invented marketing claims,
   and it's already on file after the review import.
6. Write the JSON, validate it parses, then write it to the product's
   `custom.pdp_content` metafield (JSON type) via the Admin API.
7. Re-render the page and run the Section 5C parity table plus the
   Section 12 tests **with that product's handle added to
   `PRODUCT_HANDLES`** (see 5D.5 — this is the step that has been
   silently skipped).

## 5D.5 — Why the test suite kept passing while 8 products were broken

Checked directly (v1.50): `tests/test_pdp_compliance.py` in the
Hydrogen repo has

```python
PRODUCT_HANDLES = [
    "ergonomic-baby-hip-carrier",
    # add each new handle here as it's built …
]
```

— one product. Every compliance run has therefore tested the carrier
and nothing else, and come back green while the crib and Glow Whale
rendered without a buy box at all. A suite that only covers the one
page that was already correct cannot catch a regression on any other
page, and a green run has been read as "the store is compliant."

**Rule from v1.50 on: `PRODUCT_HANDLES` is not a hand-maintained list.**
It must be derived from the real catalog — every product the storefront
actually serves — and there is now a test (Section 12,
`TestCatalogCoverage`) whose whole job is to FAIL when a product exists
on the storefront but is missing from the suite's coverage. Adding a
product to the store and not to the suite is itself the bug.

## 5D.6 — Bundle authored on every built product (v2.2, 2026-09-21)

7.D #34 is closed. `quantityTiers` + `tierBenefits` now exist on all eight
built products, each backed by a real Shopify automatic discount scoped to
that product at `quantity >= 2`, so the tier price the page shows is the
price checkout actually charges:

| Product | Unit | `amountOff` | Buy 2 total | Discount |
|---|---|---|---|---|
| Ergonomic Baby Hip Carrier | $94.90 | 19.90 | $169.90 | 10.5% |
| Foldable Portable Baby Crib | $152.90 | 30.90 | $274.90 | 10.1% |
| Automatic Domino Train Set | $53.90 | 10.90 | $96.90 | 10.1% |
| Montessori Shape Sorting Egg | $58.90 | 11.90 | $105.90 | 10.1% |
| Toddler Sensory Learning Board | $46.90 | 8.90 | $84.90 | 9.5% |
| Baby Beach Sun Shelter | $81.90 | 15.90 | $147.90 | 9.7% |
| Foldable Baby Bed Canopy Set | $67.90 | 13.90 | $121.90 | 10.2% |
| Cozy Portable Baby Nest | $107.90 | 21.90 | $193.90 | 10.1% |

The rule used to pick `amountOff`, so the next product doesn't have to
re-derive it: take `2 x unit`, target 10% off it (the carrier's own
ratio), then choose the nearest total ending in `.90`. `amountOff` is the
difference, and the same number goes into the Shopify discount.

**Writing the metafield is not shipping it.** After `metafieldsSet`
succeeded on all six, every page still rendered the plain buy box — the
Hydrogen dev server was serving a cached Storefront API response while the
Storefront API itself already returned the new `quantityTiers`. Restart the
dev server (or otherwise bust the storefront cache) before concluding a
metafield write didn't take, and confirm against the Storefront API
directly rather than against the rendered page alone.
