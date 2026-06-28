"""
Whole-store scan → one big JSON of the live store's real state, with issue flags.

Grace/Linus call this to get the FULL picture (products, collections, theme,
navigation, shipping) in one structured object, so they can see exactly what's
wrong and decide what to fix — instead of guessing. Read-only.
"""
from __future__ import annotations

import httpx

from src.config import get_settings


def _hdr():
    s = get_settings()
    return f"https://{s.shopify_store_domain}/admin/api/2024-07", {"X-Shopify-Access-Token": s.shopify_access_token}


async def scan_store() -> dict:
    """Return a comprehensive JSON snapshot of the store + a list of detected issues."""
    base, hdr = _hdr()
    gql = f"{base}/graphql.json"
    out: dict = {"products": [], "collections": [], "navigation": {}, "theme": {}, "issues": []}
    issues = out["issues"]
    async with httpx.AsyncClient(timeout=30, headers=hdr) as c:
        # Shop
        shop = (await c.post(gql, json={"query": "{ shop{ name myshopifyDomain currencyCode } }"})).json().get("data", {}).get("shop", {})
        out["shop"] = shop

        # Products (active) with issue flags
        prods = (await c.get(f"{base}/products.json", params={"limit": 100,
                 "fields": "id,title,handle,status,variants,images,body_html,product_type"})).json().get("products", [])
        baby_words = ("baby", "toddler", "newborn", "infant", "romper", "onesie", "bodysuit", "kids", "boy", "girl")
        for p in prods:
            body = p.get("body_html") or ""
            variants = p.get("variants", [])
            has_size = any(v.get("option1") and v.get("option1") not in ("Default Title", "") for v in variants)
            entry = {
                "id": p["id"], "title": p["title"], "status": p["status"],
                "variants": len(variants), "has_size_or_color": has_size,
                "images": len(p.get("images", [])),
                "generic_text": "Satisfaction guaranteed" in body,
                "real_cj_text": ("Fabric" in body or "crafted for little" in body),
            }
            out["products"].append(entry)
            # per-product issues
            t = p["title"].lower()
            if not any(w in t for w in baby_words) and p["status"] == "active":
                issues.append(f"product '{p['title']}' may be off-niche (not baby-related)")
            if entry["images"] < 2 and p["status"] == "active":
                issues.append(f"product '{p['title']}' has <2 images")
            if not has_size and p["status"] == "active":
                issues.append(f"product '{p['title']}' has no size/color variants")
            if entry["generic_text"]:
                issues.append(f"product '{p['title']}' still has generic template text")

        active = [p for p in out["products"] if p["status"] == "active"]
        out["product_count"] = {"total": len(prods), "active": len(active)}
        if len(active) < 50:
            issues.append(f"only {len(active)} active products (target ~50)")

        # Collections
        for kind in ("custom_collections", "smart_collections"):
            cc = (await c.get(f"{base}/{kind}.json", params={"limit": 50, "fields": "handle,title"})).json().get(kind, [])
            out["collections"] += [{"handle": x["handle"], "title": x["title"]} for x in cc]

        # Navigation menus
        menus = (await c.post(gql, json={"query": "{ menus(first:5){ nodes{ handle items{ title url } } } }"})).json().get("data", {}).get("menus", {}).get("nodes", [])
        out["navigation"] = {m["handle"]: [i["title"] for i in m["items"]] for m in menus}
        for m in menus:
            if m["handle"] == "main-menu" and any("portrait" in i["title"].lower() or "pet" in i["title"].lower() for i in m["items"]):
                issues.append("main menu still has off-niche (pet/portrait) links")

        # Theme: homepage + product templates
        themes = (await c.get(f"{base}/themes.json", params={"fields": "id,role,name"})).json().get("themes", [])
        main = next((t for t in themes if t.get("role") == "main"), None)
        if main:
            out["theme"]["name"] = main["name"]; out["theme"]["id"] = main["id"]
            for tpl in ("templates/index.json", "templates/product.json"):
                a = (await c.get(f"{base}/themes/{main['id']}/assets.json", params={"asset[key]": tpl})).json().get("asset", {}).get("value", "")
                out["theme"][tpl] = "timeofbaby" in a or "tobp" in a or "tob" in a

    return out
