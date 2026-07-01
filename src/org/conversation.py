"""
Two-way Slack: each agent answers in their own voice.

`agents_respond(message)` takes a message (yours) and has EVERY active agent
reply in-persona — using their role, skill, recent lessons, and the company
culture — then posts each reply to the Slack channel as that agent. So you ask
one thing and see Ada (CEO), Linus (CTO), Maya (HR)… each answer.

Reading your Slack message automatically needs a bot token (a webhook can only
post). If SLACK_BOT_TOKEN + SLACK_CHANNEL are set, `fetch_and_respond()` pulls
new channel messages and answers them; otherwise call `agents_respond(text)`
directly (e.g. via POST /org/respond) with the text.

All LLM calls are best-effort: if the proxy/model is down, the agent falls back
to a short canned line so the channel still gets a reply.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re

import httpx
from langchain_core.messages import HumanMessage, SystemMessage

from src.llm import get_llm
from src.org.models import Agent, get_company, list_agents
from src.org.slack import post_as, post_to_slack

logger = logging.getLogger(__name__)

_ROLE_EMOJI = {"CEO": ":crown:", "CTO": ":brain:", "HR": ":office_worker:"}

from pathlib import Path as _Path

_STORES_ROOT = _Path(__file__).resolve().parents[2] / "stores" / "shopify"


def _store_context(store_slug: str = "timeforbaby") -> str:
    """The REAL store folder tree + the CLAUDE.md build guide, injected into the
    agents' prompts so they can answer 'list the folders' / 'read the style files'
    THEMSELVES — instead of confabulating that they lack access and asking the
    owner to paste it. The agents DO have full repo access; this proves it."""
    try:
        store_dir = next((d for d in _STORES_ROOT.iterdir()
                          if d.is_dir() and store_slug in d.name), None)
    except Exception:
        store_dir = None
    if not store_dir:
        return ""
    # Real recursive listing (so "list all folders" is answered with truth).
    lines: list[str] = [f"{store_dir.relative_to(_STORES_ROOT.parent.parent)}/"]
    try:
        for p in sorted(store_dir.rglob("*")):
            if any(part.startswith(".") for part in p.relative_to(store_dir).parts):
                continue
            rel = p.relative_to(store_dir)
            depth = len(rel.parts) - 1
            lines.append("  " * (depth + 1) + (f"{p.name}/" if p.is_dir() else p.name))
    except Exception:
        pass
    tree = "\n".join(lines[:60])
    guide = ""
    try:
        from src.mcp_tools.design_files import read_store_docs
        guide = (read_store_docs(store_slug).get("claude") or "")[:1600]
    except Exception:
        pass
    return (
        "\n\n=== YOU HAVE FULL REPO + STORE ACCESS — read these yourself, never ask the owner to paste them ===\n"
        f"Live folder tree of the store template (real listing):\n{tree}\n"
        + (f"\n--- CLAUDE.md (the build guide; build the store to match style/site.json + design.html) ---\n{guide}\n" if guide else "")
    )


def _budget_line_safe() -> str:
    """The live org-credit line for the agents' prompts, so they know how many $ are
    left this month and stay economical (hard $100/mo cap). Best-effort — never break
    a reply if the budget read fails."""
    try:
        from src.budget import budget_line
        return ("ORG CREDITS (hard $100/mo cap — be economical with tokens; when the "
                "cap is hit the team auto-switches to the free local model): " + budget_line())
    except Exception:
        return ""


def company_language() -> str:
    """The default language agents speak in the channel (ORG_LANGUAGE, default
    Hebrew). They still switch to match a message that's clearly in another
    language."""
    return os.environ.get("ORG_LANGUAGE", "Hebrew").strip() or "Hebrew"


def _parse_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)
    return json.loads(text)


def _human_content(text: str, images: list[str] | None):
    """A LangChain HumanMessage content payload — plain text, or multimodal
    (text + image_url parts) when the user attached images. The image_url parts
    are base64 data URLs the vision model (Claude Sonnet) reads directly."""
    if not images:
        return text
    parts = [{"type": "text", "text": text}]
    for url in images:
        parts.append({"type": "image_url", "image_url": {"url": url}})
    return parts

# Remember the last Slack message timestamp we answered, so the poller doesn't
# reply to the same message twice within a process.
_last_ts: dict[str, str] = {}

# Guards against the fast poll firing a second round while one is still posting
# (a full 3-agent reply takes a few seconds; the poll runs every ~4s).
_responding = asyncio.Lock()


async def _recent_transcript(exclude_msg: str = "", limit: int = 12) -> str:
    """Recent channel conversation as a labelled transcript (oldest first), so any
    reply path can feed the agent its memory of what was said. '' on failure."""
    try:
        from src.org.slack import fetch_channel_history
        hist = await fetch_channel_history(limit)
        if hist and exclude_msg and hist[-1]["text"].strip() == exclude_msg.strip():
            hist = hist[:-1]  # drop a trailing echo of the message we're answering
        # Cap each line so a giant JSON dump (e.g. an applied site.json) can't
        # dominate the context window.
        return "\n".join(f"{h['author']}: {h['text'][:300]}" for h in hist[-limit:])
    except Exception:
        return ""


async def _agent_reply(agent: Agent, message: str, author: str, company,
                       images: list[str] | None = None) -> str:
    system = (
        f"You are {agent.name}, the {agent.role} of Alpha, an autonomous "
        "e-commerce company of AI agents. Stay in character and answer in FIRST "
        "PERSON, 1-3 sentences, concrete and grounded in your role.\n"
        f"Write in {company_language()} by default; only switch if the message is "
        "clearly in another language, then match it.\n"
        "If image(s) are attached, look at them and respond to what they show.\n"
        "You CAN see the recent channel conversation (quoted in the user message) — "
        "you DO remember what was said; use it for context and never claim each "
        "conversation starts from scratch.\n"
        f"Your job (skill): {agent.skill}\n"
        f"Company values: {company.culture.get('values', []) if company else []}\n"
        f"Company goals: {company.goals if company else []}\n"
        f"Recent lessons you've learned: {agent.memory.get('lessons', [])[-2:]}\n"
        f"{_budget_line_safe()}\n"
        "You have FULL access to the repo, the store files, and the Shopify Admin "
        "API — NEVER say you lack access or ask the owner to paste files/confirm "
        "permission. The store folder tree + build guide are below; read them and act."
        + _store_context()
    )
    caption = message or "(no caption — see the attached image)"
    transcript = await _recent_transcript(message)
    user = (
        (f"Recent conversation in the team channel (oldest first) — this is your "
         f"memory of what was said:\n{transcript}\n\n" if transcript else "")
        + f"{author} just wrote:\n\"{caption}\"\n\nReply as {agent.name}, using the "
        "conversation above as context."
    )
    try:
        # Images need the vision-capable model — use the smart tier when present.
        role = "executive" if images else (agent.model_role or "standup")
        llm = get_llm(role, temperature=0.7, max_tokens=400)
        resp = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=_human_content(user, images)),
        ])
        text = str(resp.content).strip()
        if text:
            return text
    except Exception as exc:
        logger.warning("Agent %s reply failed: %s", agent.name, exc)
    # Fallback so the channel still hears from them.
    return f"(On it — {agent.role} here. {agent.skill.split('.')[0]}.)"


async def _post_replies(items: list[tuple[Agent, str]]) -> list[dict]:
    """Post each (agent, text) AS that agent, spaced for Slack's rate limit."""
    out: list[dict] = []
    for i, (agent, text) in enumerate(items):
        if i > 0:
            await asyncio.sleep(1.1)
        await post_as(agent.name, agent.role, text)
        out.append({"agent": agent.name, "role": agent.role, "reply": text})
    return out


