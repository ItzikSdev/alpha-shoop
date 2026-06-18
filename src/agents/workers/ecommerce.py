"""E-commerce Manager — creates branded Shopify products from scraper results."""
from __future__ import annotations
import json
import logging
import re
from langchain_core.messages import HumanMessage, SystemMessage
from src.agents.state import AgentState
from src.llm import get_llm
from src.mcp_tools.shopify import (
    create_shopify_product,
    update_inventory,
    create_collection,
    add_product_to_collection,
)
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


async def ecommerce_node(state: AgentState) -> dict:
    """LangGraph node: brands and publishes top-margin products to Shopify."""
    current_node.set("ecommerce_manager")

    already_created = set(state.get("shopify_products_created", []))
    products = state.get("trending_products", [])
    candidates = [p for p in products if p.get("product_id") not in already_created]
    top = sorted(candidates, key=lambda p: p.get("margin_pct", 0), reverse=True)[:5]

    created_ids: list[str] = list(already_created)
    last_error: str | None = None
    created_count = 0

    # Cache collection IDs to avoid creating duplicates within one run
    collection_cache: dict[str, str] = {}

    for product in top:
        supplier_title = product.get("title", "")
        category = product.get("category", "General")

        # Step 1: Generate brand identity for this product
        brand = await _brand_product(supplier_title, category)
        brand_title = brand.get("brand_title", supplier_title)
        collection_name = brand.get("collection", category)
        hook = brand.get("hook", "")
        audience = brand.get("audience", "")

        # Step 2: Write premium copy
        description = await _write_description(brand_title, category, hook, audience)

        # Step 3: Get or create the collection
        if collection_name not in collection_cache:
            coll_result = await create_collection(collection_name)
            if coll_result.get("collection_id"):
                collection_cache[collection_name] = coll_result["collection_id"]

        # Step 4: Create the Shopify product
        price = product.get("estimated_price_shopify_usd", 0.0) or 0.0
        compare_price = round(price * 1.35, 2)  # 35% markup as "original" price

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

            # Step 5: Assign to collection
            if collection_name in collection_cache:
                await add_product_to_collection(pid, collection_cache[collection_name])

            # Step 6: Update inventory
            inventory_item_id = (
                result["product"]
                .get("variants", {})
                .get("nodes", [{}])[0]
                .get("inventoryItem", {})
                .get("id", "")
            ) if result["product"].get("variants") else ""

            if inventory_item_id:
                await update_inventory(
                    product_id=inventory_item_id,
                    location_id="default",
                    quantity=50,
                )
        else:
            last_error = result.get("error")
            logger.warning("Failed to create product %s: %s", brand_title, last_error)

    msg = f"Created {created_count} branded products"
    if last_error:
        msg += f" (last error: {last_error})"

    return {
        "shopify_products_created": created_ids,
        "error": None if created_count else (last_error or "no eligible products"),
        "messages": [HumanMessage(content=msg)],
    }
