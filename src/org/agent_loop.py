"""
Sol's autonomous tool-use loop.

The org's normal path is a FIXED pipeline of worker nodes; this module adds a real
agentic loop so the single agent (Sol) can freely READ/WRITE code, run the build +
deploy scripts, source from CJ, and manage Shopify — iterating with tool-use until the
task is done, and narrating every step to Telegram.

Entry point:  await run_sol_task("build a new hero for the store", store_slug="alphaforbaby")

Tools given to Sol (all sandboxed):
  - list_store_files / read_store_file / write_store_file / edit_store_file  → files INSIDE THIS
    STORE'S HYDROGEN APP ONLY (stores/shopify/hydrogen-<store_slug>/). Sol has no reason to touch
    any other folder under stores/ — the Hydrogen app is the only thing that's actually live
    (deployed to Oxygen); older per-store `style/`+Liquid-theme folders are retired.
  - shell            → an ALLOW-LISTED command in the store's Hydrogen app (build/deploy/new-store/git)
  - cj_search_products → CJ Dropshipping product search (baby clothes)
  - shopify_list_products → live products on the store

Guardrails: shell is allow-listed; file read/write/edit is sandboxed to THIS store's Hydrogen app
dir (stores/shopify/hydrogen-<store_slug>/), not all of stores/; deploy.sh itself refuses to ship
unless `npm run build` passes. Requires the litellm proxy to be up (get_llm).
"""
from __future__ import annotations

import asyncio
import contextvars
import json
import re
import logging
import subprocess
import time
import uuid
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from src.llm import get_llm

logger = logging.getLogger(__name__)

# Set at the top of run_sol_task and read by any nested tool call (same asyncio Task,
# so the contextvar is visible all the way down) — lets side-effect helpers like
# _ingest_cj_candidate record their OWN live-timeline step (e.g. "wrote to RAG") without
# threading run_id through every function signature. Same pattern as src/stores'
# _current_store contextvar.
_current_run_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("sol_current_run_id", default=None)


async def _record_step(kind: str, **fields) -> None:
    """Write one live-timeline step for whichever run is current (see _current_run_id).
    No-op outside a tracked run. Fails soft — never let a DB hiccup break Sol's work."""
    run_id = _current_run_id.get()
    if not run_id:
        return
    try:
        from src.org.agent_runs import insert_step
        await asyncio.to_thread(insert_step, run_id, kind, **fields)
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parents[2]
AGENT_NAME = "Sol"


def _model_label() -> str:
    """Human-readable model tag for Telegram, derived from the LIVE role→alias mapping
    (src/llm/client.py._ROLE_MODEL['builder']) instead of a hand-written string —
    a hardcoded "· Sonnet" label previously went stale for days after the model was
    switched to local qwen3 in client.py, silently lying in every Telegram message."""
    try:
        from src.llm.client import _ROLE_MODEL
        alias = _ROLE_MODEL.get("builder", "")
    except Exception:
        alias = ""
    names = {
        "alpha/worker-smart": "Sonnet", "alpha/director": "Opus",
        "alpha/worker-fast": "Haiku", "alpha/local-coder": "local qwen3",
        "alpha/local-fast": "local qwen3",
    }
    return names.get(alias, alias or "unknown model")


# Role shown in Telegram next to Sol's name — includes his model so it's always visible.
AGENT_ROLE = f"Full-Stack Store Builder · {_model_label()}"

# shell allow-list: only these command prefixes may run, and only inside the app dir.
_SHELL_ALLOW = (
    "npm run build", "npm ci", "npm install", "npm run dev",
    "npx shopify hydrogen deploy",
    "./scripts/deploy.sh", "./scripts/new-store.sh",
    "git status", "git checkout -b", "git checkout", "git add", "git commit",
    "git branch", "git diff", "git switch", "git restore",
    "ls", "pwd",
)
# Never let a shell command touch secrets (Sol has read_store_file for store files).
_SHELL_DENY = (".env", "store.env", "printenv", "process.env", "shpat_", "atkn_",
               "SHOPIFY_ACCESS_TOKEN", "DEPLOYMENT_TOKEN", "SECRET", "PASSWORD")


def _app_dir(store_slug: str) -> Path:
    return ROOT / "stores" / "shopify" / f"hydrogen-{store_slug}"


async def _dedupe_images(urls: list[str]) -> list[str]:
    """Drop images that are byte-identical to an earlier one in the list. CJ
    listings sometimes repeat the exact same photo under different CDN URLs —
    confirmed 2026-07-09: the live "Cotton-Linen Baby Romper With Headpiece" PDP
    showed the same photo in most of its gallery slots despite each having a
    distinct CJ URL, so a plain set()-on-URL dedup wouldn't have caught it.
    Fetches each image once and hashes the bytes; keeps first-seen per hash.
    Fails soft: if a fetch fails, the url is kept rather than risk dropping a
    real, distinct photo just because of a network blip."""
    import hashlib
    import httpx
    seen_hashes: set[str] = set()
    seen_urls: set[str] = set()
    out: list[str] = []
    async with httpx.AsyncClient(timeout=15) as client:
        for url in urls:
            if url in seen_urls:
                continue  # exact URL repeat — cheap check before any fetch
            seen_urls.add(url)
            try:
                resp = await client.get(url)
                digest = hashlib.sha256(resp.content).hexdigest()
            except Exception:  # noqa: BLE001
                out.append(url)
                continue
            if digest in seen_hashes:
                continue  # genuine visual duplicate under a different URL — skip
            seen_hashes.add(digest)
            out.append(url)
    return out


def _clean_supplier_description(raw: str) -> str:
    """CJ's raw description HTML embeds its own low-res '<b>Product Image:</b>'
    thumbnail strip — those <img> srcs are CJ's own asset host, not proxied through
    Shopify, and render broken on the storefront (the real photos are already in
    the product's media gallery). Strip the images and their now-empty label."""
    import re
    text = re.sub(r"<img\b[^>]*>", "", raw, flags=re.IGNORECASE)
    text = re.sub(r"<b>\s*Product Image:?\s*</b>\s*(<br\s*/?>\s*)*", "", text, flags=re.IGNORECASE)
    return text.strip()


async def _record_title_alias(shopify_product_id: str, old_title: str, new_title: str) -> None:
    """Upsert into product_title_aliases. original_title is set ONLY on first
    insert and never touched again — repeat rewrites only move current_title
    forward — so this always answers "what did CJ actually call this" even
    after several copywriting passes. Non-fatal on failure."""
    try:
        from src.db.engine import get_session
        from src.db.models import ProductTitleAlias
        async with get_session() as session:
            existing = await session.get(ProductTitleAlias, shopify_product_id)
            if existing:
                existing.current_title = new_title
            else:
                session.add(ProductTitleAlias(
                    shopify_product_id=shopify_product_id,
                    original_title=old_title,
                    current_title=new_title,
                ))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to record title alias for %s: %s", shopify_product_id, exc)


def _safe_in_app(store_slug: str, path: str) -> Path | None:
    """Resolve `path` relative to THIS store's Hydrogen app dir and confirm it stays inside
    it. Returns None if it would escape — e.g. '../alphaforbaby.alpha-tech.live/style/site.json'
    or an absolute path elsewhere. Sol has no legitimate reason to read/write outside his own
    store's Hydrogen app: that app is the only thing actually deployed/live."""
    base = _app_dir(store_slug).resolve()
    raw = Path(path)
    p = (raw if raw.is_absolute() else base / raw).resolve()
    try:
        p.relative_to(base)
    except ValueError:
        return None
    return p


# The one shared, READ-ONLY resource outside a store's own app dir: the cross-store
# skills library. Referenced as 'skills/...' (e.g. 'skills/ui-ux-pro.md') — never writable.
_SKILLS_DIR = ROOT / "stores" / "shopify" / "skills"


def _safe_read_path(store_slug: str, path: str) -> Path | None:
    """Resolve a READ path: 'skills/...' → the shared read-only skills library;
    anything else → relative to THIS store's Hydrogen app dir. None if it escapes either."""
    if path.startswith("skills/"):
        base = _SKILLS_DIR.resolve()
        rel = path[len("skills/"):]
    else:
        base = _app_dir(store_slug).resolve()
        rel = path
    p = (base / rel).resolve()
    try:
        p.relative_to(base)
    except ValueError:
        return None
    return p


