# Product Upload Pipeline

## READ THIS BEFORE SOURCING/UPLOADING ANY PRODUCT — hard rules from real incidents

1. **Never search with a bare "girl"/"boy"/"baby" keyword alone.** CJ's free-text
   search leaks heavily off-niche results even for baby-specific terms — adult
   women's fashion, pet dog dresses, electronics, kitchenware, a white-noise
   machine, nail polish have all come back for "baby X" searches. Use a
   specific term ("newborn girl romper", "baby boy onesie"), and expect to try
   several candidates from one search before one passes the guards.
2. **A rejected candidate (`{"error": ...}` from `cj_add_product`) is the
   guard working, not a bug.** Try the next candidate from the same search
   results. Do not retry the same pid, do not assume the tool is broken.
3. **If a product shows near-duplicate Color swatches, or Size values that
   don't make sense (e.g. "Set1"/"Set2"), it's a 3D `variantKey` collapse**
   (CJ encoded 3 dimensions, e.g. "Dark Blue-59cm-Set1", but the parser assumes
   2). `cj_add_product` now rejects these automatically — if you see one live,
   the guard was bypassed or is out of date; delete the product, don't patch it.
4. **A `$0.00` variant is always a bug, never acceptable.** It means the
   phantom-variant delete step (§2.6 below) didn't run. Delete the bad
   variants immediately (`productVariantsBulkDelete`) — a $0 variant is
   actually orderable for free, not just cosmetically wrong.
5. **Trust the CJ product's own stated Gender/audience text over your
   assumption from the search keyword.** Search keyword "girl" doesn't
   guarantee the product is girls-only — check the CJ description for
   "Gender: Unisex" etc. before picking a collection.
6. **One product per task, verify before moving on.** After `cj_add_product`
   succeeds, check the response has no error, confirm the collection is
   correct, and only then call `shopify_publish_products`.

How Sol actually sources and uploads a product today. This describes the real
tool path Sol calls — `src/org/agent_loop.py`'s `cj_search_products` →
`cj_add_product` → `shopify_publish_products` — not the older, separate
`src/agents/workers/ecommerce.py` batch pipeline, which Sol does not invoke.
`hydrogen-alphaforbaby/` never writes product data itself — it only queries the
Storefront API for whatever these tools already published and renders it (see
[productDisplay.md](../guides/productDisplay/productDisplay.md)).

## 1. `cj_search_products(keyword, count)` — find candidates

Wraps `search_trending_products` (`src/mcp_tools/sourcing.py`). Hard image
gate: a candidate with fewer than 3 photos is dropped before Sol ever sees it.
Each candidate carries `margin_pct` from a **capped 2.5×–3× retail/cost ratio**
(CJ's own "suggested" price if it's ≤3× cost, else a flat 2.5×) — this
`margin_pct` is for *ranking candidates*, not the price that actually gets
charged (see step 3).

## 2. `cj_add_product(pid, title, collection)` — create the product

This is the one tool Sol should use to add a product (never raw
`shopify_admin productCreate`). Step by step:

1. **Fetch full CJ detail** for `pid`. Re-checks `productImageSet` has ≥3
   entries (a plain count check — there is no vision-based image vetting in
   this path, unlike `ecommerce.py`'s `_vet_images`).
2. **Build variants** via `_build_supplier_variants(cj_variants, 2.5, ...)` —
   every CJ `variantKey` ("{Color}-{Size}") becomes one entry, priced at a
   **flat 2.5× its own CJ cost** (not the capped/suggested-price logic from
   step 1 — that only ranks candidates). Each variant carries its CJ `vid` as
   `sku` and its own CJ photo as `image`, so color selection swaps the gallery.
3. **Price**: every variant gets `_psychological_price(cost × 2.5)` (e.g.
   $9.03 → $22.90) and `compare_at_price = price × 1.35` for the struck-through
   "was" price. The product's base `price` (used only if CJ has a single
   variant) is the cheapest priced variant.
