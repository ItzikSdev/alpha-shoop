"""Store Setup Agent — brands the Shopify store before product listings begin."""
from __future__ import annotations
import json
import logging
import re
from langchain_core.messages import HumanMessage, SystemMessage
from src.agents.state import AgentState
from src.llm import get_llm
from src.mcp_tools.shopify import _shopify_gql, _shopify_rest
from src.mcp_tools.shopify_theme import full_store_setup, setup_navigation
from src.tracing import agent_log
from src.tracing.context import current_node


def _parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```\s*$', '', text)
    return json.loads(text.strip())


logger = logging.getLogger(__name__)

_BRAND_BRIEF_SYSTEM = """\
You are a senior brand strategist who has built stores like Tanaor, MVMT, and Glossier.
Given an e-commerce task, create a complete brand brief for a Shopify store.

The single most important element is the DIFFERENTIATOR — the one specific, tangible thing
that makes every product in this store different from anything else on the market.
Tanaor's differentiator: "Every piece has all 929 Bible chapters engraved using nano-technology."
MVMT's differentiator: "Swiss movement watches for a fraction of the designer price."
Yours must be just as specific and verifiable — NOT vague ("high quality", "unique design").

Output ONLY a JSON object:
{
  "store_name": "2-3 word memorable brand name. Avoid: Shop, Store, Best, Hub. Examples: Tanaor, Beardbrand, MVMT, Glossier",
  "tagline": "Under 7 words. Captures the brand promise and differentiator.",
  "niche": "One sentence: exactly who this serves and what concrete problem it solves.",
  "differentiator": "ONE specific, tangible, verifiable claim that no generic dropshipping store can make. Must be something a customer can FEEL or SEE in the product. Examples: 'Each piece is hand-finished with a micro-engraving of the buyer's initials', 'Every item ships in FSC-certified packaging with a planted tree per order', 'All products are tested by 3 independent labs for safety before listing'.",
  "tone": "One word: warm / bold / minimal / playful / trustworthy",
  "about_us": "3 short paragraphs. Para 1: why we exist (the founder story). Para 2: what makes us different (the differentiator in plain language). Para 3: the promise. First-person plural. Plain text, no HTML.",
  "announcement_bar": "One line, pipe-separated trust signals for the top of the store. Include: free shipping threshold, return policy, and the differentiator summarized in 4 words. Example: 'Free Shipping on All Orders | 30-Day Returns | Hand-Finished in Israel'",
  "shipping_policy": "2 sentences. Specific timeframe and carrier.",
  "return_policy": "2 sentences. Customer-friendly. Specific timeframe.",
  "collections": ["3-5 collection names that create a logical, browsable catalog. Named by outcome or style, not by product type. Example: 'Everyday Essentials', 'Gift Ideas Under $50', 'Best Sellers'"]
}

Output ONLY valid JSON.
"""

_GQL_CREATE_PAGE = """
mutation pageCreate($page: PageCreateInput!) {
  pageCreate(page: $page) {
    page { id title handle }
    userErrors { field message }
  }
}
"""

_GQL_SHOP_UPDATE = """
mutation shopUpdate($input: ShopUpdateInput!) {
  shopUpdate(input: $input) {
    shop { name }
    userErrors { field message }
  }
}
"""


async def _write_brand_brief(task: str) -> dict:
    llm = get_llm("ecommerce", temperature=0.7)
    response = await llm.ainvoke([
        SystemMessage(content=_BRAND_BRIEF_SYSTEM),
        HumanMessage(content=f"Store task: {task}"),
    ])
    try:
        return _parse_json(str(response.content))
    except (json.JSONDecodeError, ValueError):
        return {}


async def _create_page(title: str, body_html: str) -> bool:
    try:
        data = await _shopify_gql(
            _GQL_CREATE_PAGE,
            {"page": {"title": title, "bodyHtml": body_html, "published": True}},
        )
        errors = data.get("pageCreate", {}).get("userErrors", [])
        return not errors
    except Exception as exc:
        logger.warning("Could not create page %s: %s", title, exc)
        return False


async def _update_store_name(name: str) -> bool:
    """Update the Shopify store's display name."""
    try:
        # Try GraphQL first
        data = await _shopify_gql(_GQL_SHOP_UPDATE, {"input": {"name": name}})
        errors = data.get("shopUpdate", {}).get("userErrors", [])
        if not errors:
            return True
    except Exception:
        pass
    # Fallback: REST API
    try:
        await _shopify_rest("PUT", "shop.json", {"shop": {"name": name}})
        return True
    except Exception as exc:
        logger.warning("Could not update store name: %s", exc)
        return False


async def _create_navigation_menu(brand_name: str, collections: list[str]) -> bool:
    """
    Create a main navigation menu linking to the store's collections.
    Uses Shopify REST API since navigation isn't easily accessible via GQL without theme scope.
    """
    try:
        # First get existing menus
        menus_data = await _shopify_rest("GET", "menus.json")
        menus = menus_data.get("menus", [])

        # Find or target the main menu
        main_menu = next((m for m in menus if m.get("handle") in ("main-menu", "frontend")), None)

        # Build menu items for each collection
        # Collections will be searched by handle (lowercase, hyphenated)
        items = []
        for coll_name in collections:
            handle = coll_name.lower().replace(" ", "-").replace("&", "and")
            items.append({
                "title": coll_name,
                "type": "collection",
                "url": f"/collections/{handle}",
            })

        # Add standard pages
        items += [
            {"title": "About Us", "type": "page", "url": "/pages/about-us"},
            {"title": "Shipping & Returns", "type": "page", "url": "/pages/shipping-returns"},
        ]

        if main_menu:
            # Update existing menu
            await _shopify_rest("PUT", f"menus/{main_menu['id']}.json", {
                "menu": {"id": main_menu["id"], "items": items}
            })
        else:
            # Create new main menu
            await _shopify_rest("POST", "menus.json", {
                "menu": {"title": "Main Menu", "handle": "main-menu", "items": items}
            })
        return True
    except Exception as exc:
        logger.warning("Could not create navigation menu: %s", exc)
        return False


async def store_setup_node(state: AgentState) -> dict:
    """
    LangGraph node: one-time store branding step.
    - Generates brand brief (name, tagline, about, policies)
    - Updates the Shopify store name
    - Creates About Us and Policy pages
    - Creates navigation menu linking to collections
    - Stores brand context in state for downstream agents
    """
    current_node.set("store_setup")

    if state.get("store_brand"):
        return {}

    agent_log("Generating brand brief...", "info")
    brief = await _write_brand_brief(state.get("task", ""))
    if not brief:
        agent_log("Brand brief generation failed", "error")
        return {"messages": [HumanMessage(content="Store setup skipped (brief generation failed)")]}

    store_name = brief.get("store_name", "")
    agent_log(f"Brand: {store_name} — \"{brief.get('tagline', '')}\"", "success")
    agent_log(f"Differentiator: {brief.get('differentiator', '')[:80]}", "info")

    actions_done = []

    # 1. Update store name
    if store_name:
        agent_log(f"Updating store name to '{store_name}'...", "action")
        if await _update_store_name(store_name):
            actions_done.append(f"Store renamed to '{store_name}'")

    # 2. About Us page
    about_html = "".join(
        f"<p>{p}</p>" for p in brief.get("about_us", "").split("\n\n") if p.strip()
    )
    if about_html:
        ok = await _create_page("About Us", about_html)
        if ok:
            actions_done.append("About Us page")

    # 3. Shipping & Returns page
    shipping = brief.get("shipping_policy", "")
    returns = brief.get("return_policy", "")
    if shipping or returns:
        policies_html = (
            "<h2>Shipping</h2>"
            f"<p>{shipping}</p>"
            "<h2>Returns & Exchanges</h2>"
            f"<p>{returns}</p>"
        )
        ok = await _create_page("Shipping & Returns", policies_html)
        if ok:
            actions_done.append("Shipping & Returns page")

    # 4. Full theme setup — colors, announcement bar, homepage, navigation
    agent_log("Running full theme setup (colors → announcement → homepage → nav)...", "action")
    theme_results = await full_store_setup(brief)
    for key, label in [
        ("colors", "Brand colors applied"),
        ("announcement", "Announcement bar set"),
        ("homepage", "Homepage rebuilt (hero → products → story → collections)"),
        ("navigation", f"Navigation menu ({len(brief.get('collections', []))} collections)"),
    ]:
        ok = theme_results.get(key)
        if ok:
            actions_done.append(label)
            agent_log(f"✓ {label}", "success")
        else:
            agent_log(f"✗ {label} failed", "warning")

    summary = (
        f"Store brand: {store_name} — \"{brief.get('tagline', '')}\"\n"
        f"Differentiator: {brief.get('differentiator', '')}\n"
        f"Niche: {brief.get('niche', '')}\n"
        f"Done: {', '.join(actions_done) or 'none'}"
    )

    return {
        "store_brand": brief,
        "messages": [HumanMessage(content=summary)],
    }
