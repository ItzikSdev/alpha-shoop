"""MCP Tool Group 1: Sourcing — CJ Dropshipping & AliExpress."""
from __future__ import annotations
import asyncio
import json
import logging
import re
import httpx
from src.config import get_settings

logger = logging.getLogger(__name__)

_BASE = "https://developers.cjdropshipping.com/api2.0/v1"

# CJ enforces a hard QPS limit of 1 request/second per token. Firing detail
# lookups in parallel (asyncio.gather) trips "Too Many Requests" and silently
# drops most candidates. We serialise CJ calls behind a lock + min-interval and
# retry on the QPS error so searches return a full batch instead of 1 survivor.
_CJ_MIN_INTERVAL = 1.15  # seconds between CJ calls (slightly above their 1/sec)
_CJ_LOCK = asyncio.Lock()
_CJ_LAST_CALL = 0.0


class CJQuotaExceeded(Exception):
    """CJ's DAILY request quota (not the 1-QPS rate limit) is exhausted. Retrying
    does not help — it only resets after CJ's daily window rolls over. Callers
    must surface this as a hard error, not silently treat it as zero results,
    or the director will loop the same failing query indefinitely."""


async def _cj_get(client: httpx.AsyncClient, path: str, params: dict, token: str, retries: int = 4) -> dict:
    """Rate-limited CJ GET that retries on the 1-QPS 'Too Many Requests' error."""
    global _CJ_LAST_CALL
    import time
    for _ in range(retries):
        async with _CJ_LOCK:
            wait = _CJ_MIN_INTERVAL - (time.monotonic() - _CJ_LAST_CALL)
            if wait > 0:
                await asyncio.sleep(wait)
            resp = await client.get(f"{_BASE}/{path}", params=params, headers={"CJ-Access-Token": token})
            _CJ_LAST_CALL = time.monotonic()
        # CJ sends the daily-quota error as HTTP 429 (not 200), with the real
        # explanation in the JSON body — confirmed live: raise_for_status() used
        # to fire here before the body was ever inspected, so the daily-limit
        # message never reached the check below and CJQuotaExceeded never got
        # raised. The 429 was instead swallowed by _fetch_detail's generic
        # `except Exception: return None`, silently turning a real quota outage
        # into a misleading "zero candidates" result for every caller.
        try:
            body = resp.json()
        except ValueError:
            resp.raise_for_status()
            raise
        msg = str(body.get("message", ""))
        if "daily request limit" in msg.lower():
            # Distinct from the 1-QPS limit: retrying within seconds/minutes can
            # never succeed here, so fail fast instead of burning retries/tokens.
            raise CJQuotaExceeded(msg)
        if body.get("result"):
            return body
        if "QPS" in msg or "Too Many" in msg:
            await asyncio.sleep(_CJ_MIN_INTERVAL)
            continue
        return body  # genuine non-rate-limit failure — let caller handle
    return body

# CJ's categoryName query param is NOT a real filter — it's ignored and returns
# the full 1.4M-product catalog. CJ requires the leaf categoryId (a UUID) from
# its fixed taxonomy. We fetch+cache that taxonomy once, then ask an LLM to
# pick the best-matching leaf category for the store's niche.
_CATEGORY_CACHE: list[dict] | None = None


async def _get_category_list() -> list[dict]:
    """Fetch and flatten CJ's category tree into leaf categories. Cached in-memory."""
    global _CATEGORY_CACHE
    if _CATEGORY_CACHE is not None:
        return _CATEGORY_CACHE

    settings = get_settings()
    token = settings.cj_mcp_key or settings.cj_api_key
    leaves: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(f"{_BASE}/product/getCategory", headers={"CJ-Access-Token": token})
            resp.raise_for_status()
            body = resp.json()
        for first in body.get("data", []):
            for second in first.get("categoryFirstList", []):
                for leaf in second.get("categorySecondList", []):
                    leaves.append({
                        "category_id": leaf.get("categoryId", ""),
                        "category_name": leaf.get("categoryName", ""),
                        "path": f"{first.get('categoryFirstName','')} > {second.get('categorySecondName','')} > {leaf.get('categoryName','')}",
                    })
    except Exception as exc:
        logger.warning("Could not fetch CJ category tree: %s", exc)

    _CATEGORY_CACHE = leaves
    return leaves