async def agents_respond(message: str, author: str = "You") -> list[dict]:
    """EVERY active agent replies (the chorus path) — each as its own identity.

    Used when a message is clearly for the whole team. For a normal message,
    prefer `route_and_respond`, which picks only the relevant teammate(s).
    """
    company = get_company()
    agents = list_agents(active_only=True)
    texts = await asyncio.gather(
        *(_agent_reply(a, message, author, company) for a in agents)
    )
    return await _post_replies(list(zip(agents, texts)))


_DISPATCH_SYS = """\
You are the Alpha team's message router. Given a message in the team channel and
the roster, decide WHO should answer — usually ONE teammate (the single most
relevant person), occasionally two, and ALL of them only if the message is
clearly addressed to everyone (e.g. a group greeting).

The team is 5 agents — ALWAYS pick the SPECIALIST whose domain the message is
about; do NOT funnel everything to the CEO. Use the EXACT role string:
- "Product Hunter" (Hunter)  → ANY mention of CJ / sourcing / finding products /
  prices / margins / "get products" / "add products" / "push products to the store".
  Hunter actually runs the CJ search himself.
- "UX & Content" (Remy)      → the store's LOOK, design, theme, announcement bar,
  colors, fonts, hero, copy, branding. Remy actually edits the design himself.
- "Shopify Developer" (Devon) → low-level Shopify API ops: variants, SEO metadata,
  collections, theme/liquid plumbing, reading store files, listing folders.
- "Growth Marketer" (Max)    → ads, Facebook/Instagram, traffic, campaigns.
- "CEO" (Ava)                → ONLY strategy/direction/money/vision, a build-or-
  launch decision, or a genuinely ambiguous greeting. NOT the default dumping ground.
If the message NAMES a person (e.g. "Devon, ..."), THAT person answers. When in
doubt between the CEO and a specialist, pick the specialist.

EVERY agent has FULL repo + Shopify access — never route to "ask the owner for
permission". The chosen person reads/does it themselves.

Write each chosen person's reply in FIRST PERSON, 1-3 sentences, in the SAME
LANGUAGE as the message (Hebrew → natural Hebrew). Output ONLY JSON:
{"responders":[{"role":"CEO","reply":"..."}]}"""


