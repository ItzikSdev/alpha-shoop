"""Store Setup Agent — brands the Shopify store before product listings begin."""
from __future__ import annotations
import json
import logging
import re
from langchain_core.messages import HumanMessage, SystemMessage
from src.agents.state import AgentState
from src.llm import get_llm
from src.mcp_tools.shopify import _shopify_gql, _shopify_rest, create_collection, create_welcome_discount
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

# Third-party Shopify apps require a human to click "Install" in the App
# Store (OAuth + billing consent) — there's no Admin API that lets an agent
# silently install another vendor's app, by deliberate Shopify design. So this
# is a recommendation surfaced in the run summary, not something automated.
_RECOMMENDED_APPS = """\
Recommended apps to install manually (not automatable — each requires your \
own App Store install + OAuth consent):
- Reviews: Judge.me (unlimited reviews, free tier, SEO rich snippets)
- Email/lifecycle: Klaviyo (welcome flows, abandoned cart, post-purchase)
- Post-purchase upsell: ReConvert
- Profit tracking once running ads: Lifetimely or Triple Whale
- Page speed/SEO: TinyIMG or Avada
Already done natively (no app needed): storewide welcome discount code, \
theme/design, navigation, collections, pages."""

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

_GQL_SET_SHOP_POLICY = """
mutation setPolicy($policy: ShopPolicyInput!) {
  shopPolicyUpdate(shopPolicy: $policy) {
    shopPolicy { type body }
    userErrors { field message }
  }
}
"""


def _load_store_template(store_slug: str = "timeofbaby") -> str:
    """The store folder IS the template + source of truth (see the store's CLAUDE.md).
    Pull the README rules + CLAUDE build guide + OWNER + the existing brand identity
    from style/site.json so Devon BUILDS TO THE TEMPLATE instead of inventing a new
    brand every run. Empty string if there's no template on disk yet."""
    blocks: list[str] = []
    try:
        from src.mcp_tools.design_files import read_store_docs
        docs = read_store_docs(store_slug)
        if docs.get("claude"):
            blocks.append("--- CLAUDE.md (how to build this store) ---\n" + docs["claude"][:2200])
        if docs.get("readme"):
            blocks.append("--- readme/README.md (source-of-truth rules) ---\n" + docs["readme"][:1600])
        if docs.get("owner"):
            blocks.append("--- readme/OWNER.md (who the owner is) ---\n" + docs["owner"][:1000])
    except Exception:
        pass
    # The existing brand identity already encoded in the design spec — name, colors,
    # announcement bar — so the brief adopts it rather than reinventing it.
    try:
        from src.mcp_tools.shopify_design import load_site_json
        site = load_site_json(store_slug)
        if site:
            ident = {
                "store_name": site.get("brand") or site.get("store_name"),
                "design_tokens.colors": (site.get("design_tokens") or {}).get("colors"),
                "announcement_marquee": next(
                    (s.get("settings") for s in site.get("sections", [])
                     if "announcement" in str(s.get("id", "")).lower()), None),
            }
            blocks.append("--- style/site.json — the EXISTING brand identity (adopt it) ---\n"
                          + json.dumps(ident, ensure_ascii=False)[:1200])
    except Exception:
        pass
    return "\n\n".join(blocks)


async def _write_brand_brief(task: str, template: str = "") -> dict:
    llm = get_llm("ecommerce", temperature=0.7)
    if template:
        system = (
            _BRAND_BRIEF_SYSTEM
            + "\n\n=== STORE TEMPLATE — THIS IS THE SOURCE OF TRUTH ===\n"
            "A template folder for this store exists below. You MUST build the brief to "
            "MATCH it — adopt its exact brand name, colors, niche/product_category, voice, "
            "and announcement-bar trust signals. Do NOT invent a new brand or a different "
            "look. Only fill in any field the template leaves unspecified, and keep it "
            "consistent with the template.\n\n" + template
        )
    else:
        system = _BRAND_BRIEF_SYSTEM
    response = await llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=f"Store task: {task}"),
    ])
    try:
        return _parse_json(str(response.content))
    except (json.JSONDecodeError, ValueError):
        return {}