async def resolve_category(niche_text: str) -> dict | None:
    """
    Map a free-text niche/product description to a real CJ leaf category
    (categoryId + categoryName), since CJ ignores free-text category filters.
    Returns None if no category tree is available or no good match is found.
    """
    from src.llm import get_llm
    from langchain_core.messages import HumanMessage, SystemMessage

    categories = await _get_category_list()
    if not categories:
        return None

    catalogue = "\n".join(f"{c['category_id']}::{c['path']}" for c in categories)
    system = (
        "You map a store's product niche to the single best-matching category from a fixed list.\n"
        "Each line below is formatted as: category_id::category_path\n"
        f"{catalogue}\n\n"
        "Output ONLY valid JSON: {\"category_id\": \"<the exact id from the list>\"}"
    )
    llm = get_llm("scraper", temperature=0.0)
    response = await llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=f"Store niche / product type: {niche_text}"),
    ])
    raw = str(response.content).strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```\s*$', '', raw)
    try:
        picked_id = json.loads(raw.strip()).get("category_id", "")
    except (json.JSONDecodeError, ValueError):
        return None

    return next((c for c in categories if c["category_id"] == picked_id), None)


def _parse_price_range(price: str) -> float:
    """CJ returns prices as either '0.92' or a range '0.53 -- 0.65' / '3.65 - 4.48'."""
    sep = "--" if "--" in str(price) else "-"
    parts = [float(p.strip()) for p in str(price).split(sep)]
    return sum(parts) / len(parts) if parts else 0.0


def _parse_height_age_map(description: str) -> dict[int, str]:
    """
    CJ's product detail `description` HTML often states the supplier's own real
    age↔height correspondence, e.g. "Suitable Height: 6m/59cm, 9m/66cm, 12m/73cm,
    18M/80cm, 24M/85cm". Parse that line directly rather than guessing a fixed
    cm→age band table — the real correspondence varies by garment (a 59cm romper
    and a 59cm dress aren't necessarily the same supplier-intended age), and a
    fixed table was previously found to be flatly wrong (claimed 59cm="0-3M";
    real supplier data for that exact product says 59cm="6m").
    Returns {} if the description doesn't state this — caller then falls back
    to showing the cm measurement alone, never an invented age label.
    """
    mapping: dict[int, str] = {}
    for age, unit, cm in re.findall(r'(\d{1,2})\s*([mM])\s*/\s*(\d{2,3})\s*cm', description or ""):
        mapping[int(cm)] = f"{age}{unit.upper()}"
    return mapping


def _extract_variant_size(variant: dict) -> int | None:
    """Pull the height-in-cm size from a CJ variant's key/name, if present."""
    text = f"{variant.get('variantKey', '')} {variant.get('variantNameEn', '')}"
    match = re.search(r'(\d{2,3})\s*cm', text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _build_supplier_variants(variants: list[dict], price_ratio: float, description: str = "") -> list[dict]:
    """
    Translate CJ's raw per-variant data into {vid, size_label, size_cm,
    price_supplier_usd, price_retail_usd} entries, deduped by size. Returns []
    if no variant carries a recognizable size — caller then creates a
    single-variant product.

    size_label uses the supplier's own stated age↔height correspondence (parsed
    from `description`) when available — e.g. "6M (59cm)" — falling back to the
    bare cm measurement ("59cm") when the description doesn't state one. Never
    an invented/guessed age band.

    Color is NOT extracted here — CJ's real per-SKU color names aren't exposed
    in a usable structured field for these listings (checked: variantProperty is
    "[]" even on products whose category lists color as a dimension). Variants
    instead differ by an opaque numeric "style" code (e.g. "32154Style") that has
    no text label — don't turn that into a fake "Color" without a real name.
    """
    age_map = _parse_height_age_map(description)
    seen_labels: set[str] = set()
    out: list[dict] = []
    for v in variants:
        cm = _extract_variant_size(v)
        if cm is None:
            continue
        label = f"{age_map[cm]} ({cm}cm)" if cm in age_map else f"{cm}cm"
        if label in seen_labels:
            continue
        seen_labels.add(label)
        supplier_price = _parse_price_range(str(v.get("variantSellPrice", "0")))
        out.append({
            "vid": v.get("vid", ""),
            "size_label": label,
            "size_cm": cm,
            "price_supplier_usd": supplier_price,
            "price_retail_usd": round(supplier_price * price_ratio, 2),
        })
    out.sort(key=lambda v: v["size_cm"])
    return out


def _trend_score(listing_count: int) -> int:
    """Heuristic trend signal from CJ's listingCount (stores already selling it).

    CJ's basic product/list endpoint has no dedicated "trend" metric, so this
    derives one from real listing-count data rather than fabricating a score.
    """
    return min(100, 30 + listing_count * 2)


async def _fetch_detail(client: httpx.AsyncClient, token: str, pid: str) -> dict | None:
    """Fetch real supplier price, suggested retail price, and variant id for a product."""
    try:
        body = await _cj_get(client, "product/query", {"pid": pid}, token)
        if not body.get("result"):
            return None
        return body.get("data")
    except CJQuotaExceeded:
        raise  # must propagate — silently returning None here is what caused the
        # "0 candidates, retry forever" loop when the daily quota ran out mid-run.
    except Exception:
        return None


async def search_trending_products(
    category: str = "",
    category_id: str = "",
    max_results: int = 20,
    min_margin: float = 0.30,
    max_price_usd: float = 0.0,
    page_num: int = 1,
) -> list[dict]:
    """
    Search CJ Dropshipping for trending products above a minimum margin.

    Args:
        category: Free-text keyword — used as the search filter when category_id
            isn't available, and always used for the mock-data fallback/logging.
        category_id: Real CJ leaf categoryId (UUID) from resolve_category() —
            preferred over the keyword when present (see priority note above).
        max_results: Maximum number of products to return
        min_margin: Minimum profit margin (0.0–1.0)
        page_num: CJ result page — without this, repeated calls for the same
            category always return the same page-1 items, which dedup then
            filters down to zero "new" candidates once a category's first page
            has already been mined. Callers building toward a product-count
            target should advance this across rounds.

    Returns:
        List of product dicts with keys: product_id, title, price_supplier_usd,
        estimated_price_shopify_usd, margin_pct, trend_score, cj_vid
    """
    settings = get_settings()
    token = settings.cj_mcp_key or settings.cj_api_key
    params = {"pageNum": max(1, page_num), "pageSize": max_results}
    # Prefer the real CJ leaf categoryId over a free-text keyword when resolve_category()
    # found one — verified empirically for baby apparel: categoryId alone returned 9/10
    # genuine baby clothing items vs. mostly unrelated junk (storage bags, adult clothing,
    # baby gear) for the same niche via productNameEn keyword search.
    # CAVEAT: this was flipped FROM keyword-priority because, for a different niche
    # (ambient lighting), the LLM category resolver kept collapsing distinct keywords
    # ("sunset lamp", "galaxy projector") into the same wrong broad leaf, making keyword
    # search the only reliable filter there. If results look generic/repetitive for a
    # new niche, check whether resolve_category() is actually picking distinct, accurate
    # leaves for it before assuming this priority is still right.
    keyword = (category or "").strip()
    if category_id:
        params["categoryId"] = category_id
    elif keyword:
        params["productNameEn"] = keyword

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            body = await _cj_get(client, "product/list", params, token)
            if not body.get("result"):
                raise RuntimeError(body.get("message", "CJ API error"))
            raw = body.get("data", {}).get("list", [])
        except CJQuotaExceeded:
            raise  # hard stop — must reach the caller as a real error, not mock data
        except Exception:
            # Fall back to mock data only when the real API is unreachable.
            return _mock_products(category, max_results)

        # Fetch real price + variant id per candidate. Detail lookups go through the
        # rate-limited _cj_get (1 QPS), so run them sequentially — parallel gather would
        # trip CJ's throttle and drop most candidates. Cap to keep latency bounded.
        # CJQuotaExceeded propagates out of this loop deliberately (not caught here) —
        # see _fetch_detail.
        raw = raw[:12]
        details = [await _fetch_detail(client, token, p["pid"]) for p in raw]

    products = []
    for p, detail in zip(raw, details):
        if detail is None or not detail.get("variants"):
            continue
        supplier_price = _parse_price_range(detail.get("sellPrice", p.get("sellPrice", "0")))
        suggest = _parse_price_range(detail.get("suggestSellPrice", "0"))
        # Cap retail at 3× supplier to avoid absurd CJ suggested prices
        if suggest and (suggest / supplier_price) <= 3.0:
            retail_price = round(suggest, 2)
        else:
            retail_price = round(supplier_price * 2.5, 2)
        margin_pct = round((retail_price - supplier_price) / retail_price, 2)
        images = detail.get("productImageSet") or [p.get("productImage", "")]
        price_ratio = (retail_price / supplier_price) if supplier_price else 2.5
        supplier_description = detail.get("description", "") or ""
        supplier_variants = _build_supplier_variants(detail["variants"], price_ratio, supplier_description)
        products.append({
            "product_id": p["pid"],
            "cj_vid": detail["variants"][0]["vid"],
            "title": p.get("productNameEn") or p.get("productSku", ""),
            "price_supplier_usd": supplier_price,
            "estimated_price_shopify_usd": retail_price,
            "margin_pct": margin_pct,
            "trend_score": _trend_score(p.get("listingCount", 0)),
            # Real supplier spec sheet (fabric, fit, pattern, packing list) — used
            # to ground the branding LLM's copy in real product details instead of
            # generic filler. Not shown verbatim to customers.
            "description": supplier_description,
            "image": images[0] if images else "",
            "images": [img for img in images if img],
            "video": detail.get("productVideo") or "",
            "category": p.get("categoryName", ""),
            # Size variants (e.g. "6M (59cm)") when CJ's listing has more than
            # one — empty list means single-variant product, no size selector needed.
            "supplier_variants": supplier_variants if len(supplier_variants) > 1 else [],
        })

    filtered = [p for p in products if p.get("margin_pct", 0) >= min_margin]
    if max_price_usd > 0:
        filtered = [p for p in filtered if p.get("estimated_price_shopify_usd", 0) <= max_price_usd]
    return filtered[:max_results]


async def get_shipping_cost(
    product_id: str,
    destination_country: str,
    shipping_method: str = "standard",
) -> dict:
    """
    Get shipping cost and estimated days from CJ Dropshipping.

    Args:
        product_id: CJ variant id (cj_vid from search_trending_products), or
            product pid as a fallback — freight is quoted per variant.
        destination_country: ISO 3166-1 alpha-2 country code (e.g. "US")
        shipping_method: "standard" | "express" | "economy"

    Returns:
        Dict with keys: cost_usd, estimated_days, carrier
    """
    settings = get_settings()
    token = settings.cj_mcp_key or settings.cj_api_key
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(
                f"{_BASE}/logistic/freightCalculate",
                json={
                    "startCountryCode": "CN",
                    "endCountryCode": destination_country,
                    "products": [{"quantity": 1, "vid": product_id}],
                },
                headers={"CJ-Access-Token": token},
            )
            resp.raise_for_status()
            body = resp.json()
            options = body.get("data") or []
            if not body.get("result") or not options:
                raise RuntimeError(body.get("message", "no freight options"))
            cheapest = min(options, key=lambda o: float(o.get("logisticPrice", 1e9)))
            return {
                "cost_usd": float(cheapest.get("logisticPrice", 3.99)),
                "estimated_days": int(str(cheapest.get("logisticAging", "12")).split("-")[-1] or 12),
                "carrier": cheapest.get("logisticName", "CJ Packet"),
            }
        except Exception:
            return {"cost_usd": 3.99, "estimated_days": 12, "carrier": "CJ Packet"}


def _mock_products(category: str, count: int) -> list[dict]:
    return [
        {
            "product_id": f"CJ{i:06d}",
            "title": f"Trending {category.title()} Product #{i}",
            "price_supplier_usd": round(5.0 + i * 2.5, 2),
            "estimated_price_shopify_usd": round((5.0 + i * 2.5) * 2.2, 2),
            "margin_pct": round(0.35 + (i % 3) * 0.05, 2),
            "trend_score": 60 + (i % 30),
            "description": f"High-quality {category} product for resale.",
        }
        for i in range(1, count + 1)
    ]
