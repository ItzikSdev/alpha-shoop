"""E-commerce Manager — creates branded Shopify products from scraper results."""
from __future__ import annotations
import json
import logging
import math
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

INPUT: brand_title, category, hook (emotional opener), audience

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


async def _write_description(brand_title: str, category: str, hook: str, audience: str) -> str:
    """Write premium product copy at TANAOR-level quality."""
    llm = get_llm("ecommerce", temperature=0.7)
    prompt = (
        f"brand_title: {brand_title}\n"
        f"category: {category}\n"
        f"hook: {hook}\n"
        f"audience: {audience}"
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


_MAX_STORE_PRODUCTS = 8  # Hard cap — TANAOR quality means curated, not crowded
_MAX_SOURCING_ATTEMPTS = 3  # retry trend_scraper with relaxed terms this many times before giving up

_FIT_SYSTEM = """\
You are a strict product curator for a focused niche store.
Given the store's product category and a supplier product title, answer ONE word: YES or NO.
YES = this product is exactly a {category} and belongs in this store.
NO = this product is something different (different product type, accessory, or off-niche).

Be strict. If the store sells women's silver rings, a necklace = NO. A gold men's ring = YES.
If the store sells soy candles, a wax melt = YES. A diffuser = NO.
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
    candidates = [
        p for p in products
        if str(p.get("product_id", "")) not in already_created
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
        agent_log(f"No niche-matching candidates after {attempts} attempts — giving up", "error")
        return {
            "shopify_products_created": list(already_created),
            "sourcing_attempts": attempts,
            "error": "no niche-matching products found after multiple sourcing attempts",
            "messages": [HumanMessage(content="No niche-matching products to publish after retries")],
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

        # Write premium copy
        agent_log(f"Writing copy for '{brand_title}'...", "action")
        description = await _write_description(brand_title, collection_name, hook, audience)

        # Get/create collection
        if collection_name not in collection_cache:
            coll_result = await create_collection(collection_name)
            if coll_result.get("collection_id"):
                collection_cache[collection_name] = coll_result["collection_id"]

        # Publish — psychological .90 pricing (e.g. 11.47 → 11.90), USD assumed
        # (store currency must be USD — Shopify has no API to change it, admin-only)
        price = _psychological_price(product.get("estimated_price_shopify_usd", 0.0) or 0.0)
        compare_price = _psychological_price(price * 1.35)
        agent_log(f"Publishing '{brand_title}' @ ${price:.2f}...", "action")

        result = await create_shopify_product(
            title=brand_title,
            description=description,
            price=price,
            compare_at_price=compare_price,
            images=product.get("images") or [product.get("image", "")],
            variants=[],
        )

        if result.get("success"):
            pid = result["product"]["id"]
            created_ids.append(str(pid))
            created_count += 1
            agent_log(f"✓ Published '{brand_title}' (ID: {pid})", "success")

            if collection_name in collection_cache:
                await add_product_to_collection(pid, collection_cache[collection_name])

            inventory_item_id = (
                result["product"]
                .get("variants", {})
                .get("nodes", [{}])[0]
                .get("inventoryItem", {})
                .get("id", "")
            ) if result["product"].get("variants") else ""
            if inventory_item_id:
                await update_inventory(product_id=inventory_item_id, location_id="default", quantity=50)
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

    return {
        "shopify_products_created": created_ids,
        "sourcing_attempts": 0,  # reset for the next monitoring cycle
        "error": None if created_count else (last_error or "no eligible products"),
        "messages": [HumanMessage(content=msg)],
    }
