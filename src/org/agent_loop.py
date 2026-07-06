"""
Sol's autonomous tool-use loop.

The org's normal path is a FIXED pipeline of worker nodes; this module adds a real
agentic loop so the single agent (Sol) can freely READ/WRITE code, run the build +
deploy scripts, source from CJ, and manage Shopify — iterating with tool-use until the
task is done, and narrating every step to Slack.

Entry point:  await run_sol_task("build a new hero for the store", store_slug="timeforbaby")

Tools given to Sol (all sandboxed):
  - list_store_files / read_store_file / write_store_file  → any file under stores/ (design_files)
  - shell            → an ALLOW-LISTED command in the store's Hydrogen app (build/deploy/new-store/git)
  - cj_search_products → CJ Dropshipping product search (baby clothes)
  - shopify_list_products → live products on the store

Guardrails: shell is allow-listed; file writes are sandboxed to stores/; deploy.sh itself
refuses to ship unless `npm run build` passes. Requires the litellm proxy to be up (get_llm).
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from src.llm import get_llm
from src.mcp_tools.design_files import (
    list_design_files,
    read_design_file,
    write_design_file,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
AGENT_NAME = "Sol"
# Role shown in Slack next to Sol's name — includes his model so it's always visible.
AGENT_ROLE = "Full-Stack Store Builder · Sonnet"

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


# ── Tools ────────────────────────────────────────────────────────────────────
@tool
async def list_store_files(subdir: str = "") -> dict:
    """List files under stores/ (optionally a subdir like 'shopify/hydrogen-timeforbaby/app')."""
    return list_design_files(subdir)


@tool
async def read_store_file(path: str) -> dict:
    """Read a file under stores/ (path relative to stores/, e.g. 'shopify/hydrogen-timeforbaby/app/theme.config.json')."""
    return read_design_file(path)


@tool
async def write_store_file(path: str, content: str) -> dict:
    """Write/overwrite a file under stores/ (creates folders). Use for code + theme.config.json edits.
    Storefronts are ENGLISH-ONLY; never write Hebrew into store files."""
    return write_design_file(path, content)


@tool
async def edit_store_file(path: str, old: str, new: str) -> dict:
    """Make a SURGICAL edit to a file under stores/: replace the exact text `old` with `new`.
    PREFER THIS over write_store_file for changing existing files — it avoids re-emitting the
    whole file. `old` must appear EXACTLY once. Returns {ok} or {error}."""
    r = read_design_file(path)
    if r.get("error"):
        return {"error": r["error"]}
    body = r["content"]
    n = body.count(old)
    if n == 0:
        return {"error": f"`old` text not found in {path}. Read the file first."}
    if n > 1:
        return {"error": f"`old` appears {n}× in {path}; make it unique (add surrounding lines)."}
    return write_design_file(path, body.replace(old, new, 1))


@tool
async def shell(command: str, store_slug: str = "timeforbaby") -> dict:
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


@tool
async def cj_search_products(keyword: str = "baby clothes", count: int = 12) -> dict:
    """Search CJ Dropshipping for products worth selling (default: baby clothes).
    Returns candidate products (each with images[], video, price, margin). Only
    products with >= 3 images are returned (store rule). Resolves the keyword to a
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
    return {
        "products": res,
        "cj_category": resolved["path"] if resolved else None,
    }


@tool
async def shopify_list_products() -> dict:
    """List the products currently live on the Shopify store."""
    from src.mcp_tools.shopify import list_shopify_products
    return {"products": await list_shopify_products()}