# ── Tools ────────────────────────────────────────────────────────────────────
@tool
async def list_store_files(subdir: str = "", store_slug: str = "alphaforbaby") -> dict:
    """List files inside THIS store's Hydrogen app (stores/shopify/hydrogen-<store_slug>/) —
    optionally a subdir like 'app/components', or 'skills' for the shared skills library.
    Cannot list anything outside those two locations."""
    base = _app_dir(store_slug)
    target = _safe_read_path(store_slug, subdir) if subdir else base
    if target is None or not target.exists():
        return {"root": str(base), "files": []}
    root = _SKILLS_DIR if subdir.startswith("skills") else base
    files = sorted(str(f.relative_to(root)) for f in target.rglob("*") if f.is_file())
    return {"root": str(root), "files": files}


@tool
async def read_store_file(path: str, store_slug: str = "alphaforbaby") -> dict:
    """Read a file inside THIS store's Hydrogen app (path relative to
    stores/shopify/hydrogen-<store_slug>/, e.g. 'app/theme.config.json'), or the shared
    read-only skills library via 'skills/...' (e.g. 'skills/ui-ux-pro.md'). Cannot read
    outside those two locations — the old per-store style/ + Liquid-theme folders are
    retired and not part of the live site."""
    p = _safe_read_path(store_slug, path)
    if not p or not p.exists() or not p.is_file():
        return {"error": f"not found or outside the {store_slug} Hydrogen app / skills library: {path}"}
    root = _SKILLS_DIR if path.startswith("skills/") else _app_dir(store_slug)
    return {"path": str(p.relative_to(root)), "content": p.read_text(encoding="utf-8", errors="ignore")}


@tool
async def write_store_file(path: str, content: str, store_slug: str = "alphaforbaby") -> dict:
    """Write/overwrite a file inside THIS store's Hydrogen app ONLY (path relative to
    stores/shopify/hydrogen-<store_slug>/, creates folders as needed). Use for code +
    theme.config.json edits. Cannot write outside that app dir.
    Storefronts are ENGLISH-ONLY; never write Hebrew into store files."""
    p = _safe_in_app(store_slug, path)
    if not p:
        return {"error": f"path escapes the {store_slug} Hydrogen app sandbox: {path}"}
    if p.suffix.lower() == ".json":
        import json
        try:
            json.loads(content)
        except Exception as exc:  # noqa: BLE001
            return {"error": f"invalid JSON, not written: {exc}"}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(p.relative_to(_app_dir(store_slug))), "bytes": len(content)}


@tool
async def edit_store_file(path: str, old: str, new: str, store_slug: str = "alphaforbaby") -> dict:
    """Make a SURGICAL edit to a file inside THIS store's Hydrogen app: replace the exact text
    `old` with `new`. PREFER THIS over write_store_file for changing existing files — it avoids
    re-emitting the whole file. `old` must appear EXACTLY once. Returns {ok} or {error}."""
    p = _safe_in_app(store_slug, path)
    if not p or not p.exists() or not p.is_file():
        return {"error": f"not found or outside the {store_slug} Hydrogen app: {path}"}
    body = p.read_text(encoding="utf-8", errors="ignore")
    n = body.count(old)
    if n == 0:
        return {"error": f"`old` text not found in {path}. Read the file first."}
    if n > 1:
        return {"error": f"`old` appears {n}× in {path}; make it unique (add surrounding lines)."}
    new_body = body.replace(old, new, 1)
    if p.suffix.lower() == ".json":
        import json
        try:
            json.loads(new_body)
        except Exception as exc:  # noqa: BLE001
            return {"error": f"edit would produce invalid JSON, not written: {exc}"}
    p.write_text(new_body, encoding="utf-8")
    return {"ok": True, "path": str(p.relative_to(_app_dir(store_slug))), "bytes": len(new_body)}


