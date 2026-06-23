"""Store Setup Agent — brands the Shopify store before product listings begin."""
from __future__ import annotations
import json
import logging
import re
from langchain_core.messages import HumanMessage, SystemMessage
from src.agents.state import AgentState
from src.llm import get_llm
from src.mcp_tools.shopify import _shopify_gql, _shopify_rest, create_collection
from src.mcp_tools.shopify_theme import full_store_setup, setup_navigation
from src.mcp_tools.theme_installer import install_free_theme
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

CRITICAL RULE ON NICHE FOCUS:
The store MUST sell ONE and ONLY ONE type of product. Not a general gift shop, not a multi-category store.
Think Tanaor (only jewelry), Beardbrand (only beard products), MVMT (only watches).
The "product_category" field is THE product type — every single item in the store must be this exact thing.

Output ONLY a JSON object:
{
  "store_name": "2-3 word memorable brand name. Avoid: Shop, Store, Best, Hub. Examples: Tanaor, Beardbrand, MVMT, Glossier",
  "tagline": "Under 7 words. Captures the brand promise and differentiator.",
  "niche": "One sentence: exactly who this serves and what concrete problem it solves.",
  "product_category": "The ONE AND ONLY product type this store sells. Must be a specific, searchable CJ Dropshipping keyword. Examples: 'silver women rings', 'leather minimalist wallet', 'scented soy candles', 'yoga mat'. This is the strict product filter — nothing outside this category will ever be listed.",
  "differentiator": "ONE specific, tangible, verifiable claim that no generic dropshipping store can make. Must be something a customer can FEEL or SEE in the product.",
  "tone": "One word: warm / bold / minimal / playful / trustworthy",
  "about_us": "3 short paragraphs. Para 1: why we exist (the founder story). Para 2: what makes us different (the differentiator in plain language). Para 3: the promise. First-person plural. Plain text, no HTML.",
  "announcement_bar": "One line, pipe-separated trust signals. Include: free shipping threshold, return policy, differentiator in 4 words. Example: 'Free Shipping on All Orders | 30-Day Returns | Hand-Finished in Israel'",
  "shipping_policy": "2 sentences. Specific timeframe and carrier.",
  "return_policy": "2 sentences. Customer-friendly. Specific timeframe.",
  "collections": ["3-4 collection names within the same product category. Split by the axis that matters most for this niche: jewelry → 'Rings', 'Necklaces', 'Bracelets', 'Gift Sets'; CLOTHING (baby/kids/adult apparel) → split by audience first, e.g. 'Boys', 'Girls', 'Gift Sets' (never mix genders in one clothing collection); candles → 'Scented', 'Unscented', 'Gift Sets'."]
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

_GQL_SHOP_UPDATE = ""  # shopUpdate removed from Shopify API — store name changed via admin only


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
    # Try GQL first (needs write_content scope)
    try:
        data = await _shopify_gql(
            _GQL_CREATE_PAGE,
            {"page": {"title": title, "body": body_html, "isPublished": True}},
        )
        errors = data.get("pageCreate", {}).get("userErrors", [])
        if not errors:
            return True
        if any("ACCESS_DENIED" in str(e) for e in errors):
            raise PermissionError("write_content scope missing")
    except PermissionError:
        pass
    except Exception as exc:
        logger.warning("GQL pageCreate failed for %s: %s", title, exc)
        return False
    # REST fallback (also needs write_content, but different error path)
    try:
        result = await _shopify_rest("POST", "pages.json", {
            "page": {"title": title, "body_html": body_html, "published": True}
        })
        return bool(result.get("page", {}).get("id"))
    except Exception as exc:
        logger.warning("REST pageCreate failed for %s: %s — add write_content scope to Custom App", title, exc)
        return False


async def _update_store_name(name: str) -> bool:
    """Store name is managed via Shopify admin — not available via API."""
    logger.info("Store name '%s' set in brand brief (must be applied manually in Shopify admin → Settings → General)", name)
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

    # 4. Install free Shopify theme that matches the store niche
    store_niche = brief.get("niche", "") or brief.get("product_category", "")
    store_slug = store_name.lower().replace(" ", "_")[:30] if store_name else "store"
    agent_log(f"Selecting and installing free Shopify theme for '{store_niche}'...", "action")
    theme_result = await install_free_theme(niche=store_niche, store_name=store_slug)
    if theme_result.get("success"):
        actions_done.append(f"Theme installed: {theme_result['display_name']} (saved to stores/{store_slug}/theme/)")
        brief["installed_theme"] = theme_result["theme_key"]
        agent_log(f"✓ Theme '{theme_result['display_name']}' active", "success")
    else:
        agent_log(f"Theme install skipped — keeping existing theme", "warning")

    # 4.5 Create all brief collections upfront (empty) so navigation can link to
    #     real, existing collections instead of producing broken 404 links.
    #     ecommerce_manager fills these with products later.
    collection_names = brief.get("collections", [])
    if collection_names:
        agent_log(f"Creating {len(collection_names)} collections: {', '.join(collection_names)}...", "action")
        created_collections = 0
        for coll_name in collection_names:
            result = await create_collection(coll_name)
            if result.get("collection_id"):
                created_collections += 1
        agent_log(f"✓ {created_collections}/{len(collection_names)} collections ready", "success")
        actions_done.append(f"{created_collections} collections created")

    # 5. Full theme setup — colors, announcement bar, homepage, navigation
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
