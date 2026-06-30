"""E-commerce Manager — creates branded Shopify products from scraper results."""
from __future__ import annotations
import json
import logging
import math
import os
import re
from langchain_core.messages import HumanMessage, SystemMessage
from src.agents.state import AgentState
from src.llm import get_llm
from src.mcp_tools.shopify import (
    create_shopify_product,
    update_inventory,
    create_collection,
    add_product_to_collection,
    list_shopify_products,
    delete_shopify_product,
)
from src.mcp_tools.shopify_theme import setup_navigation
from src.tracing import agent_log
from src.tracing.context import current_node

logger = logging.getLogger(__name__)


def _parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```\s*$', '', text)
    return json.loads(text.strip())


async def _save_product_mapping(
    store_id: str,
    shopify_product_id: str,
    supplier_product_id: str,
    supplier_sku: str,
    cost_price: float,
    retail_price: float,
) -> None:
    """Record the Shopify↔CJ cross-reference so price/stock monitoring and
    fulfillment can look this product back up later. Non-fatal on failure —
    a DB hiccup shouldn't undo a product that's already live on Shopify."""
    if not supplier_product_id:
        return
    try:
        from src.db.engine import get_session
        from src.db.models import ProductMapping

        async with get_session() as session:
            await session.merge(ProductMapping(
                shopify_product_id=shopify_product_id,
                store_id=store_id,
                supplier_product_id=supplier_product_id,
                supplier_sku=supplier_sku,
                cost_price=cost_price,
                retail_price=retail_price,
            ))
    except Exception as exc:
        logger.warning("Failed to save product mapping for %s: %s", shopify_product_id, exc)


async def _existing_supplier_ids(store_id: str) -> set[str]:
    """CJ product ids already listed for this store (from product_mappings). The
    RELIABLE cross-run dedup key: after re-branding renames the title and Shopify
    renames the images, only the CJ product id still matches — so this is what stops
    the same supplier item being listed twice across separate runs."""
    try:
        from sqlalchemy import select as _sel
        from src.db.engine import get_session
        from src.db.models import ProductMapping
        async with get_session() as session:
            rows = await session.execute(
                _sel(ProductMapping.supplier_product_id).where(ProductMapping.store_id == store_id)
            )
            return {str(r[0]) for r in rows.all() if r[0]}
    except Exception as exc:
        logger.warning("Could not load existing supplier ids: %s", exc)
        return set()


# ── Brand identity ────────────────────────────────────────────────────────────

_BRAND_SYSTEM = """\
You are a brand strategist for a premium e-commerce store.
Given a raw supplier product title and category, output a JSON object with:

{
  "brand_title": "Short, appealing 3-6 word product name. Remove ALL supplier jargon, model numbers, specs. Sound like a real consumer brand. Examples: 'Wireless QR Barcode Scanner' NOT 'Portable 1D Bluetooth Scanner CJ-88124'",
  "collection": "The store collection this belongs to. Use ONE of: Home Decor, Kitchen & Dining, Tech Accessories, Personal Care, Fitness & Wellness, Pet Supplies, Baby & Kids, Outdoor & Garden, Fashion Accessories, Office & Productivity",
  "hook": "One sentence emotional/outcome-driven opener for the product copy. Start with the customer benefit or desire, NOT the product name. Example: 'Say goodbye to tangled cables and slow checkout lines.'",
  "audience": "One short phrase describing who buys this: e.g. 'remote workers who scan inventory', 'dog owners who hate nail clippers'"
}

Output ONLY valid JSON. No markdown.
"""

# ── Premium copy ──────────────────────────────────────────────────────────────

_COPY_SYSTEM = """\
You are a senior conversion copywriter for a premium Shopify brand — think MVMT, Beardbrand, Tanaor.
You write product descriptions that make people stop scrolling and feel they found exactly what they needed.

INPUT: brand_title, category, hook (emotional opener), audience, real_specs (actual
supplier spec sheet — fabric, fit, pattern options, set contents; may be empty)

If real_specs is present, ground at least 1-2 bullets in those ACTUAL details
(fabric name, closure style, number of pieces, etc.) instead of inventing generic
ones — e.g. prefer "Soft cotton blend — gentle on sensitive newborn skin" over a
made-up claim, when real_specs says the fabric is cotton. Never copy real_specs
verbatim or mention supplier/sourcing language; translate it into customer-facing
benefit language.

OUTPUT: Valid HTML only — <p> and <ul><li> tags. NO markdown, NO wrapper divs.

STRUCTURE:
1. <p> — Use the hook verbatim, then expand into 1-2 sentences connecting the customer's desire to the product.
2. <p> — One sentence that states what the product IS and WHO it's for (specific, not vague).
3. <ul> — Exactly 5 <li> bullets. Format: "[Short outcome label] — [specific explanation]"
   Examples:
   ✓ "Zero-cord freedom — pairs instantly with any Bluetooth device up to 10 meters away"
   ✗ "High quality — made with premium materials for lasting durability"
   Rules for bullets:
   - Lead with the outcome, explain the feature
   - At least one bullet addresses a common worry ("Won't scratch — rubberized tip protects surfaces")
   - At least one bullet is about ease or speed of use
   - No invented certifications, stats, or brand names
   - No vague words: premium, innovative, high-quality, perfect, amazing
4. <p class="trust"> — ONE trust line. Pick the strongest: free returns / satisfaction guarantee / ships in 24 hours / designed to last. Keep it short and specific.

TONE: Confident, warm, direct. Speak to the customer as "you". Natural English.
LIMIT: 280 words max.
Output ONLY the HTML.
"""

# ── Trust & guarantee block appended to every product ────────────────────────

_TRUST_HTML = """
<div class="product-trust">
  <ul class="trust-badges">
    <li>✓ Free shipping on all orders</li>
    <li>✓ 30-day hassle-free returns</li>
    <li>✓ Satisfaction guaranteed or your money back</li>
  </ul>
</div>
"""


async def _brand_product(title: str, category: str) -> dict:
    """Generate branded title, collection, hook, and audience for a supplier product."""
    llm = get_llm("ecommerce", temperature=0.6)
    response = await llm.ainvoke([
        SystemMessage(content=_BRAND_SYSTEM),
        HumanMessage(content=f"Supplier title: {title}\nCategory: {category}"),
    ])
    try:
        return _parse_json(str(response.content))
    except (json.JSONDecodeError, ValueError):
        return {
            "brand_title": title,
            "collection": category or "General",
            "hook": f"Discover a smarter way to {category.lower()}.",
            "audience": "anyone looking for quality products",
        }


def _extract_real_specs(supplier_description_html: str) -> str:
    """
    Pull the plain-text 'Product information' spec line out of CJ's raw HTML
    description (fabric, fit, pattern, set contents) so the copy LLM can ground
    claims in real supplier data instead of inventing generic ones. Returns ""
    if the description doesn't have a recognizable spec section.
    """
    if not supplier_description_html:
        return ""
    match = re.search(
        r'Product information:?\s*</b>?(.*?)(?:<b>Packing|<b>Product Image|$)',
        supplier_description_html, re.IGNORECASE | re.DOTALL,
    )
    block = match.group(1) if match else supplier_description_html
    text = re.sub(r'<br\s*/?>', '; ', block)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:600]


async def _write_description(brand_title: str, category: str, hook: str, audience: str, real_specs: str = "") -> str:
    """Write premium product copy at TANAOR-level quality."""
    llm = get_llm("ecommerce", temperature=0.7)
    prompt = (
        f"brand_title: {brand_title}\n"
        f"category: {category}\n"
        f"hook: {hook}\n"
        f"audience: {audience}\n"
        f"real_specs: {real_specs}"
    )
    response = await llm.ainvoke([
        SystemMessage(content=_COPY_SYSTEM),
        HumanMessage(content=prompt),
    ])
    body = str(response.content).strip()
    return body + _TRUST_HTML


def _image_key(product: dict) -> str:
    """
    Normalize a product's main image URL into a comparable identity key.

    CJ source images keep the same filename across re-scrapes even when query
    strings / CDN paths differ, and Shopify's GQL image URLs share that filename
    too — so comparing just the filename (without extension/query) reliably
    catches "same physical product, different LLM-branded title" duplicates
    that a title-only check misses.
    """
    images_field = product.get("images")
    if isinstance(images_field, dict):
        # Shopify GQL shape: {"images": {"nodes": [{"url": "..."}]}}
        nodes = images_field.get("nodes", [])
        url = nodes[0]["url"] if nodes else ""
    else:
        # Scraper candidate shape: {"image": "...", "images": ["...", ...]}
        url = product.get("image") or (images_field or [""])[0]
    if not url:
        return ""
    filename = url.split("/")[-1].split("?")[0]
    return filename.rsplit(".", 1)[0] if "." in filename else filename


def _psychological_price(price: float) -> float:
    """Round up to the nearest dollar minus 10 cents — e.g. 11.47 → 11.90, 7.03 → 7.90."""
    return max(0.90, math.ceil(price) - 0.10)


# Catalog target. The owner wants a full store (min 100 SKUs), so the default is
# 100; override with ORG_MAX_STORE_PRODUCTS. (Was a hard 30 "curated" cap before.)
_MAX_STORE_PRODUCTS = int(os.environ.get("ORG_MAX_STORE_PRODUCTS", "100"))

# How many candidate images to vision-vet per product (keeps cost bounded).
_VET_MAX_IMAGES = int(os.environ.get("IMAGE_VET_MAX", "5"))

_IMAGE_VET_SYS = (
    "You are an e-commerce visual merchandiser deciding if a supplier photo is good "
    "enough to SELL with on a premium baby store. Look at the image and KEEP it ONLY "
    "if it's an attractive, styled/lifestyle product photo. REJECT if ANY of these are "
    "true: plain white/grey studio background with no styling; ANY visible text, "
    "watermark, label, sticker or foreign language (e.g. Chinese characters) in the "
    "image; a collage / multiple panels stitched together; blurry or low quality; or it "
    "doesn't clearly show this product. When unsure, REJECT. "
    'Reply ONLY JSON: {"keep": true|false, "reason": "<max 6 words>"}'
)


async def _vet_images(urls: list[str], product_title: str) -> tuple[list[str], str]:
    """Vision-vet supplier (CJ) images and return (kept_urls, note). Keeps only clean,
    sellable lifestyle shots — rejects white-background-only, any text/foreign language
    (Chinese), collages, and low quality (the owner's image rules). Uses the cheap Haiku
    vision tier. Budget-aware: when the monthly/daily cap is hit the team runs on the
    local model (no vision), so we KEEP the images rather than blindly dropping them and
    say so — never silently strip a product's only photos because we couldn't look."""
    from src.budget import over_budget
    urls = [u for u in urls if u]
    if not urls:
        return [], "no images on candidate"
    if over_budget():
        return urls, "vetting skipped (budget cap → local model has no vision)"
    kept: list[str] = []
    checked = 0
    for u in urls[:_VET_MAX_IMAGES]:
        checked += 1
        try:
            llm = get_llm("scraper", temperature=0.0, max_tokens=120)  # Haiku, vision-capable
            resp = await llm.ainvoke([
                SystemMessage(content=_IMAGE_VET_SYS),
                HumanMessage(content=[
                    {"type": "text", "text": f"Product: {product_title}. Keep this image for the store?"},
                    {"type": "image_url", "image_url": {"url": u}},
                ]),
            ])
            txt = str(resp.content)
            m = re.search(r"\{.*\}", txt, re.DOTALL)
            verdict = json.loads(m.group(0)) if m else {}
            if verdict.get("keep") is True:
                kept.append(u)
        except Exception:
            # Couldn't vet this one (vision unavailable / transient) — don't drop it.
            kept.append(u)
    if not kept:
        return [], f"all {checked} image(s) rejected (white-bg / text / low quality)"
    return kept, f"kept {len(kept)}/{checked} vetted image(s)"
_MAX_BACKFILL_PER_CYCLE = 5  # Cap color-selector self-heals per cycle (bound live mutations)
_MAX_SOURCING_ATTEMPTS = 3  # retry trend_scraper with relaxed terms this many times before giving up

_FIT_SYSTEM = """\
You are a strict product curator for a focused niche store.
Given the store's product category and a supplier product title, answer ONE word: YES or NO.
YES = this product is exactly a {category} and belongs in this store.
NO = this product is something different (different product type, accessory, or off-niche).

IGNORE marketing/quality adjectives in the category when judging fit — words like
"premium", "organic", "artisan", "luxury", "eco-friendly" describe how WE will brand
and price the item, not a literal requirement the supplier's listing text must contain.
A plain, unbranded supplier listing of the correct core product TYPE is still a YES —
judge only whether the product TYPE matches, never whether the title repeats those
adjectives. E.g. category "premium organic baby clothing" + title "Infant Cotton Romper"
= YES (it's baby clothing; "premium organic" is our branding to add later, not theirs).

Be strict on PRODUCT TYPE only. If the store sells women's silver rings, a necklace = NO.
A gold men's ring = YES. If the store sells soy candles, a wax melt = YES. A diffuser = NO.
Answer only YES or NO.
"""


_COLLECTION_PICK_SYSTEM = """\
You sort a supplier product into exactly one of the store's existing collections.
Given the product title and the list of collection names, answer with ONLY the
single best-matching collection name, verbatim as given. If genuinely none fit
(e.g. it's a gift set and there's no "Gift Sets" collection), pick the closest one.
"""


async def _pick_collection(supplier_title: str, collections: list[str]) -> str:
    """Classify a product into one of the brief's defined collections (e.g. Boys vs Girls)."""
    if not collections:
        return ""
    if len(collections) == 1:
        return collections[0]
    llm = get_llm("ecommerce", temperature=0.0)
    response = await llm.ainvoke([
        SystemMessage(content=_COLLECTION_PICK_SYSTEM),
        HumanMessage(content=f"Collections: {', '.join(collections)}\nProduct title: {supplier_title}"),
    ])
    answer = str(response.content).strip()
    # Exact match first, then substring either direction (LLM may answer "Girls" for "Baby Girls")
    picked = next((c for c in collections if c.lower() == answer.lower()), None)
    if not picked:
        picked = next((c for c in collections if c.lower() in answer.lower() or answer.lower() in c.lower()), None)
    picked = picked or collections[0]
    agent_log(f"  → collection: '{picked}' (for '{supplier_title[:40]}')", "info")
    return picked


async def _fits_niche(supplier_title: str, product_category: str) -> bool:
    """Return True only if the supplier product exactly matches the store's product category."""
    llm = get_llm("ecommerce", temperature=0.0)
    response = await llm.ainvoke([
        SystemMessage(content=_FIT_SYSTEM.format(category=product_category)),
        HumanMessage(content=f"Store category: {product_category}\nProduct title: {supplier_title}"),
    ])
    answer = str(response.content).strip().upper()
    return answer.startswith("Y")


async def _curate_existing_products(product_category: str) -> int:
    """
    List all products in Shopify.
    Delete any that don't fit the store's product category.
    Returns how many were deleted.
    """
    existing = await list_shopify_products()
    if not existing:
        return 0

    deleted = 0
    agent_log(f"Curating {len(existing)} existing products against niche '{product_category}'...", "info")
    for p in existing:
        title = p.get("title", "")
        gid = p.get("id", "")
        fits = await _fits_niche(title, product_category)
        if not fits:
            agent_log(f"✗ Deleting off-niche: '{title}'", "warning")
            ok = await delete_shopify_product(gid)
            if ok:
                deleted += 1
        else:
            agent_log(f"✓ Keeping: '{title}'", "info")
    return deleted


async def ecommerce_node(state: AgentState) -> dict:
    """
    LangGraph node: curate → cap check → brand → validate → publish.

    Steps:
    1. Delete any existing Shopify products that don't fit the store's product_category
    2. Count how many products remain — skip if already at _MAX_STORE_PRODUCTS
    3. For each scraper candidate, validate niche fit before publishing
    4. Publish only niche-matching products, up to the cap
    """
    current_node.set("ecommerce_manager")

    store_id = state.get("store_id", "")
    store_brand = state.get("store_brand") or {}
    product_category = store_brand.get("product_category", "")
    # On a sourcing retry, trend_scraper may have relaxed the search term (e.g. dropped
    # "organic"/"certified" modifiers CJ doesn't carry data for) — validate new candidates
    # against what was actually searched, not the stricter original brief text.
    validate_category = state.get("search_category_used") or product_category
    already_created = set(str(pid) for pid in state.get("shopify_products_created", []))
    products = state.get("trending_products", [])

    # ── Phase 1: Curate existing store (delete off-niche products) ─────────────
    if product_category:
        deleted = await _curate_existing_products(product_category)
        if deleted:
            agent_log(f"Curated store: removed {deleted} off-niche products", "success")

    # ── Phase 2: Count remaining products — enforce max cap ────────────────────
    existing_after = await list_shopify_products()
    current_count = len(existing_after)
    slots_remaining = _MAX_STORE_PRODUCTS - current_count

    if slots_remaining <= 0:
        agent_log(f"Store is at max ({_MAX_STORE_PRODUCTS} products) — skipping publish", "info")
        return {
            "shopify_products_created": list(already_created),
            "messages": [HumanMessage(content=f"Store full ({current_count}/{_MAX_STORE_PRODUCTS}) — no new products added")],
        }

    agent_log(f"Store has {current_count}/{_MAX_STORE_PRODUCTS} products · {slots_remaining} slot(s) open", "info")

    # ── Phase 3: Filter candidates by niche fit ────────────────────────────────
    # Dedupe by image first — the LLM brands the same supplier item differently across
    # separate runs (already_created only tracks *this* run's batch), so two listings
    # for the literal same physical product can otherwise slip through with different names.
    existing_image_keys = {_image_key(p) for p in existing_after if _image_key(p)}
    existing_supplier_ids = await _existing_supplier_ids(store_id)
    candidates = [
        p for p in products
        if str(p.get("product_id", "")) not in already_created
        and str(p.get("product_id", "")) not in existing_supplier_ids  # already listed (reliable CJ-pid dedup)
        and _image_key(p) not in existing_image_keys
    ]
    skipped_dupes = len(products) - len(candidates) - sum(1 for p in products if str(p.get("product_id", "")) in already_created)
    if skipped_dupes > 0:
        agent_log(f"Skipped {skipped_dupes} candidate(s) — same image already live in store", "warning")
    top_by_margin = sorted(candidates, key=lambda p: p.get("margin_pct", 0), reverse=True)

    niche_validated: list[dict] = []
    rejected_titles: list[str] = []
    for product in top_by_margin:
        if len(niche_validated) >= slots_remaining:
            break
        supplier_title = product.get("title", "")
        if validate_category:
            fits = await _fits_niche(supplier_title, validate_category)
            if not fits:
                agent_log(f"⊘ Skip (wrong niche): '{supplier_title[:50]}'", "warning")
                rejected_titles.append(supplier_title)
                continue
        niche_validated.append(product)

    if not niche_validated:
        attempts = state.get("sourcing_attempts", 0) + 1
        if attempts < _MAX_SOURCING_ATTEMPTS:
            feedback = (
                f"Rejected as off-niche for category '{product_category}': "
                + "; ".join(rejected_titles[:5])
            )
            agent_log(
                f"No niche-matching candidates (attempt {attempts}/{_MAX_SOURCING_ATTEMPTS}) — "
                f"asking trend_scraper to retry with relaxed terms",
                "warning",
            )
            return {
                "shopify_products_created": list(already_created),
                "sourcing_attempts": attempts,
                "sourcing_feedback": feedback,
                "messages": [HumanMessage(content=f"No matches (attempt {attempts}) — retrying sourcing: {feedback}")],
            }
        # Final attempt: rather than dead-end (which stalled MONITOR/BOOST), fall
        # back to the best available candidates by margin. Listing related
        # products beats failing the whole run; the niche filter still applied on
        # earlier attempts.
        if top_by_margin:
            niche_validated = top_by_margin[:slots_remaining]
            agent_log(
                f"Niche filter rejected all after {attempts} attempts — listing top "
                f"{len(niche_validated)} by margin instead of failing",
                "warning",
            )
        else:
            agent_log("No candidates at all from supplier — giving up", "error")
            return {
                "shopify_products_created": list(already_created),
                "sourcing_attempts": attempts,
                "error": "no products available from supplier after multiple attempts",
                "messages": [HumanMessage(content="No supplier products to publish after retries")],
            }

    agent_log(f"{len(niche_validated)} products passed niche filter → publishing...", "action")

    # ── Phase 4: Brand, copy, publish ─────────────────────────────────────────
    created_ids: list[str] = list(already_created)
    last_error: str | None = None
    created_count = 0
    collection_cache: dict[str, str] = {}

    brief_collections = store_brand.get("collections", [])
    # Track titles already live in the store (+ ones we publish this pass) so the
    # branding LLM's tendency to reuse generic names ("Organic Cotton Baby Romper")
    # doesn't create visible duplicate listings.
    existing_titles = {p.get("title", "").lower() for p in existing_after}

    for product in niche_validated:
        supplier_title = product.get("title", "")
        # Classify into one of the brief's defined collections (e.g. Boys vs Girls)
        # so a single-product-type store can still split by audience/use-case.
        collection_name = await _pick_collection(supplier_title, brief_collections)
        if not collection_name:
            collection_name = product_category.title() if product_category else product.get("category", "General")

        # Brand the product
        agent_log(f"Branding: '{supplier_title[:50]}'...", "action")
        brand = await _brand_product(supplier_title, product_category or product.get("category", "General"))
        brand_title = brand.get("brand_title", supplier_title)
        hook = brand.get("hook", "")
        audience = brand.get("audience", "")

        if brand_title.lower() in existing_titles:
            # Disambiguate instead of skipping — append a short distinguishing detail
            # pulled from the supplier title (e.g. "Plaid", "Striped") so it's still readable.
            distinguisher = next((w for w in supplier_title.split() if w.lower() not in brand_title.lower()), "")
            brand_title = f"{distinguisher} {brand_title}".strip() if distinguisher else f"{brand_title} ({supplier_title[:20]})"
            agent_log(f"  (renamed to avoid duplicate title: '{brand_title}')", "info")
        existing_titles.add(brand_title.lower())
        agent_log(f"→ '{brand_title}'", "info")

        # Write premium copy — grounded in the supplier's real spec sheet (fabric,
        # fit, set contents) when available, instead of generic invented claims.
        agent_log(f"Writing copy for '{brand_title}'...", "action")
        real_specs = _extract_real_specs(product.get("description", ""))
        description = await _write_description(brand_title, collection_name, hook, audience, real_specs)

        # Get/create collection
        if collection_name not in collection_cache:
            coll_result = await create_collection(collection_name)
            if coll_result.get("collection_id"):
                collection_cache[collection_name] = coll_result["collection_id"]

        # Publish — psychological .90 pricing (e.g. 11.47 → 11.90), USD assumed
        # (store currency must be USD — Shopify has no API to change it, admin-only)
        price = _psychological_price(product.get("estimated_price_shopify_usd", 0.0) or 0.0)
        compare_price = _psychological_price(price * 1.35)

        # Per-(color, size) options from CJ — gives the storefront real Color +
        # Size selectors with per-variant Add to Cart. Each carries its CJ vid as
        # `sku` so the matching Shopify variant binds to the exact CJ SKU and the
        # right color/size gets fulfilled.
        supplier_variants = product.get("supplier_variants", [])
        product_variants = [
            {
                "color": sv.get("color", ""),
                "label": sv["size_label"],
                "sku": sv.get("vid", ""),
                "price": _psychological_price(sv["price_retail_usd"]),
                "compare_at_price": _psychological_price(sv["price_retail_usd"] * 1.35),
            }
            for sv in supplier_variants
        ]
        n_colors = len({sv.get("color", "") for sv in supplier_variants if sv.get("color")})
        n_sizes = len({sv["size_label"] for sv in supplier_variants})
        dims = ", ".join(
            part for part in (
                f"{n_colors} colors" if n_colors > 1 else "",
                f"{n_sizes} sizes" if n_sizes > 1 else "",
            ) if part
        )
        # Vision-vet the supplier images — keep only clean, sellable lifestyle shots
        # (no white-bg-only, no text/Chinese, no collages). Skip the product entirely
        # if none of its images are good enough — we never list an image-less product.
        good_images, vet_note = await _vet_images(
            product.get("images") or [product.get("image", "")], brand_title
        )
        if not good_images:
            agent_log(f"⊘ Skip (no sellable image): '{brand_title}' — {vet_note}", "warning")
            continue
        agent_log(f"🖼️ {brand_title}: {vet_note}", "info")

        agent_log(
            f"Publishing '{brand_title}' @ ${price:.2f}" + (f" ({dims})" if dims else "") + "...",
            "action",
        )

        result = await create_shopify_product(
            title=brand_title,
            description=description,
            price=price,
            compare_at_price=compare_price,
            images=good_images,
            variants=product_variants,
            video_url=product.get("video", ""),
        )

        if result.get("success"):
            pid = result["product"]["id"]
            created_ids.append(str(pid))
            created_count += 1
            agent_log(f"✓ Published '{brand_title}' (ID: {pid})", "success")

            if collection_name in collection_cache:
                await add_product_to_collection(pid, collection_cache[collection_name])

            # Stock every CJ-backed variant (the Color×Size selectors create one
            # per combo; no options = the single default variant) — without this,
            # inventory tracking defaults to 0 and "Add to Cart" doesn't work.
            # Skip auto-generated combos CJ doesn't actually carry (matched_sku
            # == "") so they show as sold out rather than orderable-but-unshippable.
            variant_nodes = result["product"].get("variants", {}).get("nodes", [])
            for vnode in variant_nodes:
                if "matched_sku" in vnode and not vnode["matched_sku"]:
                    continue
                inventory_item_id = vnode.get("inventoryItem", {}).get("id", "")
                if inventory_item_id:
                    await update_inventory(product_id=inventory_item_id, location_id="default", quantity=50)

            # Record the supplier cross-reference so price/stock monitoring and
            # fulfillment can look this product back up later.
            await _save_product_mapping(
                store_id=store_id,
                shopify_product_id=str(pid),
                supplier_product_id=str(product.get("product_id", "")),
                supplier_sku=str(product.get("cj_vid", "")),
                cost_price=product.get("price_supplier_usd", 0.0) or 0.0,
                retail_price=price,
            )
        else:
            last_error = result.get("error")
            agent_log(f"✗ Failed: '{brand_title}' — {last_error}", "error")

    total_now = current_count + created_count
    msg = f"Published {created_count} products · store now has {total_now}/{_MAX_STORE_PRODUCTS}"
    if last_error:
        msg += f" (last error: {last_error})"

    # Refresh navigation now that collections actually have products —
    # earlier runs may have skipped nav links to collections that were still empty.
    if created_count and brief_collections:
        nav_ok = await setup_navigation(store_brand.get("store_name", ""), brief_collections)
        if nav_ok:
            agent_log("✓ Navigation refreshed with live collection links", "success")

    # Self-heal existing listings that predate the color-variant pipeline: add a
    # Color selector + per-variant CJ SKUs to any mapped product still missing it,
    # so the customer can pick a color and CJ ships the exact one. Idempotent
    # (already-done products return cheaply) and bounded per cycle so we never fire
    # a burst of live mutations. Runs BEFORE the CJ connect below so freshly
    # backfilled variants get bound in the same cycle.
    try:
        from src.mcp_tools.variant_backfill import backfill_product_color
        from src.db.engine import get_session
        from src.db.models import ProductMapping
        from sqlalchemy import select as _select
        async with get_session() as _s:
            _rows = await _s.execute(
                _select(ProductMapping.shopify_product_id).where(ProductMapping.store_id == store_id)
            )
            _pids = [r[0] for r in _rows.all()]
        healed = 0
        for _pid in _pids:
            if healed >= _MAX_BACKFILL_PER_CYCLE:
                break
            try:
                r = await backfill_product_color(_pid, store_id, run_cj_connect=False)
            except Exception as exc:
                agent_log(f"color backfill error for {_pid}: {exc}", "warning")
                continue
            if r.get("status") == "backfilled":
                healed += 1
                agent_log(
                    f"🎨 added Color selector to '{r.get('title','')}' "
                    f"({len(r.get('colors', []))} colors, {r.get('variants_created', 0)} variants added)",
                    "success",
                )
        if healed:
            agent_log(f"Color self-heal: {healed} existing product(s) gained a Color selector this cycle", "success")
    except Exception as exc:
        agent_log(f"color self-heal skipped (non-fatal): {exc}", "warning")

    # Connect every mapped product to its CJ product so the CJ app auto-fulfills
    # paid orders (places the CJ order + pushes tracking). Idempotent and
    # self-resolving (finds the store's CJ shop) — safe to run every cycle. CJ
    # only exposes a product for binding once its app has synced it from Shopify,
    # so freshly-published items may land in skipped_no_variant now and connect on
    # a later cycle once CJ has synced them.
    try:
        from src.mcp_tools.cj_connect import connect_store_products
        cj = await connect_store_products(store_id)
        if cj.get("error"):
            agent_log(f"CJ connect skipped: {cj['error']}", "warning")
        else:
            agent_log(
                f"CJ auto-fulfill links: {len(cj.get('connected', []))} new, "
                f"{len(cj.get('already_connected', []))} already, "
                f"{len(cj.get('needs_review', []))} need manual review, "
                f"{len(cj.get('skipped_no_variant', []))} awaiting CJ sync",
                "success" if cj.get("connected") else "info",
            )
    except Exception as exc:  # never let fulfillment wiring break the publish flow
        agent_log(f"CJ connect error (non-fatal): {exc}", "warning")

    return {
        "shopify_products_created": created_ids,
        "sourcing_attempts": 0,  # reset for the next monitoring cycle
        "error": None if created_count else (last_error or "no eligible products"),
        "messages": [HumanMessage(content=msg)],
    }
