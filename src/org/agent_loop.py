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
AGENT_ROLE = "Full-Stack Store Builder"

# shell allow-list: only these command prefixes may run, and only inside the app dir.
_SHELL_ALLOW = (
    "npm run build", "npm ci", "npm install", "npm run dev",
    "./scripts/deploy.sh", "./scripts/new-store.sh",
    "git status", "git checkout -b", "git checkout", "git add", "git commit",
    "git branch", "git diff", "git switch", "git restore",
    "node -", "ls", "cat ", "pwd",
)


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
async def shell(command: str, store_slug: str = "timeforbaby") -> dict:
    """Run ONE allow-listed shell command inside the store's Hydrogen app
    (npm run build | npm ci | ./scripts/deploy.sh <slug> | ./scripts/new-store.sh <slug> | git ...).
    Returns {ok, code, output}. Non-allow-listed commands are refused."""
    cmd = command.strip()
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
    Returns candidate products with rating/shipping/price info."""
    from src.mcp_tools.sourcing import search_trending_products
    try:
        res = await search_trending_products(category=keyword, count=count)  # type: ignore[call-arg]
    except TypeError:
        res = await search_trending_products(keyword, count)  # positional fallback
    return {"products": res}


@tool
async def shopify_list_products() -> dict:
    """List the products currently live on the Shopify store."""
    from src.mcp_tools.shopify import list_shopify_products
    return {"products": await list_shopify_products()}


_TOOLS = [
    list_store_files, read_store_file, write_store_file, shell,
    cj_search_products, shopify_list_products,
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


def _system_prompt(store_slug: str) -> str:
    app = f"stores/shopify/hydrogen-{store_slug}"
    return (
        f"You are {AGENT_NAME}, {AGENT_ROLE}. {_charter()}\n\n"
        f"CURRENT STORE: {store_slug}. Its Hydrogen app is at {app}/ — the store's whole look "
        f"is driven by {app}/app/theme.config.json (brand, colors, fonts, nav, hero, tiles, "
        f"testimonials, legal, favicons). Products come LIVE from the Shopify Storefront API; "
        f"policies come LIVE from Shopify. THIS IS A TEMPLATE: to change a store edit its "
        f"theme.config.json (and app/*.jsx only when structure must change) — do NOT tangle or "
        f"rewrite the template wholesale. To make a NEW store, run ./scripts/new-store.sh <slug> "
        f"then edit its store-profiles/<slug>/theme.config.json; deploy with ./scripts/deploy.sh <slug>.\n\n"
        f"AFTER ANY CHANGE you MUST follow {app}/docs/AGENT_WORKFLOW.md and run the checks in "
        f"docs/QA.md, docs/SEO.md and docs/UIUX.md (new store = run the full set). Before going to "
        f"production, run the full audit in stores/shopify/skills/store-audit.md. "
        f"RULES: storefronts are ENGLISH-ONLY. Work on a git branch. ALWAYS run `npm run build` "
        f"and confirm it passes before any deploy. Never publish the owner's personal details "
        f"(only public contact: suppot.timeforbaby@alpha-tech.live). Use the tools to actually "
        f"DO the work — don't just describe it. When done, give a short final summary in Hebrew."
    )


# ── The loop ─────────────────────────────────────────────────────────────────
async def run_sol_task(task: str, store_slug: str = "timeforbaby", max_steps: int = 25,
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

    llm = get_llm("executive", temperature=0.2, max_tokens=4000).bind_tools(_TOOLS)
    messages = [SystemMessage(content=_system_prompt(store_slug)), human]
    await say(f":hammer_and_wrench: על זה — *{task}* (חנות: {store_slug})")

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

    await say(":warning: הגעתי למקסימום צעדים — עוצר. תגיד לי אם להמשיך.")
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
