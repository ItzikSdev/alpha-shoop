# Product Sourcing — how Sol finds & vets CJ products for the baby store

Use this when the request is about **finding, adding, or improving PRODUCTS**
(source new items, fill a collection, replace weak listings, fix 1-image
products). Read it, then do the work yourself with your tools.

---

## 1. How you (Sol) are responsible for CJ products

Every product in the store originates from **CJ Dropshipping** and flows through
one pipeline. You own the whole chain:

```
keyword → CJ search → quality gate → publish to Shopify → CJ fulfills orders
```

Concretely, in this repo:

1. **Search** — `search_trending_products()` (`src/mcp_tools/sourcing.py`) calls
   CJ `product/list`, then `product/query` per hit for the real price, variants,
   and **full image set** (`productImageSet`). Your agent tool for this is
   **`cj_search_products(keyword, count)`**.
2. **Vet** — the function filters by margin (≥30%), price (≤$50), and now
   **images (≥3 — see §2)**. In the automated build it's the `ecommerce_manager`
   node that also rejects off-niche items.
3. **Publish** — `create_shopify_product()` (`src/mcp_tools/shopify.py`) pushes
   ALL images as media and builds Color/Size selectors from the CJ variants. You
   can also manage live products with the **`shopify_admin`** tool.
4. **Fulfill** — the **CJ Shopify app** is installed; it auto-syncs orders and
   tracking. Your only manual CJ-panel step is product-connection + shipping
   method per new product (see [[cj_app_fulfillment]]).

Two ways products get added:
- **Automated**: a `build_store` run drives `trend_scraper → ecommerce → publisher`.
- **Manual (you)**: `cj_search_products` → review → `create_shopify_product` /
  `shopify_admin`. Both paths now enforce the 3-image rule.

---

## 2. The 3-image rule (hard requirement)

**No single-image products on the storefront.** A product page with one photo
looks unfinished and converts badly. A product must have **≥ 3 real supplier
images** to be published.

- **Enforced in code**: `search_trending_products(..., min_images=3)` — the
  default. Candidates CJ only has 1–2 photos for are dropped during sourcing and
  never reach the publisher. `cj_search_products` inherits this default, so your
  own searches are already gated. (`min_images=0` disables it — don't, unless
  debugging.)
- **Tested**: `tests/test_sourcing_min_images.py` — run `python -m pytest
  tests/test_sourcing_min_images.py -q` after touching sourcing.
- **Existing 1-image products** already live (STORE_MEMORY flagged ~6): CJ search
  does NOT map back to already-imported SKUs, so you can't reliably re-fetch their
  galleries. Options, in order: (a) copy the 3+ images from an **identical-SKU
  sibling** already in the store (done once for "Baby Cotton Monk Onesie"); (b)
  re-source the same garment fresh from CJ and swap; (c) if neither is safe, leave
  the single clean image rather than attach WRONG photos. Never attach images
  from a different product.

Verify live counts with `shopify_admin` (`images(first:20)`), **not**
`shopify_list_products` — the latter only returns 1 image/product even when there
are 20.

**Enforcement — delete, then replace (owner rule).** A product with <3 images may
NOT stay on the store. Run `cleanup_bad_products(dry_run=True, min_images=3)` to
audit, review the list, then `dry_run=False` to DELETE the offenders (irreversible;
it also removes empty/CJK-title junk). **After any cleanup you MUST source
replacements** so the assortment doesn't shrink: find that many NEW suitable
products (≥3 images, video prioritized) and publish them. Cleanup without refill
leaves the store thin — the two steps are one job.

---

## 3. How to find the BEST product for a baby store

**Keywords — be concrete, never generic.** CJ free-text search matches literal
product names. Generic nouns ("baby clothing", "kids apparel") pull in junk
(adult clothing, storage bags, gear). Use the **garment/product type**:

| Bucket | Good CJ keywords |
|---|---|
| Baby body (bodysuits) | `baby bodysuit`, `newborn romper`, `baby onesie`, `cotton baby bodysuit`, `baby sleep sack` |
| Baby girl | `baby girl dress`, `baby girl romper`, `floral baby outfit`, `baby tutu bodysuit`, `baby girl headband set` |
| Unisex | `baby knit cardigan`, `baby waffle set`, `newborn footed sleepsuit`, `baby bib set`, `baby beanie` |
| Games / toys | `baby sensory toy`, `soft stacking rings`, `baby teether`, `montessori baby toy`, `baby activity gym` |

**Prefer the resolved CJ category over the keyword** when `resolve_category()`
finds a real leaf — for baby apparel it returns far cleaner results than free-text.

**Quality checklist for a "best" candidate** (in priority order):
0. **Has a product VIDEO — FIRST PRIORITY (owner rule).** A candidate with a CJ
   `video` (`productVideo`) wins over an equal photo-only one; a video PDP
   converts far better. Prefer video products; pass the `video` URL through to
   `create_shopify_product(video_url=...)` so it's attached as VIDEO media. The
   automated pipeline already sorts video candidates first. Video is a
   *preference*, not a hard gate — publish a great video-less item over a weak
   one with video, but between comparable candidates the video one always wins.