# Agents allowed to execute Shopify directly (full freedom, no approval gate).
# The new roster: Devon owns the Shopify API; Ava (CEO) orchestrates + can act.
_SHOPIFY_DOERS = {"Shopify Developer", "CEO", "Developer", "CTO"}


async def _agent_act_shopify(agent: Agent, message: str, company) -> str:
    """Let a Shopify doer (Devon/Ava) actually RUN a Shopify call in chat (no
    approval) and report the result, instead of only talking about it."""
    system = (
        f"You are {agent.name} ({agent.role}) at Alpha. You have FULL DIRECT "
        "Shopify Admin API + repo/store-file access — NO approval needed, you act "
        "yourself. NEVER ask the owner for permission or to paste files.\n"
        f"Answer in {company_language()}. You can see the recent channel conversation "
        "in the user message — you DO remember it; use it for context. If the request "
        "needs a Shopify call, include it. Output ONLY JSON:\n"
        '{"reply":"<short first-person reply>","shopify_request":null OR '
        '{"method":"GET|POST|PUT|DELETE","path":"<e.g. products/count.json>","body":<obj or null>}}'
        + _store_context()
    )
    transcript = await _recent_transcript(message)
    human = (f"Recent conversation (oldest first), your memory of the chat:\n{transcript}\n\n"
             if transcript else "") + author_q(message)
    try:
        role = "developer" if agent.role == "Developer" else "executive"
        llm = get_llm(role, temperature=0.3, max_tokens=900)
        resp = await llm.ainvoke([SystemMessage(content=system),
                                  HumanMessage(content=human)])
        parsed = _parse_json(str(resp.content))
        reply = str(parsed.get("reply", "")).strip()
        req = parsed.get("shopify_request")
    except Exception:
        return await _agent_reply(agent, message, "You", company)
    if isinstance(req, dict) and req.get("path"):
        from src.org.proposals import execute_shopify
        res = await execute_shopify(req.get("method", "GET"), req["path"], req.get("body"))
        reply = (reply + "\n" if reply else "") + f"→ {req.get('method','GET')} {req['path']}: {res.get('status')} {str(res.get('body',''))[:300]}"
    return reply or "בוצע."


def author_q(message: str) -> str:
    return f'User asked: "{message}"'