@tool
async def shell(command: str, store_slug: str = "alphaforbaby") -> dict:
    """Run ONE allow-listed shell command inside the store's Hydrogen app
    (npm run build | npm ci | ./scripts/deploy.sh <slug> | ./scripts/new-store.sh <slug> | git ...).
    Returns {ok, code, output}. Non-allow-listed commands are refused."""
    cmd = command.strip()
    if any(bad in cmd for bad in _SHELL_DENY):
        return {"ok": False, "error": "refused: commands may not read/echo secrets (.env, tokens). "
                "Store files: use read_store_file. Shopify/CJ: use the API tools."}
    if not any(cmd.startswith(p) for p in _SHELL_ALLOW):
        return {"ok": False, "error": f"command not allow-listed: {cmd!r}. Allowed: {_SHELL_ALLOW}"}
    cwd = _app_dir(store_slug)
    if not cwd.exists():
        return {"ok": False, "error": f"no app dir for store {store_slug!r}: {cwd}"}
    try:
        proc = await asyncio.to_thread(
            subprocess.run, cmd, shell=True, cwd=str(cwd),
            capture_output=True, text=True, timeout=600,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return {"ok": proc.returncode == 0, "code": proc.returncode, "output": out[-4000:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "command timed out after 600s"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


async def _ingest_cj_candidate(pid: str, product: dict, verdict: str, reason: str = "") -> None:
    """Persist a CJ candidate (pass or reject) into the local RAG catalog (Corpus A)
    so future sourcing runs can search it locally and never re-evaluate a known
    reject. Fails soft — a Redis outage must never block sourcing/creation.

    `pid` is ALWAYS passed explicitly by the caller — never guessed from `product`.
    Both callers already have it in scope (search_trending_products's `product_id`
    key at one call site, cj_add_product's own `pid` parameter at the other), and
    those two dicts use different native field names for everything else (CJ's
    search-result shape vs. its raw product/query detail shape). A prior version of
    this function tried to guess the id from `product.get("pid")`/`("productId")`,
    which matched NEITHER shape — every call silently no-opped (caught by nothing,
    since an empty pid just returns early) and the whole catalog corpus stayed
    empty despite real sourcing runs. Confirmed 2026-07-09: verified the ingest
    path itself works via a direct upsert() call, then reproduced zero docs from a
    real cj_search_products call, which is what surfaced this."""
    if not pid:
        return
    try:
        import json
        from src.rag.index import upsert
        title = product.get("productNameEn") or product.get("title") or ""
        desc = product.get("description") or ""
        await upsert(
            "cj_catalog", str(pid), f"{title}\n{desc}",
            {
                "pid": pid, "verdict": verdict, "reason": reason,
                "category": product.get("categoryName") or "",
                "images": json.dumps(product.get("productImageSet") or product.get("images") or []),
                "variants": json.dumps(product.get("variants") or []),
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("CJ catalog RAG ingest failed for %s: %s", product.get("pid"), exc)


@tool
async def search_local_catalog(query: str, count: int = 10) -> dict:
    """Search the LOCAL, already-seen CJ product catalog (persisted from past
    cj_search_products/cj_add_product runs) before hitting CJ live. Use this FIRST
    when looking for "something like X we already looked at" — it also remembers
    which candidates were already rejected (and why), so you don't re-evaluate known
    junk. Falls back to nothing (empty list) if the local index has no match yet —
    in that case use cj_search_products for a live CJ search instead."""
    from src.rag.index import search
    hits = await search("cj_catalog", query, top_k=count)
    return {"candidates": hits}


@tool
async def cj_search_products(keyword: str = "baby clothes", count: int = 12) -> dict:
    """Search CJ Dropshipping for products worth selling (default: baby clothes).
    Returns candidate products as a SLIM summary (product_id, title, price,
    margin, trend_score, image_count, has_video, variant_count) to keep this
    tool's result small — full detail (description, images, variants, specs)
    isn't included here; pass a chosen product_id to cj_add_product, which
    fetches the full CJ detail fresh. Only products with >= 3 images are
    returned (store rule). Resolves the keyword to a
    real CJ category first so results stay on-niche instead of the junk free-text
    search returns (adult clothing, gadgets, car parts)."""
    from src.mcp_tools.sourcing import search_trending_products, resolve_category
    # Resolve to a real CJ leaf category — this is what keeps results genuinely
    # baby-relevant (verified: category_id → 10/10 real baby items vs. mostly junk
    # for the same free-text keyword). Falls back to keyword search if resolve fails.
    resolved = await resolve_category(keyword)
    res = await search_trending_products(
        category=keyword,
        category_id=resolved["category_id"] if resolved else "",
        max_results=count,
    )
    for p in res:
        await _ingest_cj_candidate(p.get("product_id", ""), p, verdict="seen", reason="returned by search_trending_products (>=3 images)")
    if res:
        await _record_step("tool_result", tool_name="rag_ingest",
                            text=f"📥 RAG: cached {len(res)} candidate(s) into cj_catalog corpus", ok=True)
    # Slim the payload before it hits the transcript: search_trending_products'
    # full product dicts (long supplier description, every image URL, full
    # variant/spec objects) run 20-50KB for a 12-product page — well past the
    # generic 6000-char tool-result cap, so the LLM only ever saw a mid-JSON
    # truncation of the first product or two and kept re-searching. Nothing is
    # lost: the full dict is already cached above via RAG ingest, and
    # cj_add_product re-fetches the full CJ detail fresh once a pid is picked.
    slim = [{
        "product_id": p.get("product_id", ""),
        "title": p.get("title", ""),
        "price_supplier_usd": p.get("price_supplier_usd"),
        "estimated_price_shopify_usd": p.get("estimated_price_shopify_usd"),
        "margin_pct": p.get("margin_pct"),
        "trend_score": p.get("trend_score"),
        "category": p.get("category", ""),
        "image_count": len(p.get("images") or []),
        "has_video": bool(p.get("video")),
        "variant_count": len(p.get("supplier_variants") or []) or 1,
    } for p in res]
    return {
        "products": slim,
        "cj_category": resolved["path"] if resolved else None,
    }


@tool
async def shopify_list_products() -> dict:
    """List the products currently live on the Shopify store."""
    from src.mcp_tools.shopify import list_shopify_products
    return {"products": await list_shopify_products()}


@tool
async def shopify_admin(query: str, variables: dict | None = None, store_slug: str = "alphaforbaby") -> dict:
    """Call the store's Shopify ADMIN GraphQL API (queries + mutations). The auth token is
    injected server-side — you never see it. Use this to MANAGE STORE DATA: move products
    between collections (fix categorization), remove duplicates, fix $0/high prices, edit SEO
    titles/meta, manage variants/images. `query` = a GraphQL string; `variables` = its vars.
    Example: query the collections + their products, then `collectionAddProducts`/`collectionRemoveProducts`."""
    import sqlite3
    import httpx
    try:
        c = sqlite3.connect(str(ROOT / "data" / "traces.db"))
        row = c.execute(
            "select shopify_domain, shopify_access_token from stores where store_id=?",
            (store_slug,),
        ).fetchone()
        if not row:
            return {"error": f"no store {store_slug!r}"}
        domain, tok = row
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://{domain}/admin/api/2024-10/graphql.json",
                headers={"X-Shopify-Access-Token": tok, "Content-Type": "application/json"},
                json={"query": query, "variables": variables or {}},
            )
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@tool
async def cj_add_product(pid: str, title: str = "", collection: str = "", store_slug: str = "alphaforbaby") -> dict:
    """Create ONE store product PROPERLY from a CJ product id — the right way to add
    products (use this, NOT raw shopify_admin productCreate). Fetches the CJ detail
    and builds: all images, Color+Size variants EACH with their own image (so the
    gallery swaps on color), a Product Details spec table (material/packaging/weight),
    psychological pricing, and publishes to the storefront. Pass a clean English
    `title`; optional `collection` (e.g. 'Baby Girls') to categorise it."""
    import httpx
    from src.config import get_settings
    from src.mcp_tools.sourcing import _fetch_detail, _parse_price_range, _build_supplier_variants, _supplier_specs
    from src.agents.workers.ecommerce import _psychological_price, _brand_product, _extract_real_specs, _write_description
    from src.mcp_tools.shopify import create_shopify_product, add_product_to_collection, create_collection, _shopify_gql
    tok = get_settings().cj_mcp_key or get_settings().cj_api_key
    try:
        async with httpx.AsyncClient(timeout=40) as c:
            d = await _fetch_detail(c, tok, pid)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"CJ fetch failed: {exc}"}
    if not d or not d.get("variants"):
        return {"error": "CJ returned no product/variants for that pid"}
    imgs = [i for i in (d.get("productImageSet") or []) if i]
    imgs = await _dedupe_images(imgs)
    # Product-only images, never a human model — CJ listings often mix a product
    # shot with a photo of someone wearing the item. Plain face detection (OpenCV
    # Haar cascade, src/mcp_tools/image_person.py), not an AI model — no GPU/
    # Ollama memory involved.
    from src.mcp_tools.image_person import strip_person_images
    imgs = await strip_person_images(imgs)
    if len(imgs) < 3:
        return {"error": f"only {len(imgs)} distinct product-only images (after removing any with a "
                          f"person) — store rule needs >=3, skipped"}

    # Stock guard: never list a product with zero real inventory anywhere — a
    # sale with no stock behind it is a broken order Milo can't fulfill. Checked
    # via the REAL CJ MCP client (cj_product_inventory's own backend), not REST,
    # since REST doesn't expose per-warehouse stock at all. get_product_inventory
    # returns a STRING (a human-readable note + an embedded JSON block with
    # "inventories" — per-country totals — and "variantInventories" — per-vid
    # stock), NOT a plain dict — confirmed against a live call before trusting this.
    try:
        from src.cj_mcp import get_product_inventory
        raw = await get_product_inventory(pid, "US")
        m = re.search(r"\{.*\}", raw, re.DOTALL) if isinstance(raw, str) else None
        inv = json.loads(m.group(0)) if m else (raw if isinstance(raw, dict) else {})
        total_stock = sum(int(w.get("totalInventoryNum") or 0) for w in (inv.get("inventories") or []))
    except Exception as exc:  # noqa: BLE001
        # Log the FULL traceback: this guard swallows any failure from the CJ
        # call or the parse below it, and a bare str(exc) hid which line raised
        # for long enough that a bug here silently rejected every product.
        logger.exception("cj_add_product stock guard failed for pid=%s", pid)
        return {"error": f"couldn't verify CJ stock before listing, skipped: "
                         f"{type(exc).__name__}: {exc}"}
    if total_stock <= 0:
        return {"error": "CJ shows zero stock for this product (all warehouses) — refusing to list an out-of-stock item"}

    # Niche guard: CJ's search/category resolution is known to leak off-niche junk
    # (electronics, home goods, etc.) even for baby-specific keywords — a wireless
    # mouse pad was created this way on 2026-07-07. Reject anything that doesn't
    # look like baby/kids apparel before it ever reaches Shopify.
    _name = (title or d.get("productNameEn") or "").lower()
    _cat = (d.get("categoryName") or "").lower()
    _deny = ("mouse pad", "charger", "charging", "wireless", "electronic", "lamp", "kitchen",
             "pet ", "car accessor", "phone case", "laptop", "bluetooth", "speaker", "cable",
             "machine", "device", "monitor", "stroller", "pacifier", "feeding bottle", " toy")
    if any(k in _name or k in _cat for k in _deny):
        await _ingest_cj_candidate(pid, d, verdict="rejected", reason=f"denylist match: {_name!r}")
        await _record_step("tool_result", tool_name="rag_ingest", text=f"📥 RAG: rejected {pid} — denylist match", ok=True)
        return {"error": f"off-niche result rejected (matched a non-baby keyword): {_name!r}"}
    # Gender/adult-audience terms are checked against the TITLE ONLY, not category — CJ's
    # own category taxonomy nests plenty of genuine baby items under a generic parent like
    # "Women's Clothing > Tops & Sets" (confirmed 2026-07-07 on a product literally titled
    # "...For Baby Girls"), so trusting _cat here caused false-positive rejections of good
    # products. The title is the reliable signal for "is this actually adult clothing".
    _adult_deny = ("women", "womens", "women's", "men's", "mens ", "adult", "sexy", "spicy girl", "bodycon")
    if any(k in _name for k in _adult_deny):
        await _ingest_cj_candidate(pid, d, verdict="rejected", reason=f"adult-deny match: {_name!r}")
        await _record_step("tool_result", tool_name="rag_ingest", text=f"📥 RAG: rejected {pid} — adult-deny match", ok=True)
        return {"error": f"off-niche result rejected (matched a non-baby keyword): {_name!r}"}
    # Require an APPAREL-specific term, not just a baby/kids-audience word — CJ's "baby"
    # category also includes non-clothing gear (sleep machines, monitors, etc.) that a
    # bare "baby"/"kid"/"infant" match would wrongly let through (happened 2026-07-07:
    # a "Baby Soothing Device White Noise Machine" and a "Womens Casual Dress" both
    # passed the old baby/kid-word-only allowlist).
    _allow = ("romper", "onesie", "jumpsuit", "bodysuit", "sleepsuit", "sleeper", "playsuit",
              "swaddle", "bib", "dress", "outfit", "clothing", "apparel", "pajama", "pyjama",
              "shirt", "pants", "shorts", "skirt", "coat", "jacket", "hoodie", "sock", "shoe",
              "hat", "beanie", "legging", "bloomer", "bodysuit")
    if not any(k in _name or k in _cat for k in _allow):
        await _ingest_cj_candidate(pid, d, verdict="rejected", reason=f"no apparel term matched: {_name!r}")
        await _record_step("tool_result", tool_name="rag_ingest", text=f"📥 RAG: rejected {pid} — not apparel", ok=True)
        return {"error": f"doesn't look like baby/kids apparel, skipped: {_name!r}"}

    # Dedup guard: reject if any of this CJ product's own variant ids are already a
    # SKU on the store (SKU = CJ vid) — catches re-adding the same CJ pid even under
    # a different title/collection (happened 2026-07-07).
    candidate_vids = {v.get("vid") for v in d["variants"] if v.get("vid")}
    if candidate_vids:
        existing = await _shopify_gql(
            "{ products(first:100){ nodes{ variants(first:50){ nodes{ sku } } } } }", {})
        existing_skus = {
            n["sku"] for p in existing.get("products", {}).get("nodes", [])
            for n in p.get("variants", {}).get("nodes", []) if n.get("sku")
        }
        if candidate_vids & existing_skus:
            await _ingest_cj_candidate(pid, d, verdict="rejected", reason="duplicate SKU already on store")
            await _record_step("tool_result", tool_name="rag_ingest", text=f"📥 RAG: rejected {pid} — duplicate SKU", ok=True)
            return {"error": "duplicate: this CJ product (or its variants) is already on the store"}

    # Semantic duplicate guard: CJ's catalog itself repeats near-identical listings
    # under DIFFERENT pids (different supplier/reseller re-uploads of the same
    # design) — the SKU-based check above can't catch this since the CJ vids
    # genuinely differ. Confirmed 2026-07-09: "Baby Jumpsuit Spring And Autumn"
    # got created TWICE, two days apart, from two different CJ pids with
    # near-identical titles. Embed this candidate and check it against already-
    # ACCEPTED products in the local RAG catalog before ever touching Shopify —
    # only a product that's genuinely new gets pushed to the store.
    _dup_title = title or (d.get("productNameEn") or "")
    _dup_desc = d.get("description") or ""
    try:
        from src.rag.index import search as _rag_search
        dup_hits = await _rag_search(
            "cj_catalog", f"{_dup_title}\n{_dup_desc}", filters={"verdict": "accepted"}, top_k=1)
    except Exception:  # noqa: BLE001
        dup_hits = []
    if dup_hits and dup_hits[0].get("score") is not None and dup_hits[0]["score"] >= 0.90:
        match = dup_hits[0]
        await _ingest_cj_candidate(
            pid, d, verdict="rejected",
            reason=f"semantic duplicate of already-accepted pid {match['id']} (similarity {match['score']:.2f})")
        await _record_step("tool_result", tool_name="rag_ingest",
                            text=f"📥 RAG: rejected {pid} — semantic duplicate of {match['id']}", ok=True)
        return {"error": f"semantic duplicate: {match['score']:.2f} similarity to already-accepted CJ "
                          f"product {match['id']} — likely the same design re-listed under a different pid, skip it"}

    supplier = _parse_price_range(d.get("sellPrice", "0"))
    sv = _build_supplier_variants(d["variants"], 2.5, d.get("description", "") or "")
    # Guard: CJ's variantKey is assumed 2-dimensional ("Color-Size"), split on the
    # LAST "-". Some listings actually encode 3 dimensions (e.g. "Dark Blue-59cm-Set1"),
    # which silently produces a bogus "color" like "Dark Blue-59cm" (height baked into
    # the color) and a meaningless "Size" of "Set1"/"Set2" — confirmed 2026-07-07 on a
    # product that shipped with 24 near-duplicate Color swatches. Reject rather than
    # create obviously-broken variant data.
    if any(re.search(r'\d{2,3}\s*cm', v["color"], re.IGNORECASE) for v in sv):
        return {"error": "CJ variantKey looks 3-dimensional (color+size collapsed together) "
                          "— this product's variant structure isn't supported yet, skip it"}
    # If CJ had 2+ real variants but _normalize_size (src/mcp_tools/sourcing.py) could
    # not recover a cm value for ANY of them (dropped as ("", 9999) — e.g. internal
    # codes like "WW942"), there's nothing left to sell with a consistent Size
    # selector. Reject rather than create a product with zero real options.
    if d["variants"] and not sv:
        return {"error": "no variant sizes could be normalized to cm — CJ gave only "
                          "unrecognizable size tokens (e.g. internal codes), skip it"}
    variants = [{"color": v["color"], "label": v["size_label"], "sku": v["vid"], "image": v.get("image", ""),
                 "price": _psychological_price(v["price_retail_usd"]),
                 "compare_at_price": _psychological_price(v["price_retail_usd"] * 1.35)}
                for v in sv]
    base = _psychological_price(min([x["price"] for x in variants], default=_psychological_price(supplier * 2.5)))

    # Copywriting: this is Sol's actual job now — never ship raw/machine-translated
    # CJ supplier text. Reuses the same brand/copy prompts as the old automated
    # store-build pipeline (src/agents/workers/ecommerce.py) instead of duplicating them.
    supplier_title = title or (d.get("productNameEn") or "")[:80]
    category = d.get("categoryName") or collection or "Baby & Kids"
    brand = await _brand_product(supplier_title, category)
    real_specs = _extract_real_specs(d.get("description") or "")
    description = await _write_description(
        brand.get("brand_title", supplier_title), category,
        brand.get("hook", ""), brand.get("audience", ""), real_specs,
    )
    final_title = brand.get("brand_title") or supplier_title
    # SEO fields derived from the same copywriting call rather than a second LLM
    # round-trip — keeps this loop fast, which is the whole point of narrowing it.
    seo_title = final_title[:70]
    seo_description = (brand.get("hook") or "").strip()[:160] or supplier_title[:160]

    res = await create_shopify_product(
        title=final_title,
        description=description,
        price=base, compare_at_price=_psychological_price(base * 1.35),
        images=imgs, variants=variants, video_url=d.get("productVideo") or "",
        specs=_supplier_specs(d), seo_title=seo_title, seo_description=seo_description)
    if not res.get("success"):
        return {"error": res.get("error")}
    prod_id = res["product"]["id"]

    # Size guide: CJ's own stated height↔age correspondence (parsed from its
    # description text), stored as a JSON metafield so the storefront can show it
    # in a "Size Guide" popup — independent of whatever unit the Size BUTTON itself
    # is labeled with (CJ's raw variantKey unit can be wrong/odd per listing, e.g.
    # "Yards" on a garment that's actually sized by height in cm).
    from src.mcp_tools.sourcing import _parse_height_age_map
    age_map = _parse_height_age_map(d.get("description") or "")
    if age_map:
        try:
            # NB: no `import json` here. `json` is already imported at module
            # scope, and a function-local import binds the name as a LOCAL for
            # the WHOLE function — so this line (near the end) made the earlier
            # `json.loads(...)` in the stock guard raise UnboundLocalError,
            # which the guard reported as "couldn't verify CJ stock before
            # listing, skipped" and silently rejected every single product.
            await _shopify_gql(
                "mutation($metafields: [MetafieldsSetInput!]!) {"
                " metafieldsSet(metafields: $metafields) { userErrors { field message } } }",
                {"metafields": [{
                    "ownerId": prod_id, "namespace": "custom", "key": "size_guide",
                    "type": "json", "value": json.dumps(age_map),
                }]},
            )
        except Exception:  # noqa: BLE001
            pass  # non-fatal — product still works, just without the size-guide popup

    # Color×Size is a cartesian product — Shopify auto-creates every combination
    # even ones CJ doesn't actually stock. create_shopify_product only prices/skus
    # the real ones and tags the rest with matched_sku="". Left alone those phantom
    # variants ship at Shopify's default $0.00 with no inventory tracking, i.e.
    # untracked ⇒ always "available for sale" ⇒ orderable for free. Delete them.
    variant_nodes = res["product"].get("variants", {}).get("nodes", [])
    phantom_ids = [v["id"] for v in variant_nodes if not v.get("matched_sku")]
    if phantom_ids and len(phantom_ids) < len(variant_nodes):
        try:
            await _shopify_gql(
                "mutation($productId: ID!, $variantsIds: [ID!]!) {"
                " productVariantsBulkDelete(productId: $productId, variantsIds: $variantsIds)"
                " { userErrors { field message } } }",
                {"productId": prod_id, "variantsIds": phantom_ids},
            )
        except Exception:  # noqa: BLE001
            pass  # non-fatal — worst case a $0 phantom variant lingers, not silently corrupting the create

    # Color/collection sanity check: CJ listing titles say "Boys"/"Girls" but the
    # actual PHOTO can disagree (e.g. a pink outfit titled "Newborn Boys
    # Embroidered Outfit") — reads the real image's dominant color (plain pixel
    # analysis, no AI model) and corrects the collection if they clash, matching
    # this store's own existing color convention rather than trusting CJ's title.
    if collection and imgs:
        from src.mcp_tools.image_color import collection_mismatch, dominant_color
        color = await dominant_color(imgs[0])
        corrected = collection_mismatch(collection, color["label"])
        if corrected:
            logger.info(
                "cj_add_product: collection %r clashes with dominant color %r for %r — using %r instead",
                collection, color["label"], final_title, corrected,
            )
            collection = corrected

    if collection:
        try:
            coll = await create_collection(collection)  # get-or-create by title
            if coll.get("collection_id"):
                await add_product_to_collection(prod_id, coll["collection_id"])
        except Exception:  # noqa: BLE001
            pass
    await _ingest_cj_candidate(pid, d, verdict="accepted", reason=f"created as {prod_id}")
    await _record_step("tool_result", tool_name="rag_ingest", text=f"📥 RAG: cached {pid} as accepted ({prod_id})", ok=True)

    # Shopify↔CJ cross-reference — src/db/models.py's ProductMapping docstring says
    # this is "created by create_shopify_product after Shopify API call", but until
    # now only the old ecommerce.py pipeline actually wrote it; this live path never
    # did, silently breaking POST /org/fulfill-latest's ability to dropship these
    # orders (it looks this table up by shopify_product_id). Non-fatal on failure —
    # a DB hiccup shouldn't undo a product that's already live on Shopify.
    try:
        from src.db.engine import get_session
        from src.db.models import ProductMapping
        async with get_session() as session:
            await session.merge(ProductMapping(
                shopify_product_id=prod_id,
                store_id=store_slug,
                supplier_product_id=pid,
                supplier_sku=variants[0]["sku"] if variants else "",
                cost_price=supplier,
                retail_price=base,
            ))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to save product mapping for %s: %s", prod_id, exc)

    await _record_title_alias(prod_id, supplier_title, final_title)

    return {"product_id": prod_id, "images": len(imgs), "variants": len(variants),
            "phantom_variants_removed": len(phantom_ids),
            "collection": collection or "(none)",
            # Creating is no longer the same act as showing it to customers: the
            # publish gate decides, and a brand-new product normally fails it (no
            # 360° video exists yet). `held_back` says exactly what's missing —
            # it's a request to make of a teammate, not an error to retry.
            "published": res.get("published", False),
            "held_back": res.get("held_back", "")}


@tool
async def cj_rewrite_all_copy(limit: int = 0) -> dict:
    """Rewrite marketing copy (title, description, SEO) for EVERY existing product
    already on the store — replaces raw/machine-translated supplier text with real
    benefit-led copy, using the same copywriting step new products get. Works
    directly off each product's CURRENT title/description on Shopify (does NOT
    depend on product_mappings — most live products predate that tracking and have
    no mapping row, confirmed empty for this store's current catalog). Does not
    touch images/variants/price. Set `limit` to a small number to test on a few
    products first — 0 (default) does every live product."""
    from src.mcp_tools.shopify import _shopify_gql, update_product_copy
    from src.agents.workers.ecommerce import _brand_product, _extract_real_specs, _write_description

    products: list[dict] = []
    cursor = None
    while True:
        data = await _shopify_gql(
            "query($cursor: String) { products(first: 50, after: $cursor) { "
            "pageInfo { hasNextPage endCursor } "
            "nodes { id title descriptionHtml productType } } }",
            {"cursor": cursor},
        )
        block = data.get("products", {})
        products.extend(block.get("nodes", []))
        page = block.get("pageInfo", {})
        if not page.get("hasNextPage") or (limit and len(products) >= limit):
            break
        cursor = page.get("endCursor")
    if limit:
        products = products[:limit]

    results = []
    for p in products:
        shopify_id, old_title = p["id"], p["title"]
        category = p.get("productType") or "Baby & Kids"
        try:
            brand = await _brand_product(old_title, category)
            real_specs = _extract_real_specs(p.get("descriptionHtml") or "")
            description = await _write_description(
                brand.get("brand_title", old_title), category,
                brand.get("hook", ""), brand.get("audience", ""), real_specs,
            )
            new_title = brand.get("brand_title") or old_title
            seo_title = new_title[:70]
            seo_description = (brand.get("hook") or "").strip()[:160] or old_title[:160]
            res = await update_product_copy(shopify_id, new_title, description, seo_title, seo_description)
        except Exception as exc:  # noqa: BLE001
            res, new_title = {"success": False, "error": str(exc)}, old_title
        if res.get("success"):
            await _record_title_alias(shopify_id, old_title, new_title)
        results.append({
            "shopify_id": shopify_id,
            "old_title": old_title, "new_title": new_title if res.get("success") else old_title,
            "success": res.get("success", False), "error": res.get("error"),
        })
        await _record_step("tool_result", tool_name="cj_rewrite_all_copy",
                            text=f"✍️ {old_title!r} → {new_title!r}" if res.get("success")
                                 else f"⚠️ failed on {shopify_id}: {res.get('error')}", ok=res.get("success", False))
    ok = sum(1 for r in results if r.get("success"))
    return {"updated": ok, "total": len(results), "results": results}


@tool
async def shopify_publish_products(store_slug: str = "alphaforbaby") -> dict:
    """Publish unpublished products to the storefront — but ONLY those that pass the
    gate. A product created via cj_add_product/shopify_admin is ACTIVE but INVISIBLE
    until published; this is the choke point that makes one visible.

    THE GATE (owner's rule, enforced in code — you cannot talk your way past it):
    >=3 images, Reel's 360° video (CJ's own supplier clip does NOT count), and real
    CJ stock. All three are checked against Shopify and CJ rather than our own
    tables, because a status column can be stale while the storefront is what
    customers actually see. Anything held back comes back in `waiting_on` with the
    teammate who owns the missing piece — ASK THEM with ask_teammate. Idempotent."""
    from src.mcp_tools.shopify import _shopify_gql, _publish_product, media_blockers, PublishBlocked
    try:
        nodes = (await _shopify_gql(
            '{ products(first:100){ nodes{ id title publishedAt '
            'images(first:100){ nodes{ id } } '
            'media(first:100){ nodes{ mediaContentType alt } } } } }', {}
        ))["products"]["nodes"]
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}

    todo = [n for n in nodes if n.get("publishedAt") is None]
    published, waiting, failed = 0, [], []
    for n in todo:
        # Cheap media check first, from data we already have — it saves a CJ stock
        # call (rate-limited to ~1 req/s) on every product that can't go live anyway.
        missing = media_blockers(n)
        if missing:
            waiting.append({"title": n["title"], "needs": "; ".join(missing)})
            continue
        try:
            await _publish_product(n["id"])     # full gate: media re-checked + CJ stock
            published += 1
        except PublishBlocked as exc:
            waiting.append({"title": n["title"], "needs": str(exc)})
        except Exception as exc:  # noqa: BLE001
            failed.append({"title": n["title"], "error": str(exc)})

    note = "products are now on the storefront" if published else "nothing new published"
    if waiting:
        note += (f" — {len(waiting)} held back by the gate. Do NOT retry in a loop: use "
                 "ask_teammate to get the missing media or stock answer from whoever owns it, "
                 "then publish again")
    return {"unpublished_found": len(todo), "published": published,
            "waiting_on": waiting, "failed": failed, "note": note}


@tool
async def cj_stock_sweep(remove: bool = True, max_removals: int = 3,
                         store_slug: str = "alphaforbaby") -> dict:
    """Check REAL CJ stock for EVERY live product and DELETE the ones that are out of
    stock. Standing rule: out of stock at CJ ⇒ off the store immediately — a customer
    must never be able to buy something nobody can ship.

    Reads stock per variant from CJ (each Shopify variant's sku IS the CJ variant id),
    not from Shopify, whose inventory is meaningless for dropship items. Deliberately
    cautious about DELETING real products: a variant whose lookup fails counts as
    UNKNOWN and never triggers removal, a product must read zero on two consecutive
    sweeps before it goes, and at most `max_removals` are removed per run — so a CJ
    outage can't wipe the catalog. Every removal is announced.

    `remove=False` reports what WOULD be removed without touching anything — use that
    first if you want to see the damage before doing it."""
    from src.org.stock_watch import check_store_stock
    res = await check_store_stock(store_slug=store_slug, remove=remove, max_removals=max_removals)
    removed = res.get("removed") or []
    await _record_step("tool_result", tool_name="cj_stock_sweep",
                       text=(f"📦 stock sweep: {res.get('scanned', 0)} scanned, "
                             f"{len(res.get('out_of_stock') or [])} out of stock, "
                             f"{len(removed)} removed"),
                       ok=not res.get("error"))
    return res


@tool
async def ask_teammate(agent: str, question: str) -> dict:
    """ASK A TEAMMATE and get their real answer back. Use this instead of guessing,
    instead of giving up, and instead of retrying something that's blocked on work
    you don't own — e.g. Reel for a product's images or 360° rotation video, Milo
    for live CJ stock/fulfilment reality, Nora for what customers are complaining
    about, Kai for ad performance, Ava when a decision is above your pay grade.

    `agent` = their name or role (see YOUR TEAM in your prompt for who can do what).
    `question` = what you need, concretely: name the product and what's missing, not
    "please help". They actually run their tools on it — this is a real hand-off, not
    a chat message — and their reply comes back to you here, so read it and act on it.

    This is how a blocked product gets unblocked. A product held back by the publish
    gate is not a bug to work around; it's a request to make."""
    cooldown = await _recent_substantive_answer(agent, question)
    if cooldown is not None:
        await _record_step("tool_result", tool_name="ask_teammate",
                           text=f"🤝 (skipped — asked {agent} this within the last 10m) {question[:80]}",
                           ok=True)
        return {"asked": agent, "question": question, "reply": cooldown,
                "note": "Reused a recent answer instead of re-asking — same product/id was asked "
                        "about within the last 10 minutes and got a real answer. If you need a fresh "
                        "check, wait a few minutes or ask about something that's actually changed."}
    from src.org.conversation import dispatch_to_agent
    reply = await dispatch_to_agent(agent, question, requested_by=AGENT_NAME, return_reply=True)
    await _record_step("tool_result", tool_name="ask_teammate",
                       text=f"🤝 asked {agent}: {question[:80]}", ok=True)
    return {"asked": agent, "question": question, "reply": reply}


# A reply this generic isn't a real answer — just an LLM narrating its own charter
# back rather than reporting a result. Don't let it block a legitimate re-ask.
_INCONCLUSIVE_REPLY_PREFIXES = (
    "(on it", "i'll check", "i'll investigate", "i'll verify", "i'll look",
    "i'll search", "checking", "let me check",
)


def _looks_inconclusive(reply: str) -> bool:
    r = (reply or "").strip().lower()
    if len(r) < 40:
        return True
    return any(r.startswith(p) for p in _INCONCLUSIVE_REPLY_PREFIXES)


async def _recent_substantive_answer(agent: str, question: str) -> str | None:
    """Anti-spam guard for ask_teammate: if Sol already asked about the SAME
    product/id within the last 10 minutes and got a real (non-generic) reply,
    return that reply instead of re-asking. Triggered the exact pattern this
    guards against: the same CJ PID re-asked 4-6x in a few minutes, burning
    paid Haiku calls each time for no new information.

    Topic key is the first long digit run in the question (CJ product ids run
    16-19 digits, Shopify ids ~10-13) — deliberately narrow: only dedupe when
    there's a concrete id to match on, never on vague/generic questions."""
    m = re.search(r"\d{10,}", question)
    if not m:
        return None
    key = m.group(0)
    try:
        import sqlite3
        db = sqlite3.connect(str(ROOT / "data" / "traces.db"))
        rows = db.execute(
            "SELECT result_json FROM agent_steps "
            "WHERE tool_name='ask_teammate' AND result_json LIKE ? "
            "AND ts >= datetime('now', '-10 minutes') "
            "ORDER BY ts DESC LIMIT 5",
            (f"%{key}%",),
        ).fetchall()
    except Exception:  # noqa: BLE001
        return None
    for (result_json,) in rows:
        try:
            prev = json.loads(result_json)
        except Exception:
            continue
        if prev.get("asked") != agent:
            continue
        reply = prev.get("reply") or ""
        if not _looks_inconclusive(reply):
            return reply
    return None


@tool
async def cj_product_inventory(pid: str, country_code: str = "US") -> dict:
    """Live CJ warehouse STOCK for a product in a destination country — via CJ's
    REAL MCP server (src/cj_mcp), NOT available through cj_search_products (REST).
    `pid` = CJ product id. Returns per-warehouse inventory (totalInventoryNum,
    cjInventoryNum, factoryInventoryNum) so you can see if an item is actually in
    stock (e.g. US warehouse) before featuring or reordering it."""
    from src.cj_mcp import get_product_inventory, CJMCPThrottled, CJMCPError
    try:
        return {"inventory": await get_product_inventory(pid, country_code)}
    except CJMCPThrottled as exc:
        return {"error": f"CJ MCP throttled (retry shortly): {exc}"}
    except CJMCPError as exc:
        return {"error": str(exc)}


@tool
async def cj_track_shipment(track_numbers: str) -> dict:
    """Live shipment TRACKING for one or more CJ tracking numbers (comma-separated)
    — via CJ's REAL MCP server (src/cj_mcp). Use to answer 'where is order X?'."""
    from src.cj_mcp import get_tracking_info, CJMCPThrottled, CJMCPError
    try:
        return {"tracking": await get_tracking_info(track_numbers)}
    except CJMCPThrottled as exc:
        return {"error": f"CJ MCP throttled (retry shortly): {exc}"}
    except CJMCPError as exc:
        return {"error": str(exc)}


@tool
async def search_playbook(query: str, count: int = 5) -> dict:
    """Search Sol's own operating playbook — the accumulated docs/guides on WHY certain
    products get sourced, what makes an SEO-good title/description, how to showcase a
    product, QA/SEO checklists, etc. (ingested from docs/*.md, guides/**/*.md). Call
    this instead of assuming — e.g. "what makes a good product description" or "how
    should a new product's gallery be structured" — before writing SEO copy or making a
    sourcing/display judgment call."""
    from src.rag.index import search
    return {"guidance": await search("playbook", query, top_k=count)}


@tool
async def refresh_playbook() -> dict:
    """Re-ingest the playbook RAG corpus (search_playbook) from the current
    docs/*.md and guides/**/*.md files. Call this AFTER you edit or add a guide doc
    (e.g. after appending to STORE_MEMORY.md, or updating PRODUCT_UPLOAD_PIPELINE.md/
    QA.md/SEO.md via edit_store_file/write_store_file) — otherwise search_playbook
    keeps returning the stale pre-edit content. Idempotent (safe to call anytime)."""
    from scripts.ingest_playbook import _find_markdown_files, _ingest_file
    files = _find_markdown_files()
    total = 0
    for path in files:
        total += await _ingest_file(path)
    return {"files_processed": len(files), "chunks_ingested": total}


@tool
async def send_customer_email(to: str, subject: str, body: str, in_reply_to: str | None = None) -> dict:
    """Send an email to a customer from THIS STORE'S support address (never your own
    identity). Sign as store support, never disclose internal costs/margins/system
    details, keep it short and on-topic. For anything refund/legal-shaped, do NOT
    promise money back yourself — open a ticket instead and say a human will follow up."""
    from src.mcp_tools.email import send_email
    return await send_email(to=to, subject=subject, body=body, in_reply_to=in_reply_to)


@tool
async def check_inbox(query: str = "is:unread", max_results: int = 10) -> dict:
    """Check the store's support inbox for new customer messages (Gmail). Returns
    thread_id/from/subject/snippet/body per message — use send_customer_email to reply
    (pass in_reply_to=thread's message_id to thread it), then mark_email_handled."""
    from src.mcp_tools.email import check_inbox as _check_inbox
    return await _check_inbox(query=query, max_results=max_results)


@tool
async def mark_email_handled(thread_id: str) -> dict:
    """Mark a customer email thread as handled (removes UNREAD) so check_inbox stops
    returning it. Call this after you've replied via send_customer_email."""
    from src.mcp_tools.email import mark_handled
    return await mark_handled(thread_id)


# Narrowed 2026-07-23: Sol is sourcing+copywriting+push only, not a developer —
# dropped list_store_files/read_store_file/write_store_file/edit_store_file/shell
# (store code) and send_customer_email/check_inbox/mark_email_handled (customer
# comms, out of scope). Those tool functions stay defined above for a future
# dev-focused agent; only what's bound here shrank.
_TOOLS = [
    cj_search_products, cj_add_product, cj_rewrite_all_copy, shopify_list_products, shopify_admin, shopify_publish_products,
    # CJ via REAL MCP (src/cj_mcp) — data REST/cj_search_products can't reach
    cj_product_inventory, cj_track_shipment, cj_stock_sweep,
    # Peer delegation: Sol owns the catalog but not the media or the warehouse.
    # Without this he had no way to reach the teammate who does, from inside the
    # loop where the work actually happens — so he shipped around the problem.
    ask_teammate,
    # Local RAG (Redis) — Corpus A: seen CJ candidates; Corpus B: Sol's own playbook docs
    search_local_catalog, search_playbook, refresh_playbook,
]
_TOOLS_BY_NAME = {t.name: t for t in _TOOLS}


# ── System prompt ────────────────────────────────────────────────────────────
def _charter() -> str:
    """Sol's charter from the DB (stays in sync with seed.py), with a safe fallback.

    Also appends his recent per-agent lessons (agent.memory["lessons"], written by
    train_agent/record_lesson) — until this was added they were recorded but never
    read back into HIS OWN real tool-using run (only into the meeting persona
    summary shown to other agents, and the plain-chat fallback in conversation.py),
    so a lesson trained on him could never change what he actually does."""
    try:
        from src.org.models import list_agents
        for a in list_agents(active_only=True):
            if a.name == AGENT_NAME:
                lessons = a.memory.get("lessons", [])
                if lessons:
                    return a.skill + "\n\nRecent lessons you've learned (apply these): " + "; ".join(lessons[-5:])
                return a.skill
    except Exception:  # noqa: BLE001
        pass
    return "Sole autonomous full-stack Shopify builder. Sources from CJ, writes code, deploys."


def _team_block() -> str:
    """The live roster — who's on the team and what each of them can actually run,
    derived at call time from the DB roster + tool catalog (src/org/directory.py).

    Sol is the only agent with a real tool loop, and until now his prompt was the
    one place the roster never reached: he could not name a teammate, so he had no
    choice but to work around whatever he couldn't do himself. This is data, not
    routing — no teammate is named in code; he reads the directory and decides who
    to ask."""
    try:
        from src.org.directory import capability_directory
        return capability_directory(exclude=AGENT_NAME)
    except Exception:  # noqa: BLE001
        return "(roster unavailable — ask Ava who owns this)"


def _store_memory(store_slug: str) -> str:
    """Sol's persistent knowledge of the store — so he doesn't re-read everything each run."""
    try:
        p = ROOT / "stores" / "shopify" / f"hydrogen-{store_slug}" / "docs" / "STORE_MEMORY.md"
        if p.exists():
            return ("\n\nYOUR STORE MEMORY (you already KNOW this store — do NOT re-read files you "
                    "know from here; read a file only when you need its current content to edit it. "
                    "After a change, APPEND one line under 'Recent changes' in docs/STORE_MEMORY.md "
                    "via edit_store_file):\n" + p.read_text(encoding="utf-8")[:4500])
    except Exception:  # noqa: BLE001
        pass
    return ""


def _system_prompt(store_slug: str) -> str:
    app = f"stores/shopify/hydrogen-{store_slug}"
    return (
        "CRITICAL LANGUAGE RULE: You ALWAYS respond in ENGLISH ONLY, in every message, "
        "even when the user writes to you in Hebrew or any other language. Never reply in Hebrew.\n"
        + _store_memory(store_slug) + (
        f"You are {AGENT_NAME}, {AGENT_ROLE}. {_charter()}\n\n"
        f"CURRENT STORE: {store_slug}. You are NOT a developer — you have no file, shell, build, "
        f"or deploy tools (that changed 2026-07-23; ignore any past instruction or memory that "
        f"tells you to edit theme.config.json, run npm/deploy scripts, or touch the Hydrogen app "
        f"at {app}/ — none of that is reachable from here anymore). If a task asks for a store "
        f"code/UI/theme change, say plainly that's outside your job now — ask_teammate whoever "
        f"owns dev work if YOUR TEAM below lists one, otherwise tell the owner directly. Your job "
        f"is CJ sourcing + copywriting + pushing products live via shopify_admin/"
        f"shopify_publish_products.\n\n"
        f"PUBLISHING (CRITICAL): a product you create via shopify_admin is ACTIVE but INVISIBLE "
        f"on the live store until it is published to the storefront sales channel. After creating "
        f"ANY product(s), you MUST call shopify_publish_products — otherwise the owner sees NOTHING "
        f"on the store. When told 'I don't see products', run shopify_publish_products first.\n"
        f"THE PUBLISH GATE (owner's rule, enforced in code): a product reaches customers only "
        f"with >=3 images, a real 360° video and live CJ stock. Creating a product no longer "
        f"publishes it. A product held back is correct behaviour, not a bug — and it is not "
        f"yours to work around: you own the catalog, not the media and not the warehouse. Read "
        f"the blocker, decide who on YOUR TEAM below owns the missing piece, and ask_teammate "
        f"them. Never publish anyway, never retry the same publish in a loop, and never report a "
        f"product as live when the gate held it back.\n\n"
        f"YOUR TEAM — the live roster. You are not alone and you are not stuck; every one of "
        f"these is an agent you can ask, and they answer for themselves:\n{_team_block()}\n\n"
        f"CJ DATA TOOLS: for product SEARCH/detail use cj_search_products (CJ REST — already "
        f"filters to >=3 images, resolves the niche category). For anything about STOCK or "
        f"SHIPMENTS use the REAL CJ MCP tools: cj_product_inventory(pid, country_code) for live "
        f"warehouse stock by country, and cj_track_shipment(track_numbers) for tracking — REST "
        f"cannot give these. From now on ALWAYS check cj_product_inventory before featuring, "
        f"reordering, or promising availability on a product (e.g. confirm the US warehouse "
        f"actually has stock). MCP wraps the same CJ backend, so it is NOT richer product detail "
        f"than REST — use REST for the catalog, MCP for inventory + tracking. See docs/mcp_vs_rest.md.\n\n"
        f"RULES: storefronts are ENGLISH-ONLY. Never publish the owner's personal details "
        f"(only public contact: support@alphaforbaby.com). Use the tools to actually "
        f"DO the work — don't just describe it.\n\n"
        f"RAG: before a live CJ search, try search_local_catalog first (it remembers past "
        f"candidates AND why they were rejected — don't re-evaluate a known reject). For "
        f"sourcing/SEO/display judgment calls (why this product, what makes a good title/"
        f"description, how to showcase it), call search_playbook instead of guessing. "
        f"search_local_catalog updates itself automatically as you source/create products — "
        f"but if YOU edit a guide doc (docs/*.md, guides/**/*.md, e.g. appending to "
        f"STORE_MEMORY.md), call refresh_playbook afterward so search_playbook isn't stale.\n\n"
        f"CUSTOMER EMAIL: you have no email tool (send_customer_email/check_inbox/"
        f"mark_email_handled) — that's Nora's job. If a task asks you to reply to a customer, "
        f"ask_teammate Nora with the details instead of trying to send it yourself.\n\n"
        f"When done, give a short final summary IN ENGLISH."
    ))


# Sentinel distinguishing "no reply_thread_id given" (say() uses Sol's own default
# Telegram topic) from an explicit `None` (which means General specifically, per
# post_as's thread_override contract) — see run_sol_task's `reply_thread_id` param.
_NO_THREAD = object()


# ── The loop ─────────────────────────────────────────────────────────────────
async def run_sol_task(task: str, store_slug: str = "alphaforbaby", max_steps: int = 40,
                       narrate: bool = True, images: list[str] | None = None,
                       run_id: str | None = None, ticket_id: str | None = None,
                       max_minutes: float = 0, reply_thread_id=_NO_THREAD) -> dict:
    """Run Sol autonomously on `task` until done (or max_steps, or max_minutes wall-clock
    elapses — whichever comes first; max_minutes=0 means no time cap, only max_steps).
    Narrates each step to Telegram AND records it live to data/traces.db (agent_runs/agent_steps)
    for the platform-app `/agents/live` live activity page — see src/org/agent_runs.py.
    `images` = list of data: URLs (e.g. a Telegram screenshot) — Sol sees them and fixes accordingly.
    `run_id` — pass to correlate with a caller-known id (e.g. from POST /org/sol); auto-generated
    if omitted, so every call path (heartbeat, chat, tickets) still gets a live-recorded run.
    `ticket_id` — if set, the ticket flips to 'doing' at start and 'done' on a clean finish.
    `max_minutes` matters for scheduled/cron-triggered runs: POST /org/sol fires this loop in
    the BACKGROUND and returns immediately, so a caller's own timeout (e.g. a cron job's
    --timeout-seconds) never actually bounds this loop's real runtime — only max_steps did,
    until this param existed.
    `reply_thread_id` — the Telegram topic the triggering message came from (e.g. General);
    when given, Sol's narration lands there instead of his own default topic. Omit for
    non-chat callers (heartbeat, tickets, POST /org/sol) to keep the old default-topic behavior.
    Returns {steps, final, transcript_len}."""
    from src.org.telegram import post_as
    from src.org.agent_runs import start_run, finish_run
    from src.org.tickets import update_ticket

    run_id = run_id or str(uuid.uuid4())
    _current_run_id.set(run_id)  # visible to nested tool calls in this same Task, e.g. RAG writes

    async def say(text: str) -> None:
        if narrate and text:
            try:
                if reply_thread_id is _NO_THREAD:
                    await post_as(AGENT_NAME, AGENT_ROLE, text)
                else:
                    await post_as(AGENT_NAME, AGENT_ROLE, text, thread_override=reply_thread_id)
            except Exception:  # noqa: BLE001
                pass

    record = _record_step

    await asyncio.to_thread(start_run, run_id, AGENT_NAME, task, store_slug, ticket_id)
    if ticket_id:
        try:
            await asyncio.to_thread(update_ticket, ticket_id, status="doing")
        except Exception:  # noqa: BLE001
            pass

    # Multimodal first message when a screenshot is attached (e.g. a mobile bug photo).
    if images:
        human = HumanMessage(content=(
            [{"type": "text", "text": task}]
            + [{"type": "image_url", "image_url": {"url": u}} for u in images]
        ))
    else:
        human = HumanMessage(content=task)

    # Narrowed 2026-07-23: sourcing+copywriting+push doesn't need the heavy "builder"
    # tier (a 35B local model) — moved to "shopify_dev" (Haiku), already budget-aware
    # (falls back to the free local model over the monthly cap, same as before).
    # timeout raised 180->600 2026-08-16: 180s was well under LiteLLM's own 900s
    # budget and tripped on ordinary slow steps (large/late-loop prompts, or the
    # local Ollama fallback's prompt-reprocessing cost), aborting the whole run and
    # losing all prior steps' progress — same failure mode already fixed for
    # standup calls (90s->240s). This is a per-call ceiling, not multiplied by
    # max_steps: each of up to 40 llm.ainvoke() calls in the loop below gets its
    # own independent budget.
    llm = get_llm("shopify_dev", temperature=0.2, max_tokens=8000, timeout=600).bind_tools(_TOOLS)
    messages = [SystemMessage(content=_system_prompt(store_slug)), human]
    opener = f":hammer_and_wrench: On it — *{task}* (store: {store_slug})"
    await say(opener)  # full text to Telegram — only the live-timeline copy is capped
    await record("status", text=opener[:600])

    steps = 0
    start_time = time.monotonic()
    try:
        for _ in range(max_steps):
            if max_minutes and (time.monotonic() - start_time) > max_minutes * 60:
                await say(f":alarm_clock: Reached the {max_minutes}-minute time budget — stopping.")
                await asyncio.to_thread(finish_run, run_id, "max_minutes", f"{max_minutes}-minute budget reached")
                if ticket_id:
                    try:
                        await asyncio.to_thread(update_ticket, ticket_id, status="doing")
                    except Exception:  # noqa: BLE001
                        pass
                return {"steps": steps, "final": "max_minutes reached", "transcript_len": len(messages)}
            resp: AIMessage = await llm.ainvoke(messages)
            messages.append(resp)
            calls = getattr(resp, "tool_calls", None) or []
            if resp.content and isinstance(resp.content, str) and resp.content.strip():
                thought = resp.content.strip()[:1500]
                await say(thought)
                await record("thought", text=thought)
            if not calls:
                await asyncio.to_thread(finish_run, run_id, "done", str(resp.content or ""))
                if ticket_id:
                    try:
                        await asyncio.to_thread(update_ticket, ticket_id, status="done")
                    except Exception:  # noqa: BLE001
                        pass
                return {"steps": steps, "final": resp.content, "transcript_len": len(messages)}

            for call in calls:
                steps += 1
                name, args = call["name"], call.get("args", {})
                await say(f":gear: `{name}` {_short_args(args)}")
                await record("tool_call", tool_name=name, text=_short_args(args),
                             args_json=json.dumps(args, ensure_ascii=False)[:4000])
                fntool = _TOOLS_BY_NAME.get(name)
                if not fntool:
                    result = {"error": f"unknown tool {name}"}
                else:
                    try:
                        result = await fntool.ainvoke(args)
                    except Exception as exc:  # noqa: BLE001
                        result = {"error": str(exc)}
                messages.append(ToolMessage(content=_truncate(result), tool_call_id=call["id"]))
                await say(_result_line(name, result))
                ok = isinstance(result, dict) and not result.get("error")
                await record("tool_result", tool_name=name, text=_result_line(name, result),
                             result_json=_truncate(result), ok=ok)
                # Knowledge-graph logging (Stage 1, best-effort): a FalkorDB hiccup
                # must never break Sol's autonomous run.
                try:
                    from src.graph.knowledge_graph import log_tool_execution
                    await log_tool_execution(AGENT_NAME, name, ok, detail=_result_line(name, result)[:200])
                except Exception:
                    pass
    except Exception as exc:  # noqa: BLE001
        await asyncio.to_thread(finish_run, run_id, "error", str(exc)[:1500])
        await record("status", text=f":x: Sol hit an error: {exc}"[:1500])
        if ticket_id:
            # Revert to 'todo' rather than leaving it stuck at 'doing' forever —
            # a ticket only started "doing" because we, not the caller, said so.
            try:
                await asyncio.to_thread(update_ticket, ticket_id, status="todo")
            except Exception:  # noqa: BLE001
                pass
        raise

    await say(":warning: Reached max steps — stopping. Tell me to continue.")
    await asyncio.to_thread(finish_run, run_id, "max_steps", "max_steps reached")
    if ticket_id:
        try:
            await asyncio.to_thread(update_ticket, ticket_id, status="todo")
        except Exception:  # noqa: BLE001
            pass
    return {"steps": steps, "final": "max_steps reached", "transcript_len": len(messages)}


def _short_args(args: dict) -> str:
    parts = []
    for k, v in (args or {}).items():
        s = str(v)
        parts.append(f"{k}={s[:60]}{'…' if len(s) > 60 else ''}")
    return " ".join(parts)[:180]


def _result_line(name: str, result) -> str:
    if isinstance(result, dict):
        if result.get("error"):
            return f":x: `{name}` — {str(result['error'])[:200]}"
        if "ok" in result:
            tail = (result.get("output") or "")[-200:]
            return f":white_check_mark: `{name}` ok={result['ok']}" + (f" — …{tail}" if tail else "")
        if "products" in result:
            return f":white_check_mark: `{name}` — {len(result['products'])} items"
    return f":white_check_mark: `{name}` done"


def _truncate(result, limit: int = 6000) -> str:
    try:
        s = json.dumps(result, ensure_ascii=False)
    except Exception:  # noqa: BLE001
        s = str(result)
    return s[:limit]