@tool
async def shopify_admin(query: str, variables: dict | None = None, store_slug: str = "timeforbaby") -> dict:
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
async def cj_add_product(pid: str, title: str = "", collection: str = "") -> dict:
    """Create ONE store product PROPERLY from a CJ product id — the right way to add
    products (use this, NOT raw shopify_admin productCreate). Fetches the CJ detail
    and builds: all images, Color+Size variants EACH with their own image (so the
    gallery swaps on color), a Product Details spec table (material/packaging/weight),
    psychological pricing, and publishes to the storefront. Pass a clean English
    `title`; optional `collection` (e.g. 'Baby Girls') to categorise it."""
    import httpx
    from src.config import get_settings
    from src.mcp_tools.sourcing import _fetch_detail, _parse_price_range, _build_supplier_variants, _supplier_specs
    from src.agents.workers.ecommerce import _psychological_price
    from src.mcp_tools.shopify import create_shopify_product, add_product_to_collection, create_collection
    tok = get_settings().cj_mcp_key or get_settings().cj_api_key
    try:
        async with httpx.AsyncClient(timeout=40) as c:
            d = await _fetch_detail(c, tok, pid)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"CJ fetch failed: {exc}"}
    if not d or not d.get("variants"):
        return {"error": "CJ returned no product/variants for that pid"}
    imgs = [i for i in (d.get("productImageSet") or []) if i]
    if len(imgs) < 3:
        return {"error": f"only {len(imgs)} images — store rule needs >=3, skipped"}
    supplier = _parse_price_range(d.get("sellPrice", "0"))
    sv = _build_supplier_variants(d["variants"], 2.5, d.get("description", "") or "")
    variants = [{"color": v["color"], "label": v["size_label"], "sku": v["vid"], "image": v.get("image", ""),
                 "price": _psychological_price(v["price_retail_usd"]),
                 "compare_at_price": _psychological_price(v["price_retail_usd"] * 1.35)}
                for v in sv]
    base = _psychological_price(min([x["price"] for x in variants], default=_psychological_price(supplier * 2.5)))
    res = await create_shopify_product(
        title=title or (d.get("productNameEn") or "")[:80],
        description=f"<p>{(d.get('productNameEn') or '').strip()}</p>",
        price=base, compare_at_price=_psychological_price(base * 1.35),
        images=imgs, variants=variants, video_url=d.get("productVideo") or "",
        specs=_supplier_specs(d))
    if not res.get("success"):
        return {"error": res.get("error")}
    prod_id = res["product"]["id"]
    if collection:
        try:
            coll = await create_collection(collection)  # get-or-create by title
            if coll.get("collection_id"):
                await add_product_to_collection(prod_id, coll["collection_id"])
        except Exception:  # noqa: BLE001
            pass
    return {"product_id": prod_id, "images": len(imgs), "variants": len(variants),
            "collection": collection or "(none)", "published": True}


@tool
async def shopify_publish_products(store_slug: str = "timeforbaby") -> dict:
    """Publish EVERY currently-unpublished product to the storefront sales channels
    (Online Store + the headless channel). A product created via shopify_admin is
    ACTIVE but INVISIBLE on the live store until published — run this after adding
    products, or whenever 'I don't see products on the store'. Idempotent."""
    from src.mcp_tools.shopify import _shopify_gql, _publish_product
    try:
        nodes = (await _shopify_gql('{ products(first:100){ nodes{ id title publishedAt } } }', {}))["products"]["nodes"]
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
    todo = [n for n in nodes if n.get("publishedAt") is None]
    published = 0
    for n in todo:
        try:
            await _publish_product(n["id"])
            published += 1
        except Exception:  # noqa: BLE001
            pass
    return {"unpublished_found": len(todo), "published": published,
            "note": "products are now on the storefront" if published else "all already published"}


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


_TOOLS = [
    list_store_files, read_store_file, write_store_file, edit_store_file, shell,
    cj_search_products, cj_add_product, shopify_list_products, shopify_admin, shopify_publish_products,
    # CJ via REAL MCP (src/cj_mcp) — data REST/cj_search_products can't reach
    cj_product_inventory, cj_track_shipment,
]
_TOOLS_BY_NAME = {t.name: t for t in _TOOLS}