_OPS_SYS = """\
You are the operations dispatcher for the Alpha store agents. The owner wrote a
message in chat. Decide if it maps to ONE store-maintenance OPERATION the agent can
RUN right now, or "none" (then the agent just answers / does a normal action).

Operations you can run:
- "dedupe":       remove DUPLICATE products (same item listed more than once).
- "cleanup":      remove products with NO image or a foreign-language / invalid title.
- "apply_design": push the store template LIVE — re-render the homepage (site.json)
                  and product page (product.json) so design/JSON edits take effect.
- "fix_prices":   fix products priced $0 — re-price each $0 variant from its mapped
                  retail price (or remove it if there's no price). Use for "$0 in store".
- "ticket":       close or update a TICKET the owner refers to (mark it done/doing/blocked).
                  Use for "close the ticket ..." / "סגור את הטיקט ..." / "mark X done".

Pick "none" unless the message clearly asks for one of these (in any language).
Output ONLY JSON: {"op":"dedupe|cleanup|apply_design|fix_prices|ticket|none","reply":"<short first-person line in %s>","ticket_query":"<words identifying the ticket, only when op=ticket>","ticket_status":"done|doing|blocked|todo"}"""


async def _agent_act_ops(agent: Agent, message: str, company) -> str | None:
    """Run a REAL store-maintenance operation the owner asked for (dedupe / cleanup /
    apply-design) and report the actual result — so when you tell Devon/Remy 'remove
    the duplicates' they DO it, not just talk. Returns the reply string when an op ran,
    or None to signal the caller to fall back to its normal action."""
    transcript = await _recent_transcript(message)
    human = (f"Recent conversation:\n{transcript}\n\n" if transcript else "") + author_q(message)
    try:
        llm = get_llm("executive", temperature=0.0, max_tokens=300)
        resp = await llm.ainvoke([
            SystemMessage(content=_OPS_SYS % company_language()),
            HumanMessage(content=human),
        ])
        parsed = _parse_json(str(resp.content))
        op = str(parsed.get("op", "none")).strip()
        reply = str(parsed.get("reply", "")).strip()
        ticket_query = str(parsed.get("ticket_query", "")).strip()
        ticket_status = str(parsed.get("ticket_status", "done")).strip()
    except Exception:
        return None
    if op not in {"dedupe", "cleanup", "apply_design", "fix_prices", "ticket"}:
        return None
    # Ticket ops don't need the Shopify store context — handle + return early.
    if op == "ticket":
        from src.org.tickets import list_tickets, update_ticket
        q = ticket_query.lower()
        cand = [t for t in list_tickets() if t["status"] != "done"
                and (q in t["title"].lower() or q in t["id"].lower() or not q)]
        if not cand:
            return (reply + "\n" if reply else "") + f"⚠️ לא מצאתי טיקט פתוח שתואם ל־'{ticket_query}'."
        done = [t for t in cand if update_ticket(t["id"], status=ticket_status or "done")]
        titles = ", ".join(t["title"][:40] for t in done)
        return (reply + "\n" if reply else "") + f"✅ עדכנתי {len(done)} טיקט ל־{ticket_status or 'done'}: {titles}"
    # Make sure the Shopify calls target the store (falls back to env creds anyway).
    try:
        from src.stores import list_stores, _current_store
        store = next(iter(list_stores()), None)
        if store:
            _current_store.set(store)
    except Exception:
        store = None
    slug = "timeforbaby"
    try:
        if op == "dedupe":
            from src.mcp_tools.shopify import dedupe_products
            res = await dedupe_products(dry_run=False)
            note = f"הסרתי {res['deleted']} כפילויות (מתוך {res['duplicate_count']} שזוהו)."
        elif op == "cleanup":
            from src.mcp_tools.shopify import cleanup_bad_products
            res = await cleanup_bad_products(dry_run=False)
            note = f"ניקיתי {res['deleted']} מוצרים פגומים (בלי תמונה / טקסט לא תקין) מתוך {res['scanned']}."
        elif op == "fix_prices":
            from src.mcp_tools.shopify import fix_zero_prices
            res = await fix_zero_prices(dry_run=False)
            note = f"תיקנתי מחירי $0: תמחרתי מחדש {res['repriced']} מוצרים, הסרתי {res['deleted']} ללא מחיר."
        else:  # apply_design
            from src.mcp_tools.shopify_design import apply_site_design, apply_product_design
            r1 = await apply_site_design(slug)
            r2 = await apply_product_design(slug)
            note = f"החלתי את התבנית לייב — דף הבית {'✓' if r1.get('ok') else '✗'}, דף מוצר {'✓' if r2.get('ok') else '✗'}."
    except Exception as exc:
        return (reply + "\n" if reply else "") + f"⚠️ הפעולה נכשלה: {exc}"
    # Log it to the store changelog so nothing is invisible.
    try:
        from src.mcp_tools.design_files import append_changelog
        append_changelog(title=f"{agent.name}: {op} (from chat)", changed=note,
                         by=agent.name, context=f"Owner asked in chat: {message[:120]}")
    except Exception:
        pass
    return (reply + "\n" if reply else "") + "✅ " + note