4. **Description**: CJ's own `description` field, run through
   `_clean_supplier_description()` — this strips CJ's embedded `<b>Product
   Image:</b><img>...` thumbnail strip. Those `<img src>`s point at CJ's own
   asset host (not proxied through Shopify) and render broken on the
   storefront; the real photos are already in the product's media gallery, so
   stripping them is correct, not a loss. **If you ever see broken tiny images
   inside the description text (not the gallery) on the live site, this is the
   function to check first** — confirm it's actually being called, and that
   its two regexes still match CJ's current HTML shape (CJ can change this).
5. **Create in Shopify** via `create_shopify_product` (`src/mcp_tools/shopify.py`):
   uploads all images + video as media, creates a Color and/or Size option
   (whichever dimension has 2+ distinct values), and creates **every
   Color×Size combination** — including ones CJ doesn't actually stock, since
   Shopify options are a strict cartesian product. Only combinations matching
   a real CJ variant get an explicit price/SKU; the rest are tagged
   `matched_sku: ""` in the response and are otherwise untouched by Shopify
   (default $0.00, no SKU).
6. **Delete phantom variants**: `cj_add_product` then deletes every variant
   with an empty `matched_sku` via `productVariantsBulkDelete`. **This step is
   load-bearing, not cosmetic** — a phantom variant isn't just cosmetically
   wrong, it is untracked in Shopify (`inventory_management: null`), which
   means it's *always* "available for sale" regardless of price. Skipping
   this step means a customer can actually order a nonexistent color/size
   combo for **$0.00**. If you ever see a `$0.00` variant on a live product,
   this is the first place to check — either this delete call is missing/
   failing for that product, or someone re-introduced a caller that skips it.
7. `create_shopify_product` **publishes the product to sales channels
   automatically** — `cj_add_product`'s return already says
   `"published": True`. Calling `shopify_publish_products` afterward is a
   cheap idempotent safety net (it only acts on products that are somehow
   still unpublished), not a required step for a single product.

## 2a. Niche + duplicate guards (run right after the ≥3-image check, before pricing)

CJ's search results are **not reliably on-niche even for baby-specific keywords** —
confirmed repeatedly on 2026-07-07: a "baby girl dress" search returned mostly
adult women's fashion, and other baby-keyword searches returned a white-noise
machine, a wooden cutting board, and a pet dog dress. `cj_add_product` rejects
the candidate outright (`{"error": ...}`, nothing created) before it ever
reaches Shopify if any of these hold:

1. **Denylist match** (title OR CJ `categoryName`): obvious non-apparel goods —
   electronics, kitchenware, pet accessories, baby gadgets (monitors, white-noise
   machines, strollers, pacifiers) — `_deny` in `cj_add_product`.
2. **Adult/gender-audience match — TITLE ONLY, never category**: "women's",
   "men's", "adult", "sexy", "spicy girl", "bodycon", etc. — `_adult_deny` in
   `cj_add_product`. **Category is deliberately excluded here**: CJ's own
   taxonomy nests plenty of genuine baby items under a generic parent like
   *"Women's Clothing > Tops & Sets"* — confirmed on a product literally
   titled "...For Baby Girls" that CJ filed under Women's Clothing. Trusting
   category for this check produces false-positive rejections of good products.
3. **No apparel-specific term at all** (title or category): a bare "baby" or
   "kid" match isn't sufficient — CJ's baby category also includes non-clothing
   gear. Requires an actual garment word (romper, dress, onesie, jumpsuit, etc.).
4. **Duplicate SKU**: any of the candidate's CJ variant ids already exist as a
   SKU on the store — catches re-adding the same CJ pid under a different
   title/collection.

If Sol (or you) gets a candidate rejected, **that's the guard working, not a
bug** — just move to the next candidate or try a different keyword. Keyword
tip: adding "newborn"/"infant" instead of "girl"/"boy" alone tends to dodge
CJ's adult-fashion pollution better (CJ's free-text search seems to weight
"girl"/"boy" toward youth/adult streetwear rather than infant wear specifically).

## 3. Inventory — deliberately untracked

Unlike `ecommerce.py`'s pipeline (which calls `update_inventory` to stock
every real variant to 50 units, tracked), `cj_add_product` does **not** call
`update_inventory` at all. Every real (non-phantom) variant is left
`inventory_management: null` — untracked, meaning it shows "Add to cart" and
is always orderable regardless of any quantity number. This is today's actual
behavior, not a bug to silently "fix" by copying `ecommerce.py`'s stocking
step — if you want real per-SKU stock tracking instead, that's a deliberate
design decision to make (tracked inventory needs a real quantity source, e.g.
CJ's live per-country stock via `cj_product_inventory`), not a one-line patch.

## 4. Collections

Pass `collection` (e.g. `"Baby Girls"`) to `cj_add_product` to get-or-create a
collection and add the product to it. `create_collection` already publishes a
**newly-created** collection to the storefront sales channels explicitly
(Shopify does not do this by default — confirmed live: a fresh collection
with `published_at: None` 404s on the Hydrogen storefront even with products
in it). This only covers collections created through this function — two
older, manually-admin-created collections (`Unisex`, `All Products`) were
found unpublished and fixed by hand on 2026-07-07; if a *pre-existing*
collection 404s on the live site, check its
`resourcePublicationsV2` via Admin GraphQL before assuming the product side is
broken.

## Quick troubleshooting checklist

- **Broken tiny images inside the description text** → `_clean_supplier_description` in `agent_loop.py` (§2.4).
- **A variant is $0.00 / orderable that shouldn't exist** → phantom-variant delete step (§2.6) didn't run or failed.
- **A collection 404s on the live site with products inside it** → check its sales-channel publications (§4).
- **New product invisible on the storefront** → run `shopify_publish_products`; if still invisible, check the product's `status` is `active`.
- **A good product got rejected as "off-niche"** → check whether `_adult_deny` matched on a mislabeled CJ *category* rather than the title (§2a) — if so, that's a bug (category should never be checked for gender terms); if it matched the title, it's correctly rejected — try the next candidate or a different keyword.
- **An off-niche product (electronics, adult fashion, pet items) got created anyway** → the guards in §2a didn't catch it; add the missing term to `_deny`/`_adult_deny` in `cj_add_product`, then delete the bad product manually (`productDelete` mutation).