# ── System prompt ────────────────────────────────────────────────────────────
def _charter() -> str:
    """Sol's charter from the DB (stays in sync with seed.py), with a safe fallback."""
    try:
        from src.org.models import list_agents
        for a in list_agents(active_only=True):
            if a.name == AGENT_NAME:
                return a.skill
    except Exception:  # noqa: BLE001
        pass
    return "Sole autonomous full-stack Shopify builder. Sources from CJ, writes code, deploys."


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
        f"CURRENT STORE: {store_slug}. Its Hydrogen app is at {app}/ — the store's whole look "
        f"is driven by {app}/app/theme.config.json (brand, colors, fonts, nav, hero, tiles, "
        f"testimonials, legal, favicons). Products come LIVE from the Shopify Storefront API; "
        f"policies come LIVE from Shopify. THIS IS A TEMPLATE: to change a store edit its "
        f"theme.config.json (and app/*.jsx only when structure must change) — do NOT tangle or "
        f"rewrite the template wholesale. To make a NEW store, run ./scripts/new-store.sh <slug> "
        f"then edit its store-profiles/<slug>/theme.config.json.\n\n"
        f"EDITING: prefer edit_store_file (surgical find/replace) over write_store_file — NEVER rewrite "
        f"a whole file unless it is new/small. Touch ONLY the file/component the task names; do not "
        f"refactor adjacent files unless told. Never delete closing tags or needed vars. "
        f"COMMUNICATE IN ENGLISH. Keep replies to a 1-sentence confirmation of what changed + the "
        f"preview URL — no long explanations or apologies. DEPLOY (CI/CD) — ALWAYS PREVIEW FIRST, NEVER straight to "
        f"production: after `npm run build` passes + your checks, run shell `./scripts/deploy.sh "
        f"{store_slug} --preview` (handles the token; do NOT read .env/secrets). Then read "
        f"stores/shopify/hydrogen-{store_slug}/h2_deploy_log.json, and in your reply give Itzik the "
        f"PREVIEW URL + a short summary of what you changed, and STOP. Do NOT deploy to production "
        f"(`./scripts/deploy.sh {store_slug}`) until Itzik explicitly approves the preview.\n\n"
        f"PUBLISHING (CRITICAL): a product you create via shopify_admin is ACTIVE but INVISIBLE "
        f"on the live store until it is published to the storefront sales channel. After creating "
        f"ANY product(s), you MUST call shopify_publish_products — otherwise the owner sees NOTHING "
        f"on the store. When told 'I don't see products', run shopify_publish_products first.\n\n"
        f"CJ DATA TOOLS: for product SEARCH/detail use cj_search_products (CJ REST — already "
        f"filters to >=3 images, resolves the niche category). For anything about STOCK or "
        f"SHIPMENTS use the REAL CJ MCP tools: cj_product_inventory(pid, country_code) for live "
        f"warehouse stock by country, and cj_track_shipment(track_numbers) for tracking — REST "
        f"cannot give these. From now on ALWAYS check cj_product_inventory before featuring, "
        f"reordering, or promising availability on a product (e.g. confirm the US warehouse "
        f"actually has stock). MCP wraps the same CJ backend, so it is NOT richer product detail "
        f"than REST — use REST for the catalog, MCP for inventory + tracking. See docs/mcp_vs_rest.md.\n\n"
        f"FOR ANY TASK: first read stores/shopify/skills/SKILLS_MAP.md and open the MATCHING skill "
        f"(UI/UX → skills/ui-ux-pro.md; manage store data/collections → skills/.claude/skills/shopify-admin/"
        f"SKILL.md + the shopify_admin tool; Hydrogen code → skills/.claude/skills/shopify-hydrogen/SKILL.md; "
        f"etc.), then do the work YOURSELF. You own the store. "
        f"AFTER ANY CHANGE you MUST follow {app}/docs/AGENT_WORKFLOW.md and run the checks in "
        f"docs/QA.md, docs/SEO.md and the ui-ux-pro skill (new store = run the full set). Before going to "
        f"production, run the full audit in stores/shopify/skills/store-audit.md. "
        f"RULES: storefronts are ENGLISH-ONLY. Work on a git branch. ALWAYS run `npm run build` "
        f"and confirm it passes before any deploy. Never publish the owner's personal details "
        f"(only public contact: suppot.timeforbaby@alpha-tech.live). Use the tools to actually "
        f"DO the work — don't just describe it. When done, give a short final summary IN ENGLISH."
    ))


# ── The loop ─────────────────────────────────────────────────────────────────
async def run_sol_task(task: str, store_slug: str = "timeforbaby", max_steps: int = 40,
                       narrate: bool = True, images: list[str] | None = None) -> dict:
    """Run Sol autonomously on `task` until done (or max_steps). Narrates each step to Slack.
    `images` = list of data: URLs (e.g. a Slack screenshot) — Sol sees them and fixes accordingly.
    Returns {steps, final, transcript_len}."""
    from src.org.slack import post_as

    async def say(text: str) -> None:
        if narrate and text:
            try:
                await post_as(AGENT_NAME, AGENT_ROLE, text)
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

    # Big token budget so whole-file writes aren't truncated (that caused stuck loops).
    # Sol runs on Opus (the "builder" tier) for deep reasoning + code; falls back to
    # the free local model only when over the monthly budget cap.
    llm = get_llm("builder", temperature=0.2, max_tokens=8000).bind_tools(_TOOLS)
    messages = [SystemMessage(content=_system_prompt(store_slug)), human]
    await say(f":hammer_and_wrench: On it — *{task}* (חנות: {store_slug})")

    steps = 0
    for _ in range(max_steps):
        resp: AIMessage = await llm.ainvoke(messages)
        messages.append(resp)
        calls = getattr(resp, "tool_calls", None) or []
        if resp.content and isinstance(resp.content, str) and resp.content.strip():
            await say(resp.content.strip()[:1500])
        if not calls:
            return {"steps": steps, "final": resp.content, "transcript_len": len(messages)}

        for call in calls:
            steps += 1
            name, args = call["name"], call.get("args", {})
            await say(f":gear: `{name}` {_short_args(args)}")
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

    await say(":warning: Reached max steps — stopping. Tell me to continue.")
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
    import json
    try:
        s = json.dumps(result, ensure_ascii=False)
    except Exception:  # noqa: BLE001
        s = str(result)
    return s[:limit]