async def _agent_act_sourcing(agent: Agent, message: str, company) -> str:
    """Hunter ACTS in chat: runs a REAL CJ Dropshipping search and reports the
    candidates with live margins — and, when the owner wants them on the store,
    triggers a real catalog-fill run that lists CJ products to the live Shopify
    store (Devon's pipeline). Not just talk."""
    system = (
        f"You are {agent.name} ({agent.role}) at Alpha — the Product Hunter. You have "
        "FULL DIRECT access to the CJ Dropshipping API and source products yourself; "
        "NEVER say you lack access.\n"
        f"Answer in {company_language()}. From the owner's message decide ONE concrete "
        "CJ search keyword (a specific garment/product type, e.g. 'baby onesie', not a "
        "generic category) and whether he wants the products LISTED to the live store.\n"
        "Output ONLY JSON:\n"
        '{"reply":"<short first-person line>","category":"<concrete CJ search keyword>",'
        '"push_to_store":true|false}'
    )
    transcript = await _recent_transcript(message)
    human = (f"Recent conversation (oldest first):\n{transcript}\n\n" if transcript else "") + author_q(message)
    try:
        llm = get_llm("executive", temperature=0.3, max_tokens=500)
        resp = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=human)])
        parsed = _parse_json(str(resp.content))
        reply = str(parsed.get("reply", "")).strip()
        category = str(parsed.get("category", "")).strip()
        push = bool(parsed.get("push_to_store"))
    except Exception:
        return await _agent_reply(agent, message, "You", company)
    if not category:
        return reply or "On it — searching CJ now."
    try:
        from src.mcp_tools.sourcing import (
            search_trending_products, resolve_category, CJQuotaExceeded,
        )
        resolved = await resolve_category(category)
        products = await search_trending_products(
            category=category,
            category_id=resolved["category_id"] if resolved else "",
            max_results=6, min_margin=0.30, max_price_usd=50.0,
        )
    except CJQuotaExceeded as exc:
        return (reply + "\n" if reply else "") + f"⚠️ CJ daily quota exhausted — {exc}"
    except Exception as exc:
        return (reply + "\n" if reply else "") + f"⚠️ CJ search failed: {exc}"
    if not products:
        return (reply + "\n" if reply else "") + f"No CJ matches for '{category}' right now."
    lines = [
        f"• {p.get('title','')[:48]} — cost ${p.get('price_supplier_usd')} → "
        f"${p.get('estimated_price_shopify_usd')} ({int(p.get('margin_pct', 0) * 100)}% margin)"
        for p in products[:6]
    ]
    out = (reply + "\n" if reply else "") + f"Found {len(products)} CJ products for '{category}':\n" + "\n".join(lines)
    if push:
        try:
            from src.stores import list_stores
            from src.api.routes.agents import _spawn_run
            import uuid
            store = next(iter(list_stores()), None)
            if store:
                tid = f"chat-source-{uuid.uuid4().hex[:8]}"
                _spawn_run(
                    tid,
                    "[MONITOR] Source CJ products and list the approved ones to the store",
                    agent.name, 5.0, store.store_id,
                )
                out += "\n\n🚀 Kicked off a run to list the approved products to the store (Devon will publish them)."
            else:
                out += "\n\n(No active store to publish to yet.)"
        except Exception as exc:
            out += f"\n\n(Couldn't start the publish run: {exc})"
    return out