1. **Images ≥ 3** (hard gate, §2) — ideally 5+ showing front/back/detail/lifestyle.
2. **Margin ≥ 30%** at a retail ≤ 3× supplier (the function caps this).
3. **Retail ≤ $50** — impulse price point for baby gifting.
4. **Multiple variants** (Color/Size) — richer PDP, but a clean single-variant is OK.
5. **Trend signal** — higher `trend_score` (from CJ `listingCount`) = more stores
   already selling it = validated demand.
6. **Reasonable shipping** — check `get_shipping_cost` to the primary market (US);
   avoid items with only slow/expensive freight.
7. **On-niche & safe** — actual baby item, gender-neutral prints go to Unisex,
   no choking-hazard framing for toys, no adult/irrelevant listings.

**Deduping**: advance `page_num` across rounds and skip pids already created —
otherwise you re-fetch page 1 and dedup down to zero new items.

---

## 4. Sourcing targets (this task)

Fill each bucket to the minimum below. Every product must pass the §3 checklist
(esp. **≥3 images**). Put each in the right Shopify collection.

| Collection | Keywords (§3) | Minimum | Notes |
|---|---|---|---|
| Baby body / bodysuits | baby bodysuit, newborn romper, onesie | **20** | Core assortment |
| Baby Girls | baby girl dress/romper, floral, tutu | **20** | Girl-coded prints only |
| Unisex | knit set, waffle set, footed sleepsuit, bib | **20** | Gender-neutral only |
| Games / Toys (baby) | sensory toy, teether, stacking rings, activity gym | **20** | New bucket — may need a **"Baby Toys"/"Play" collection**; create it if missing |

**Method to hit a target** (repeat per bucket until count reached):
1. `cj_search_products("<keyword>", 12)` → candidates already gated to 3+ images.
2. Score with the §3 checklist; keep the best, drop off-niche/thin ones.
3. Publish survivors (`create_shopify_product` / pipeline).
4. Assign to the correct collection (`shopify_admin` `collectionAddProducts`).
5. Advance page / rotate keyword, repeat. Watch the CJ **daily quota** — if
   `CJQuotaExceeded` fires, stop and resume next day (don't loop).
6. Mind the **$100/month Anthropic cap** ([[token_budget_and_security]]) — source
   in focused batches, not one giant run.

---

## 5. Catalog cleanup rules (standing, owner rules)

Two more products must NEVER stay live:

- **Out of stock, no backorder.** A product where every variant is at 0 (or
  negative) inventory AND inventory policy is DENY (no overselling) can't be
  checked out — it's a dead listing. Audit + delete with
  `cleanup_out_of_stock_products(dry_run=True/False)` (`src/mcp_tools/shopify.py`).
  Products that still have stock, or allow backorder (CONTINUE), are left alone.
- **Older than 3 years AND not a baby item.** Age alone isn't the trigger — only
  age combined with no longer being baby-relevant. There's no Shopify field for
  "is this a baby product," so it needs a real read of the title/description, not
  a keyword guess. `audit_stale_products(max_age_years=3)` is READ-ONLY and returns
  candidates (title/type/description/age) for review; judge each one and delete
  with `delete_shopify_product(id)` — keep anything baby-adjacent or ambiguous.
- **Sized for older kids, not babies (regardless of listing age).** CJ titles lie —
  "Toddler Cozy Crewneck Set" turned out to be sized 130-150cm (ages 8-12) and
  "Girls' Sleeveless Vest & Shorts Set" was 110-140cm (ages 4+); both deleted
  2026-08-01. The real signal is the Size variant chart, not the title/description.
  `audit_size_mismatched_products()` (READ-ONLY) flags any product where **every**
  size option is above the baby/toddler cutoff (~98cm / no month-labeled or newborn
  size) — deterministic size-chart parsing, not LLM guessing. If a product has even
  one baby-appropriate size it's left alone. Delete flagged ones with
  `delete_shopify_product(id)`. When sourcing NEW products, check the CJ variant
  size chart the same way before publishing — don't trust a "baby"/"toddler" title.

Both rules also run as part of the periodic quality scan
(`scan_and_open_tickets` in `src/org/tickets.py`) — it opens a ticket per problem
found (dry-run only, no auto-delete) so nothing silently disappears. The owner can
also trigger either rule directly in Telegram chat (`src/org/conversation.py`
ops `remove_out_of_stock` / `remove_stale`); `remove_stale` runs an LLM judgment
pass over title/description before deleting anything.

---

## 6. After publishing (required)

Follow `docs/AGENT_WORKFLOW.md`:
- Each new product: main + **≥3 images**, real price (not $0, not absurd), unique
  SEO title/description, correct collection, variants that add-to-cart.
- Connect the product + set shipping method in the **CJ panel** ([[cj_app_fulfillment]]).
- Run `QA.md` + `SEO.md` (no dup images/products, links resolve, mobile OK).
- Append one line to `docs/STORE_MEMORY.md` and post to Slack (what was added, per
  bucket, image counts confirmed).
