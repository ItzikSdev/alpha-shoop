"""
Continuous CTO → Developer delegation. **LEGACY / DORMANT (2026-06-29).**

This was the loop that kept a local-model Developer (Grace) busy: a CTO (Linus)
looked at REAL store state and handed her the single most valuable theme change to
work on each heartbeat tick. The 5-role autonomous flow (docs/prompt.md) retired
the standing Developer — store design/build now happens INSIDE pipeline runs
(design_node / frontend_node / ecommerce_node), and the CEO (Ava) picks the next
run directly via the heartbeat's business-agent path. So `linus_delegates()` finds
no active "Developer" and returns None (a cheap, graceful no-op) — it's kept only
so the /org/delegate route stays importable. `load_store_design()` is still used by
the heartbeat's dev path for any future local Developer. Safe to delete in a later
cleanup pass.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from src.llm import get_llm
from src.org.conversation import _parse_json, company_language
from src.org.meeting import gather_snapshot
from src.org.models import (
    Agent,
    Company,
    get_agent,
    get_company,
    list_agents,
    save_agent,
)
from src.org.seed import seed_founding_team
from src.org.slack import post_as
from src.stores import list_stores
from src.tracing import agent_log

logger = logging.getLogger(__name__)

# How many of Grace's own turns to let her spend on one task before Linus rotates
# her to the next improvement (keeps her from looping the same fix forever).
TURNS_BEFORE_ROTATE = 3

# Where Susan/the owner drop the target design mockups (an approved write/read
# location — see [[design_pipeline_plan]]). One design.html per store slug.
_STYLES_ROOT = Path(__file__).resolve().parents[2] / "stores" / "shopify"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _active(role: str) -> Agent | None:
    return next((a for a in list_agents(active_only=True) if a.role.lower() == role.lower()), None)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def load_store_design() -> tuple[str, str]:
    """Return (store_name, design_brief) for the first active store that has a
    `styles/shopify/<slug>/design.html` mockup, else ('', ''). The brief is the
    target look the live Shopify theme must be made to match — it's injected into
    Linus's task-picking and Grace's turn so they actually work TOWARD the design
    instead of guessing. Read server-side (Grace never touches the filesystem)."""
    # Available design folders (each with a design.html mockup).
    try:
        folders = [d.name for d in _STYLES_ROOT.iterdir() if d.is_dir() and (d / "style" / "design.html").exists()]
    except Exception:
        folders = []
    if not folders:
        return "", ""

    for s in list_stores():
        if not s.active:
            continue
        # Match a store to a design folder by name / storefront_slug / domain prefix,
        # tolerant to suffixes (e.g. store "timeforbaby_kgg" → folder "timeforbaby").
        cands = {_slug(s.name), _slug(s.storefront_slug or ""), _slug((s.shopify_domain or "").split(".")[0])}
        cands.discard("")
        match = next(
            (fl for fl in folders
             if any(c == _slug(fl) or c.startswith(_slug(fl)) or _slug(fl).startswith(c)
                    or _slug(fl) in c or c in _slug(fl) for c in cands)),
            None,
        )
        if match:
            f = _STYLES_ROOT / match / "style" / "design.html"
            try:
                html = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            m = re.search(r"<style>(.*?)</style>", html, re.DOTALL)
            css = (m.group(1).strip() if m else "")[:1800]
            brief = (
                f"TARGET STORE DESIGN (mockup: {f}). The live Shopify theme MUST be "
                f"made to look like this premium design. Core CSS / design tokens:\n{css}\n\n"
                "Translate it into the REAL theme via the Shopify Admin Asset API "
                "(write assets/custom-alpha.css + patch layout/theme.liquid) and theme "
                "settings — match: the dark animated announcement marquee, the sticky "
                "blurred header, the full-bleed hero with the headline + uppercase CTA "
                "button, the 4-up trust 'pills' bar, 3:4 product cards with hover-zoom, "
                "the soft 'story' section, and the multi-column footer. Colors: ink "
                "#161616, soft #f6f4f1, lines #eee."
            )
            return s.name, brief
    return "", ""


def _store_context() -> str:
    """Concrete, real per-store context so Linus assigns grounded tasks (niche +
    the owner's free-text description of what the store is / should become)."""
    lines = []
    for s in list_stores():
        if not s.active:
            continue
        desc = (s.description or "").strip().replace("\n", " ")
        lines.append(
            f"- {s.name} (niche: {s.niche or 'n/a'}; domain: {s.shopify_domain}): "
            f"{desc[:240] or 'no description on file'}"
        )
    return "\n".join(lines) or "(no active stores yet)"


_PICK_SYS = """\
You are {name}, the CTO of Alpha and the owner's right hand. Grace is your senior
developer; she executes ONE task at a time directly on the live Shopify store.

THE STORE IS FULLY JSON-DRIVEN — the homepage is `site.json` and the product page
is `product.json` (in stores/shopify/timeforbaby.alpha-tech.live/style/). Grace changes the design by
editing those JSON files and re-rendering with her tools (apply_design). She must
NEVER hand-fetch theme ids or build raw asset PUTs — that's wasteful and wrong.
Already DONE (do NOT re-assign): 7-image hero carousel, size variants on all
products, free shipping, social-proof popup, real CJ descriptions, JSON-driven
font sizes. COLOR + SIZE variants now come straight from CJ automatically: the
publishing pipeline emits a Color selector for every NEW product, and each cycle
the ecommerce worker self-heals OLD products that lack one (adds the Color
selector + binds each color/size to its exact CJ SKU). So "products have no color
choice" is NOT a task to assign — it's already automated end to end. Use
`scan_store` to see real state before deciding.

Your job: choose the SINGLE most valuable next task for Grace, phrased as a
concrete change (e.g. "in product.json add a Size chart element and bump
description_size", "source 3-5 real images per product", "in site.json add a
reviews/testimonials section"). Keep it high-level (WHAT to change in the JSON),
not low-level API steps. Avoid vague advice; avoid repeating a done task. The real
lever to REVENUE now is TRAFFIC (ads) — not endless design loops.

Reply in {language}. Output ONLY JSON:
{{"task":"<one concrete task for Grace, imperative, 1 sentence>",
  "note":"<short first-person line you'll say to Grace in the channel>"}}"""


async def _linus_pick_task(linus: Agent | None, grace: Agent, company: Company) -> tuple[str, str]:
    snapshot = await gather_snapshot()
    history = grace.memory.get("task_history", [])
    _, design_brief = load_store_design()
    # Critic feedback: what Grace's LAST action actually achieved (success/failure).
    last = grace.memory.get("last_result") or {}
    if last.get("ok") is False:
        feedback = (
            f"\n\n⚠️ GRACE'S LAST ACTION FAILED — action: {last.get('action')} "
            f"(status {last.get('status')}) → {last.get('detail')}\n"
            "Your next task MUST fix this exact failure (correct the path/payload/id), "
            "not move on to something else."
        )
    elif last.get("ok") is True:
        feedback = (
            f"\n\n✅ Grace's last action succeeded: {last.get('action')} (status "
            f"{last.get('status')}). Build on it — the NEXT concrete step toward the design."
        )
    else:
        feedback = ""
    system = _PICK_SYS.format(
        name=linus.name if linus else "Linus", language=company_language(),
    )
    # Money reality: revenue vs cost (incl. what Grace/Linus cost in LLM tokens) so
    # Linus steers toward profit — not endless design loops. Best-effort; honest
    # about data pipes that aren't connected yet (e.g. PayPal re-auth pending).
    finance_block = ""
    try:
        from src.mcp_tools.finance import finance_snapshot, _summary_line
        snap = await finance_snapshot(30)
        finance_block = (
            f"\n\n=== MONEY (last 30d) — steer toward NET profit ===\n{_summary_line(snap)}\n"
            + (f"(data pipes not connected yet: {', '.join(snap['pending_data'])})\n" if snap.get("pending_data") else "")
        )
    except Exception:
        pass
    design_block = (
        f"\n\n=== THE STORE MUST MATCH THIS DESIGN — prioritize closing the gap ===\n{design_brief}\n"
        if design_brief else ""
    )
    # Who the owner is + what he actually wants — so Linus assigns tasks that match
    # Itzik's real priorities and reads his intent correctly (not generic guesses).
    owner_block = ""
    try:
        from src.mcp_tools.design_files import read_store_docs
        owner = read_store_docs("timeforbaby").get("owner", "")
        if owner:
            owner_block = f"\n\n=== WHO YOU WORK FOR — Itzik's priorities & style (honor these) ===\n{owner[:1800]}\n"
    except Exception:
        pass
    user = (
        f"{owner_block}"
        f"LIVE STORE STATE:\n{json.dumps(snapshot, indent=2)}\n\n"
        f"STORES (niche + owner's description):\n{_store_context()}\n"
        f"{feedback}\n"
        f"{design_block}\n"
        f"COMPANY GOALS: {company.goals}\n"
        f"LESSONS: {company.lessons[-5:]}\n"
        f"{finance_block}\n"
        f"GRACE'S CURRENT TASK (may be empty): {grace.memory.get('assigned_task','') or '(none)'}\n"
        f"TASKS GRACE ALREADY DID RECENTLY (do NOT repeat these):\n"
        + ("\n".join(f"- {t}" for t in history[:8]) or "(none yet)")
        + "\n\nPick Grace's next task now. While the live theme doesn't match the "
        "target design above, prefer a concrete step that moves it closer."
    )
    try:
        llm = get_llm(linus.model_role if linus else "executive", temperature=0.4, max_tokens=700)
        resp = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
        parsed = _parse_json(str(resp.content))
        task = str(parsed.get("task", "")).strip()
        note = str(parsed.get("note", "")).strip()
        return task, note
    except Exception as exc:
        logger.warning("Linus task-pick failed: %s", exc)
        return "", ""


async def linus_delegates(force: bool = False) -> dict | None:
    """Ensure Grace has a current task from Linus. No-op if she's mid-task (unless
    `force`). Returns the assignment dict when a NEW task is handed over, else None."""
    company = seed_founding_team()
    grace = _active("Developer")
    if not grace:
        return None

    # Append a daily money snapshot to the finance ledger (once/day, idempotent) so
    # the store accrues a real revenue-vs-cost history alongside the changelog.
    try:
        from src.mcp_tools.finance import log_finance_snapshot
        await log_finance_snapshot(30)
    except Exception:
        logger.debug("finance snapshot skipped", exc_info=True)

    current = (grace.memory.get("assigned_task") or "").strip()
    turns = int(grace.memory.get("turns_on_task", 0))
    failing = (grace.memory.get("last_result") or {}).get("ok") is False
    # Critic loop: if her last action FAILED, re-engage immediately with a
    # corrective task instead of letting her keep repeating a broken call.
    if current and not force and turns < TURNS_BEFORE_ROTATE and not failing:
        return None  # she's actively working and not failing — leave her be

    linus = _active("CTO")
    task, note = await _linus_pick_task(linus, grace, company)
    if not task:
        return None

    # Roll the just-finished task into history so Linus won't re-pick it.
    grace = get_agent(grace.agent_id) or grace
    history = grace.memory.get("task_history", [])
    if current and current not in history:
        history.insert(0, current)
    grace.memory["task_history"] = history[:8]
    grace.memory["assigned_task"] = task
    grace.memory["assigned_at"] = _now()
    grace.memory["turns_on_task"] = 0
    save_agent(grace)

    by = linus.name if linus else "Linus"
    await post_as(by, "CTO", note or f"📋 {grace.name}, focus next on: {task}")
    agent_log(f"📋 {by} → {grace.name}: {task}", "action")
    return {"assigned_to": grace.name, "task": task, "note": note}