def _apply_site_changes(changes: list[dict]) -> tuple[bool, list[str]]:
    """Apply Remy's targeted edits to the store's style/site.json (the homepage
    source of truth). Each change is {key, value} where `key` is either a section
    id in the sections list (e.g. 'announcement_marquee', 'hero') or a top-level
    site.json key (e.g. 'design_tokens'); `value` is the COMPLETE new object/array
    for it. Writes through the sandboxed, JSON-validating design-file writer.
    Returns (ok, applied_labels)."""
    from src.mcp_tools.shopify_design import load_site_json
    from src.mcp_tools.design_files import write_design_file, read_store_docs
    site = load_site_json("timeforbaby")
    if not site:
        return False, []
    sections = site.get("sections", [])
    sec_idx = {s.get("id"): i for i, s in enumerate(sections) if isinstance(s, dict)}
    applied: list[str] = []
    for ch in changes or []:
        key = str(ch.get("key", "")).strip()
        if not key or "value" not in ch:
            continue
        if key in sec_idx:
            sections[sec_idx[key]] = ch["value"]
            applied.append(f"section '{key}'")
        elif key in site:
            site[key] = ch["value"]
            applied.append(key)
    if not applied:
        return False, []
    site_path = str(_Path(read_store_docs("timeforbaby").get("dir", "")) / "style" / "site.json")
    res = write_design_file(site_path, json.dumps(site, ensure_ascii=False, indent=2))
    return bool(res.get("ok")), applied


async def _agent_act_design(agent: Agent, message: str, company) -> str:
    """Remy ACTS in chat: edits the store's JSON source of truth (style/site.json)
    and applies it live — the CORRECT path for 'change the announcement bar', hero
    copy, colors, etc. Never touches the live .liquid by hand. Falls back to a plain
    reply if there's no concrete edit to make."""
    site = {}
    try:
        from src.mcp_tools.shopify_design import load_site_json
        site = load_site_json("timeforbaby")
    except Exception:
        pass
    sections_digest = json.dumps(
        [{"id": s.get("id"), "type": s.get("type")} for s in site.get("sections", []) if isinstance(s, dict)],
        ensure_ascii=False,
    )[:600]
    ann = next((s for s in site.get("sections", []) if "announcement" in str(s.get("id", "")).lower()), {})
    system = (
        f"You are {agent.name} ({agent.role}) at Alpha — UX & Content; you OWN the "
        "store look + copy. The store is JSON-driven: style/site.json is the SOURCE OF "
        "TRUTH for the homepage. You edit it and re-apply; NEVER touch the live .liquid "
        "by hand.\n"
        f"Answer in {company_language()}. From the owner's message make the SINGLE most "
        "relevant edit. The announcement bar is the section whose id contains "
        "'announcement' — its scrolling messages live in its `items` array.\n"
        f"Existing sections: {sections_digest}\n"
        f"Current announcement section: {json.dumps(ann, ensure_ascii=False)[:500]}\n"
        "Output ONLY JSON:\n"
        '{"reply":"<short first-person line>","changes":[{"key":"<section id OR '
        'top-level site.json key>","value":<COMPLETE new object/array for it>}],'
        '"changelog":"<one line: what changed, old → new>"}\n'
        "Use changes:[] (empty) if no concrete edit is needed — then just reply."
    )
    transcript = await _recent_transcript(message)
    human = (f"Recent conversation (oldest first):\n{transcript}\n\n" if transcript else "") + author_q(message)
    try:
        llm = get_llm("executive", temperature=0.4, max_tokens=1200)
        resp = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=human)])
        parsed = _parse_json(str(resp.content))
        reply = str(parsed.get("reply", "")).strip()
        changes = parsed.get("changes") or []
        changelog = str(parsed.get("changelog", "")).strip()
    except Exception:
        return await _agent_reply(agent, message, "You", company)
    if not changes:
        return reply or "Noted — no design change needed."
    try:
        ok, applied = _apply_site_changes(changes)
    except Exception as exc:
        return (reply + "\n" if reply else "") + f"⚠️ Couldn't write site.json: {exc}"
    if not ok:
        return (reply + "\n" if reply else "") + "⚠️ No matching site.json section/key to edit — nothing changed."
    # Render it live, then log the change (the store's changelog discipline).
    live_note = ""
    try:
        from src.mcp_tools.shopify_design import apply_site_design
        res = await apply_site_design("timeforbaby")
        live_note = " and applied it live" if res.get("ok") else " (saved; live apply pending)"
    except Exception:
        live_note = " (saved; live apply pending)"
    try:
        from src.mcp_tools.design_files import append_changelog
        append_changelog(
            title=f"{agent.name}: store design edit (chat)",
            changed=changelog or ", ".join(applied),
            by=agent.name, context=f"Owner asked in chat: {message[:140]}",
        )
    except Exception:
        pass
    return (reply + "\n" if reply else "") + f"✏️ Updated {', '.join(applied)} in site.json{live_note}."