async def _page_exists(title: str) -> bool:
    """Confirmed real bug: store_setup re-runs (retries, [REBUILD]) called
    _create_page with no existence check, leaving 3 duplicate "About Us" /
    "Shipping & Returns" pages live on a real store. Check first."""
    try:
        existing = await _shopify_rest("GET", "pages.json")
        return any(p.get("title") == title for p in existing.get("pages", []))
    except Exception:
        return False


async def _create_page(title: str, body_html: str) -> bool:
    if await _page_exists(title):
        return True
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


async def _set_shop_policy(policy_type: str, body: str) -> bool:
    """Write to Shopify's native legal Policy fields (Settings → Policies) —
    separate from a regular Page. Confirmed real gap: the "Shipping & Returns"
    Page below is a normal content page, but checkout footer links and the
    Storefront MCP server's search_shop_policies_and_faqs tool both read from
    these structured shop.shopPolicies fields instead, so without this call
    AI shopping agents only ever see Shopify's generic shipping-zone default,
    never the brand's actual policy text."""
    if not body:
        return False
    try:
        data = await _shopify_gql(_GQL_SET_SHOP_POLICY, {"policy": {"type": policy_type, "body": f"<p>{body}</p>"}})
        errors = data.get("shopPolicyUpdate", {}).get("userErrors", [])
        if errors:
            logger.warning("shopPolicyUpdate failed for %s: %s", policy_type, errors)
        return not errors
    except Exception as exc:
        logger.warning("shopPolicyUpdate failed for %s: %s", policy_type, exc)
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

    # READ the store template/folder FIRST (the store's CLAUDE.md rule: read before
    # you act, build to match the template) so Devon builds THIS store, not a new one.
    template = _load_store_template("timeofbaby")
    if template:
        agent_log("Read the store template (README + CLAUDE + site.json) — building to match it", "info")
    agent_log("Generating brand brief...", "info")
    brief = await _write_brand_brief(state.get("task", ""), template)
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

        # Also write to Shopify's native Policy fields (checkout footer links +
        # Storefront MCP's FAQ tool read these, not the page above — see
        # _set_shop_policy's docstring).
        if await _set_shop_policy("SHIPPING_POLICY", shipping):
            actions_done.append("Native shipping policy set")
        if await _set_shop_policy("REFUND_POLICY", returns):
            actions_done.append("Native refund policy set")

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

    # 5.5 Render the store TEMPLATE's homepage from style/site.json (the JSON-driven
    #     marquee/announcement bar + hero + sections). full_store_setup above targets
    #     stock Dawn/Horizon section types, which this JSON-driven store doesn't have —
    #     so the real announcement bar lives in site.json and is applied here. Best-
    #     effort: never block the build if there's no site.json / theme yet.
    if template:
        try:
            from src.mcp_tools.shopify_design import apply_site_design
            res = await apply_site_design("timeofbaby")
            if res.get("ok"):
                actions_done.append("Template homepage applied from site.json (announcement marquee + sections)")
                agent_log("✓ Template homepage rendered from site.json", "success")
            else:
                agent_log(f"site.json homepage apply skipped: {res.get('error')}", "warning")
        except Exception as exc:
            logger.warning("apply_site_design failed: %s", exc)

    # 6. Welcome discount — a real AOV booster achievable natively via the
    # Discounts API, no third-party app (e.g. ReConvert) needed for this kind
    # of offer specifically.
    agent_log("Creating storewide welcome discount code...", "action")
    discount_result = await create_welcome_discount("WELCOME10", 0.10)
    if discount_result.get("success"):
        if discount_result.get("already_existed"):
            agent_log("✓ Welcome discount WELCOME10 already exists — reusing it", "success")
        else:
            actions_done.append("Welcome discount code WELCOME10 (10% off, storewide)")
            agent_log("✓ Discount code WELCOME10 created", "success")
    else:
        agent_log(f"✗ Discount code creation failed: {discount_result.get('error')}", "warning")

    summary = (
        f"Store brand: {store_name} — \"{brief.get('tagline', '')}\"\n"
        f"Differentiator: {brief.get('differentiator', '')}\n"
        f"Niche: {brief.get('niche', '')}\n"
        f"Done: {', '.join(actions_done) or 'none'}\n\n"
        f"{_RECOMMENDED_APPS}"
    )

    return {
        "store_brand": brief,
        "messages": [HumanMessage(content=summary)],
    }