async def route_and_respond(message: str, author: str = "You",
                            images: list[str] | None = None) -> list[dict]:
    """Route the message to the RIGHT teammate(s) — not the whole chorus — and
    have only them answer, each as their own Slack identity. If images are
    attached, the responder actually looks at them (Claude vision)."""
    company = get_company()
    agents = list_agents(active_only=True)
    by_role = {a.role: a for a in agents}

    roster = "\n".join(
        f"- {a.name} ({a.role}): {a.skill}" for a in agents
    )
    caption = message or "(no caption)"
    img_note = f"\n[{len(images)} image(s) attached — look at them]" if images else ""
    transcript = await _recent_transcript(message)
    hist_block = (f"RECENT CONVERSATION (oldest first) — the team remembers this, "
                  f"answer in its context:\n{transcript}\n\n" if transcript else "")
    user = (
        f"{hist_block}"
        f"ROSTER:\n{roster}\n\n"
        f"{author} wrote:\n\"{caption}\"{img_note}\n\n"
        "Who answers, and what do they say?"
    )
    try:
        llm = get_llm("executive", temperature=0.7, max_tokens=600)
        sys_prompt = (
            _DISPATCH_SYS
            + f"\nWrite each reply in {company_language()} by default."
            + ("\nImage(s) are attached — the responder should react to what they show." if images else "")
        )
        resp = await llm.ainvoke([
            SystemMessage(content=sys_prompt),
            HumanMessage(content=_human_content(user, images)),
        ])
        parsed = _parse_json(str(resp.content))
        chosen = parsed.get("responders", [])
    except Exception as exc:
        logger.warning("Dispatch failed (%s) — CEO will answer", exc)
        chosen = []

    items: list[tuple[Agent, str]] = []
    for r in chosen[:3]:
        agent = by_role.get(r.get("role", ""))
        reply = (r.get("reply") or "").strip()
        if agent and reply:
            items.append((agent, reply))

    if not items:  # safe fallback: the CEO (or first agent) takes it
        ceo = by_role.get("CEO") or (agents[0] if agents else None)
        if ceo:
            items.append((ceo, await _agent_reply(ceo, message, author, company, images)))

    # Each specialist actually EXECUTES in their domain (full freedom) — not just
    # talk. Devon/Ava → Shopify; Hunter → CJ sourcing; Remy → store design edits.
    # (Skipped when images are attached — then they react to the picture.)
    final: list[tuple[Agent, str]] = []
    for agent, reply in items:
        if not images:
            # First try a real maintenance OP (dedupe/cleanup/apply-design) — so a
            # "remove the duplicates" actually RUNS. Falls through to the role's
            # normal action when the message isn't an op.
            if agent.role in _SHOPIFY_DOERS or agent.role == "UX & Content":
                ran = await _agent_act_ops(agent, message, company)
                if ran is not None:
                    final.append((agent, ran))
                    continue
            if agent.role in _SHOPIFY_DOERS:
                reply = await _agent_act_shopify(agent, message, company)
            elif agent.role == "Product Hunter":
                reply = await _agent_act_sourcing(agent, message, company)
            elif agent.role == "UX & Content":
                reply = await _agent_act_design(agent, message, company)
        final.append((agent, reply))
    return await _post_replies(final)


async def _download_image(url: str, token: str) -> str | None:
    """Download a Slack file (needs the bot token + files:read scope) and return
    it as a base64 data URL for the vision model. None if it can't be read."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        ctype = r.headers.get("content-type", "")
        if r.status_code == 200 and ctype.startswith("image/"):
            return f"data:{ctype};base64,{base64.b64encode(r.content).decode()}"
        logger.warning("Image not readable (status %s, type %s) — is files:read granted?", r.status_code, ctype)
    except Exception as exc:
        logger.warning("Image download failed: %s", exc)
    return None


async def _extract_images(msg: dict, token: str, max_images: int = 3) -> list[str]:
    """Base64 data URLs for image files attached to a Slack message."""
    out: list[str] = []
    for f in (msg.get("files") or [])[:max_images]:
        if str(f.get("mimetype", "")).startswith("image/"):
            url = f.get("url_private_download") or f.get("url_private")
            if url:
                data = await _download_image(url, token)
                if data:
                    out.append(data)
    return out


# ── Optional: read the channel via a bot token (true two-way) ─────────────────

def _bot_token() -> str:
    return os.environ.get("SLACK_BOT_TOKEN", "").strip()


def _channel_id() -> str:
    """The channel ID. Tolerates a pasted Slack URL by extracting the C… id —
    confirmed real: a channel *link* in SLACK_CHANNEL gives `channel_not_found`."""
    raw = os.environ.get("SLACK_CHANNEL", "").strip()
    m = re.search(r"(C[A-Z0-9]{8,})", raw)
    return m.group(1) if m else raw


def two_way_enabled() -> bool:
    return bool(_bot_token() and _channel_id())


async def fetch_and_respond(limit: int = 15) -> list[dict]:
    """Pull the latest human messages from the channel and have agents answer.

    No-op unless SLACK_BOT_TOKEN + SLACK_CHANNEL are configured and the bot is a
    member of that channel (Slack scopes: channels:history, chat:write).
    """
    token, channel = _bot_token(), _channel_id()
    if not (token and channel):
        return []
    if _responding.locked():
        return []  # a reply round is already in flight — let it finish
    async with _responding:
        return await _fetch_and_respond_locked(token, channel, limit)


async def _fetch_and_respond_locked(token: str, channel: str, limit: int) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://slack.com/api/conversations.history",
                headers={"Authorization": f"Bearer {token}"},
                params={"channel": channel, "limit": limit},
            )
        data = resp.json()
    except Exception as exc:
        logger.warning("Slack history fetch failed: %s", exc)
        return []
    if not data.get("ok"):
        logger.warning("Slack history error: %s", data.get("error"))
        return []

    # Newest first → find the most recent real human message. Skip bot posts and
    # system messages, but KEEP image uploads (subtype "file_share") — those were
    # being dropped, which is why an image looked like an "empty message".
    for msg in data.get("messages", []):
        if msg.get("bot_id"):
            continue
        subtype = msg.get("subtype")
        if subtype and subtype != "file_share":
            continue
        text = msg.get("text", "")
        has_files = bool(msg.get("files"))
        if not text and not has_files:
            continue
        ts = msg.get("ts", "")
        if ts and _last_ts.get(channel) == ts:
            return []  # already answered the latest one
        images = await _extract_images(msg, token) if has_files else []
        if has_files and not images:
            # An image was sent but we couldn't open it — tell the agent so it
            # gives a useful answer (usually: the bot needs the files:read scope).
            text = (text + "\n" if text else "") + (
                "[The user attached an image, but the team could not open it — the "
                "Slack bot is likely missing the 'files:read' scope. Politely say you "
                "can see an image was sent but can't open it yet, and ask them to add "
                "that scope.]"
            )
        replies = await route_and_respond(text, author="You", images=images)
        # Mark as answered only AFTER a successful round, so a mid-failure
        # (e.g. litellm not ready yet) doesn't permanently skip the message.
        if replies:
            _last_ts[channel] = ts
        return replies
    return []
