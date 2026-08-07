"""
Two-way chat: each agent answers in their own voice, over Telegram.

`agents_respond(message)` takes a message (yours) and has EVERY active agent
reply in-persona — using their role, skill, recent lessons, and the company
culture — then posts each reply as that agent (src/org/telegram.py). So you
ask one thing and see Ada (CEO), Linus (CTO), Maya (HR)… each answer.

`route_and_respond(message)` is the normal path: it picks only the relevant
teammate(s) instead of the whole chorus, and is what src/org/telegram.py's
bot calls directly the moment one of your Telegram messages arrives (push-
based — no polling involved, unlike the old Slack integration).

All LLM calls are best-effort: if the proxy/model is down, the agent falls back
to a short canned line so the chat still gets a reply.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re

from langchain_core.messages import HumanMessage, SystemMessage

from src.llm import get_llm
from src.org.models import Agent, get_company, list_agents, save_company
from src.org.telegram import post_as, post_to_telegram, show_typing_as, telegram_enabled

logger = logging.getLogger(__name__)

_ROLE_EMOJI = {"CEO": ":crown:", "CTO": ":brain:", "HR": ":office_worker:"}

from pathlib import Path as _Path

_STORES_ROOT = _Path(__file__).resolve().parents[2] / "stores" / "shopify"


def _store_context(store_slug: str = "alphaforbaby") -> str:
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


async def _recent_transcript(exclude_msg: str = "", limit: int = 12) -> str:
    """Recent conversation as a labelled transcript (oldest first), so any reply
    path can feed the agent its memory of what was said. Reads the local message
    feed (src/org/agent_feed.py) rather than a chat API — unlike Slack's REST
    history endpoint, Telegram bots can't fetch arbitrary past channel messages,
    so this is now the single source of truth for "what was said" regardless of
    transport. '' on failure."""
    try:
        from src.org.agent_feed import read_agent_messages
        hist = read_agent_messages(limit + 1)
        if hist and exclude_msg and hist[-1]["text"].strip() == exclude_msg.strip():
            hist = hist[:-1]  # drop a trailing echo of the message we're answering
        # Cap each line so a giant JSON dump (e.g. an applied site.json) can't
        # dominate the context window.
        return "\n".join(f"{h['name']}: {h['text'][:300]}" for h in hist[-limit:])
    except Exception:
        return ""


async def _agent_reply(agent: Agent, message: str, author: str, company,
                       images: list[str] | None = None) -> str:
    system = (
        f"You are {agent.name}, the {agent.role} of Alpha, an autonomous "
        "e-commerce company of AI agents. Stay in character and answer in FIRST "
        "PERSON, 1-3 sentences, concrete and grounded in your role.\n"
        f"Write ALWAYS in {company_language()} (English), even if the message is in Hebrew or another language.\n"
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


async def _post_replies(items: list[tuple[Agent, str]], reply_thread_id: int | None = None) -> list[dict]:
    """Post each (agent, text) AS that agent, spaced for Telegram's rate limit.
    `reply_thread_id` forces the topic these land in (the topic you asked
    from) instead of each agent's own default topic — see post_as."""
    out: list[dict] = []
    for i, (agent, text) in enumerate(items):
        if i > 0:
            await asyncio.sleep(1.1)
        await post_as(agent.name, agent.role, text, thread_override=reply_thread_id)
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

The team is 4 agents — ALWAYS pick the SPECIALIST whose domain the message is
about; do NOT funnel everything to the CEO. Use the EXACT role string:
- "Product Sourcer & Copywriter" (Sol) → ANY mention of CJ / sourcing / finding
  products / prices / margins / "get products" / "add products" / "push products
  to the store" / product copywriting / SEO titles+descriptions. Sol runs his own
  tool loop — actually sources from CJ and pushes to Shopify himself.
- "Video Producer" (Reel)    → ad video generation/status, product video ideas,
  the video review/approve-reject queue.
- "Customer Support" (Nora)  → customer emails/tickets, support inbox questions,
  refund/complaint handling status.
- "CEO" (Ava)                → ONLY strategy/direction/money/vision, a build-or-
  launch decision, or a genuinely ambiguous greeting. NOT the default dumping ground.
If the message NAMES a person (e.g. "Sol, ..."), THAT person answers. When in
doubt between the CEO and a specialist, pick the specialist. For a group greeting
("hi all", "hey team") ALL FOUR must answer, one per line in "responders".

EVERY agent has FULL repo + Shopify access — never route to "ask the owner for
permission". The chosen person reads/does it themselves.

Write each chosen person's reply in FIRST PERSON, 1-3 sentences, ALWAYS in English
(even if the message is in Hebrew). Output ONLY JSON:
{"responders":[{"role":"CEO","reply":"..."}]}"""


# Agents allowed to execute Shopify directly (full freedom, no approval gate).
# Current roster: Sol pushes products via his own tool loop (agent_loop.py) and never
# reaches this path; Ava (CEO) is the one who can act here. Kept as a set (not just a
# single name check) so Devon/a future Shopify-Developer role slots back in for free.
_SHOPIFY_DOERS = {"Shopify Developer", "CEO", "Developer", "CTO"}


async def _agent_act_shopify(agent: Agent, message: str, company) -> str:
    """Let a Shopify doer (currently just Ava/CEO) actually RUN a Shopify call in
    chat (no approval) and report the result, instead of only talking about it."""
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
- "remove_out_of_stock": remove products that are OUT OF STOCK and cannot be purchased
                  (no backorder allowed) — dead listings customers can't check out on.
- "remove_stale": remove products older than 3 years that are NOT baby items — reads
                  each product's title/description to judge relevance before removing.
- "ticket":       CREATE, ADVANCE, or CLOSE a ticket. Create a NEW ticket for a problem/task
                  ("open a ticket to ...", "תפתח טיקט ל..."); or advance/close an EXISTING one
                  ("close the ticket ...", "סגור את הטיקט", "קדם את", "mark X done/doing/blocked").

Pick "none" unless the message clearly asks for one of these (in any language).
Output ONLY JSON: {"op":"dedupe|cleanup|apply_design|fix_prices|remove_out_of_stock|remove_stale|ticket|none","reply":"<short first-person line in %s>","ticket_action":"create|update","ticket_title":"<title, when creating>","ticket_query":"<words identifying an existing ticket, when updating>","ticket_status":"todo|doing|blocked|done"}"""


async def _classify_non_baby(candidates: list[dict]) -> list[str]:
    """LLM judgment pass for the 'remove non-baby products older than 3 years' rule.
    Age is already a hard, deterministic filter applied by the caller (audit_stale_products);
    this only judges baby-relevance from title/type/description — there's no data field
    for that on Shopify, so it needs a read of the actual product copy. Conservative:
    ambiguous/baby-adjacent items are kept."""
    if not candidates:
        return []
    listing = "\n".join(
        f"{i}. id={c['id']} title={c['title']!r} type={c['product_type']!r} desc={c['description'][:120]!r}"
        for i, c in enumerate(candidates)
    )
    system = (
        "You are auditing a BABY products store's catalog. Each numbered item below is "
        "a product older than 3 years. Decide which are CLEARLY NOT baby/infant/toddler "
        "items (e.g. unrelated adult goods, generic non-baby gadgets) and should be "
        "removed. When in doubt, KEEP the product — do not remove anything baby-adjacent "
        "or ambiguous.\n"
        'Output ONLY JSON: {"remove_ids": ["<id>", ...]}'
    )
    try:
        llm = get_llm("executive", temperature=0.0, max_tokens=1000)
        resp = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=listing)])
        parsed = _parse_json(str(resp.content))
        valid_ids = {c["id"] for c in candidates}
        return [i for i in parsed.get("remove_ids", []) if i in valid_ids]
    except Exception:
        return []


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
        ticket_action = str(parsed.get("ticket_action", "update")).strip()
        ticket_title = str(parsed.get("ticket_title", "")).strip()
        ticket_query = str(parsed.get("ticket_query", "")).strip()
        ticket_status = str(parsed.get("ticket_status", "done")).strip()
    except Exception:
        return None
    if op not in {"dedupe", "cleanup", "apply_design", "fix_prices",
                  "remove_out_of_stock", "remove_stale", "ticket"}:
        return None
    # Ticket ops — ANY agent can create / advance / close. No Shopify context needed.
    if op == "ticket":
        from src.org.tickets import list_tickets, update_ticket, open_ticket
        if ticket_action == "create":
            title = ticket_title or ticket_query or message[:80]
            t = open_ticket(title, source="chat", created_by=agent.name)
            if not t:
                return (reply + "\n" if reply else "") + "⚠️ טיקט דומה כבר פתוח."
            return (reply + "\n" if reply else "") + f"✅ פתחתי טיקט '{t.title}' — אחראי {t.assignee}, {t.priority}, deadline {t.due_at[:16]}."
        q = ticket_query.lower()
        cand = [t for t in list_tickets() if t["status"] != "done"
                and (q in t["title"].lower() or q in t["id"].lower() or not q)]
        if not cand:
            return (reply + "\n" if reply else "") + f"⚠️ לא מצאתי טיקט פתוח שתואם ל־'{ticket_query}'."
        upd = [t for t in cand if update_ticket(t["id"], status=ticket_status or "done")]
        return (reply + "\n" if reply else "") + f"✅ עדכנתי {len(upd)} טיקט ל־{ticket_status or 'done'}: " + ", ".join(t["title"][:40] for t in upd)
    # Make sure the Shopify calls target the store (falls back to env creds anyway).
    try:
        from src.stores import list_stores, _current_store
        store = next(iter(list_stores()), None)
        if store:
            _current_store.set(store)
    except Exception:
        store = None
    slug = "alphaforbaby"
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
        elif op == "remove_out_of_stock":
            from src.mcp_tools.shopify import cleanup_out_of_stock_products
            res = await cleanup_out_of_stock_products(dry_run=False)
            note = f"הסרתי {res['deleted']} מוצרים שאזלו מהמלאי ולא ניתנים לרכישה (מתוך {res['scanned']} שנבדקו)."
        elif op == "remove_stale":
            from src.mcp_tools.shopify import audit_stale_products, delete_shopify_product
            audit = await audit_stale_products(max_age_years=3)
            to_remove = await _classify_non_baby(audit["candidates"])
            removed = 0
            for gid in to_remove:
                if await delete_shopify_product(gid):
                    removed += 1
            note = (f"בדקתי {audit['candidate_count']} מוצרים בני 3+ שנים; "
                    f"הסרתי {removed} שאינם מוצרי תינוקות.")
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


async def _agent_act_video(agent: Agent, message: str, company) -> str:
    """Reel ACTS in chat: when asked to make/create/render an ad video OR a
    baby-outfit image, picks a product and kicks off a REAL render (the same
    pipelines as POST /videos/generate and POST /images/generate) instead of just
    talking about it — this was the actual bug: Reel kept replying "I'll select a
    product..." forever without ever starting anything, because no _agent_act_*
    was wired for his role. One intent-classification call decides media type
    (video vs image) plus video style, then delegates to the matching starter."""
    system = (
        f"You are {agent.name} ({agent.role}) at Alpha — Video Producer, and you also "
        "generate product IMAGES two ways. You have FULL access to the store's products "
        "and all pipelines; NEVER say you lack access or ask which product — if the owner "
        "didn't name one, YOU pick it.\n"
        f"Answer in {company_language()}. From the owner's message decide: (1) do they "
        "want you to START something NOW (e.g. 'make a video', 'create an ad', 'make an "
        "image', 'try 10 seconds', 'just take one/any product') versus just chatting; "
        "(2) if starting, is it a full AD VIDEO, a short ROTATION VIDEO, or an IMAGE, and "
        "if an image, which kind.\n"
        "Full ad video (media=video), two formats — pick PRODUCT_3D_SHOWCASE only if the "
        "owner clearly asks for a 3D/product-only/no-face/cinematic style, else default "
        "AVATAR_UGC:\n"
        "- AVATAR_UGC: an avatar talks to camera, benefit captions alongside.\n"
        "- PRODUCT_3D_SHOWCASE: no face, rotating/macro product render, floating title cards.\n"
        "Rotation video (media=rotation_video): a short (~4s) 360-degree turntable clip of "
        "JUST the product (no person, no text) — pick this when the owner asks to 'see it "
        "from every angle', 'spin it around', 'rotate', or a short product-only video. "
        "IMPORTANT: this uses a PAID API (Veo, ~$0.40/clip, NOT the free tier) — you must "
        "say so plainly in your reply and make clear you're only QUEUING it for the owner's "
        "cost approval (dashboard Videos page), not actually spending money yet.\n"
        "For images, pick ONE of three: LIFESTYLE (default — a real, text-free photo of a "
        "baby/toddler actually wearing/using the product, no headline or overlay of any "
        "kind), THREED (a text-free stylized 3D render of the product alone, no person — "
        "pick this when the owner asks for a '3D version', 'product-only', 'no person/face' "
        "image), or BABY_SWAP (the older pipeline that face-swaps a baby into an existing "
        "adult-model photo — only pick this if the owner explicitly asks to reuse/transform "
        "an existing photo with a person already in it, not for a fresh photo). Every image "
        "style is TEXT-FREE — never add a headline, logo, or callouts unless the owner "
        "explicitly asks for an ad banner with text.\n"
        "Output ONLY JSON:\n"
        '{"reply":"<short first-person line>","start_render":true|false,'
        '"media":"video"|"rotation_video"|"image","style":"AVATAR_UGC"|"PRODUCT_3D_SHOWCASE",'
        '"image_style":"LIFESTYLE"|"THREED"|"BABY_SWAP"}'
    )
    transcript = await _recent_transcript(message)
    human = (f"Recent conversation (oldest first):\n{transcript}\n\n" if transcript else "") + author_q(message)
    try:
        llm = get_llm("video_producer", temperature=0.2, max_tokens=300)
        resp = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=human)])
        parsed = _parse_json(str(resp.content))
        reply = str(parsed.get("reply", "")).strip()
        start = bool(parsed.get("start_render"))
        media = str(parsed.get("media", "video")).strip().lower()
        style = str(parsed.get("style", "AVATAR_UGC")).strip().upper()
        if style not in ("AVATAR_UGC", "PRODUCT_3D_SHOWCASE"):
            style = "AVATAR_UGC"
        image_style = str(parsed.get("image_style", "LIFESTYLE")).strip().upper()
        if image_style == "BABY_SWAP":
            engine, gemini_style = "baby_swap", "lifestyle"
        elif image_style == "THREED":
            engine, gemini_style = "gemini", "3d_showcase"
        else:
            engine, gemini_style = "gemini", "lifestyle"
    except Exception:
        return await _agent_reply(agent, message, "You", company)
    if not start:
        return reply or "Got it."
    if media == "image":
        return await _agent_act_image(reply, engine=engine, style=gemini_style)
    if media == "rotation_video":
        return await _agent_act_rotation_video(reply)
    return await _agent_act_video_render(reply, style)


async def _agent_act_video_render(reply: str, style: str) -> str:
    """Starts a real ad-video render (POST /videos/generate) for the store's first
    eligible product — the video half of _agent_act_video's dispatch."""
    from src.mcp_tools.shopify import get_products_for_video
    from src.api.routes.videos import post_generate_video
    from src.stores import list_stores
    try:
        store = next(iter(list_stores()), None)
        if not store:
            return (reply + "\n" if reply else "") + "⚠️ No active store to pick a product from."
        products = await get_products_for_video()
    except Exception as exc:
        return (reply + "\n" if reply else "") + f"⚠️ Couldn't read the store's products: {exc}"
    if not products:
        return (reply + "\n" if reply else "") + "Every eligible product already has a video queued/rendered — nothing new to make one for."
    product = products[0]
    res = await post_generate_video({"store_id": store.store_id, "product_id": product["id"], "style": style})
    if res.get("error"):
        return (reply + "\n" if reply else "") + f"⚠️ Couldn't start rendering: {res['error']}"
    pretty_style = style.replace("_", " ").title()
    return (reply + "\n" if reply else "") + f"🎬 Picked *{product['title']}* — rendering a {pretty_style} ad now (script → Wan2.2 scenes → voiceover → assembly). I'll post it here for approval when it's done."


async def _agent_act_rotation_video(reply: str) -> str:
    """Queues a Veo 360-rotation video for the store's first eligible product —
    COST GATE: this only creates an awaiting_cost_approval row (POST
    /videos/generate, engine='veo_rotation'), it never spends money on its own.
    The owner must separately approve via POST /videos/{id}/approve-render or the
    dashboard's Videos page before the paid Veo call actually fires."""
    from src.mcp_tools.shopify import get_products_for_video
    from src.api.routes.videos import post_generate_video
    from src.video.veo_video import ESTIMATED_COST_USD
    from src.stores import list_stores
    try:
        store = next(iter(list_stores()), None)
        if not store:
            return (reply + "\n" if reply else "") + "⚠️ No active store to pick a product from."
        products = await get_products_for_video()
    except Exception as exc:
        return (reply + "\n" if reply else "") + f"⚠️ Couldn't read the store's products: {exc}"
    if not products:
        return (reply + "\n" if reply else "") + "Every eligible product already has a video queued/rendered — nothing new to make one for."
    product = products[0]
    res = await post_generate_video({"store_id": store.store_id, "product_id": product["id"], "engine": "veo_rotation"})
    if res.get("error"):
        return (reply + "\n" if reply else "") + f"⚠️ Couldn't queue it: {res['error']}"
    return (
        (reply + "\n" if reply else "")
        + f"🔄 Picked *{product['title']}* for a 4s 360° rotation video — but this uses Veo, "
        f"a PAID API (~${ESTIMATED_COST_USD}, not the free tier). I've queued it, nothing "
        f"charged yet. Approve it on the dashboard's Videos page (or POST "
        f"/videos/{res['video_id']}/approve-render) to actually render it."
    )


async def _agent_act_image(reply: str, engine: str = "gemini", style: str = "lifestyle") -> str:
    """Starts a real product image render (POST /images/generate) for the store's
    first eligible product — the image half of _agent_act_video's dispatch.
    `engine='gemini'` (default) is the Gemini pipeline (src/video/gemini_images.py)
    — a clean, text-free photo generated directly from the product's real photo,
    either `style='lifestyle'` (a baby wearing/using it) or `style='3d_showcase'`
    (product-only 3D render, no person). `engine='baby_swap'` is the older Wan2.2
    baby-wearing-the-outfit pipeline. If the picked product's photos don't show an
    adult person (baby_swap only), the background task fails fast with a clear
    reason (see src/api/routes/images.py) rather than silently producing nothing."""
    from src.mcp_tools.shopify import get_products_with_all_images
    from src.api.routes.images import post_generate_image
    from src.stores import list_stores
    try:
        store = next(iter(list_stores()), None)
        if not store:
            return (reply + "\n" if reply else "") + "⚠️ No active store to pick a product from."
        products = await get_products_with_all_images()
    except Exception as exc:
        return (reply + "\n" if reply else "") + f"⚠️ Couldn't read the store's products: {exc}"
    if not products:
        return (reply + "\n" if reply else "") + "Every eligible product already has an image queued/rendered — nothing new to make one for."
    product = products[0]
    res = await post_generate_image({"store_id": store.store_id, "product_id": product["id"], "engine": engine, "style": style})
    if res.get("error"):
        return (reply + "\n" if reply else "") + f"⚠️ Couldn't start rendering: {res['error']}"
    if engine == "gemini":
        kind = "3D showcase render" if style == "3d_showcase" else "baby-lifestyle photo"
    else:
        kind = "baby-outfit image"
    return (reply + "\n" if reply else "") + f"🖼️ Picked *{product['title']}* — rendering a {kind} now. I'll post the original + generated photo here for approval when it's done."


def _apply_site_changes(changes: list[dict]) -> tuple[bool, list[str]]:
    """Apply Remy's targeted edits to the store's style/site.json (the homepage
    source of truth). Each change is {key, value} where `key` is either a section
    id in the sections list (e.g. 'announcement_marquee', 'hero') or a top-level
    site.json key (e.g. 'design_tokens'); `value` is the COMPLETE new object/array
    for it. Writes through the sandboxed, JSON-validating design-file writer.
    Returns (ok, applied_labels)."""
    from src.mcp_tools.shopify_design import load_site_json
    from src.mcp_tools.design_files import write_design_file, read_store_docs
    site = load_site_json("alphaforbaby")
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
    site_path = str(_Path(read_store_docs("alphaforbaby").get("dir", "")) / "style" / "site.json")
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
        site = load_site_json("alphaforbaby")
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
        res = await apply_site_design("alphaforbaby")
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
                            images: list[str] | None = None,
                            reply_thread_id: int | None = None) -> list[dict]:
    """Route the message to the RIGHT teammate(s) — not the whole chorus — and
    have only them answer, each as their own Telegram identity. If images are
    attached, the responder actually looks at them (Claude vision).
    `reply_thread_id` (the Telegram topic the message came from) makes every
    reply land there too, instead of each agent's own default topic."""
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

    # Show "<agent> is typing…" AS EACH responder right now, using their own bot
    # identity — so you see who received your message and is composing a reply
    # BEFORE their (possibly slower — a tool call, a real Shopify/CJ round trip)
    # answer is actually ready, not just a flash right before it lands.
    for agent, _ in items:
        try:
            await show_typing_as(agent.name, reply_thread_id)
        except Exception:
            pass

    # Each specialist actually EXECUTES in their domain (full freedom) — not just
    # talk. Devon/Ava → Shopify; Hunter → CJ sourcing; Remy → store design edits.
    # (Skipped when images are attached — then they react to the picture.)
    final: list[tuple[Agent, str]] = []
    for agent, reply in items:
        # Sol (the sole autonomous builder) runs the FULL tool-use loop — codes,
        # builds, deploys, sources from CJ — narrating each step to Telegram itself.
        # Passes any attached image (e.g. a mobile-bug screenshot) so he sees + fixes it.
        if agent.name == "Sol":
            from src.org.agent_loop import run_sol_task
            try:
                # narrate=True → Sol posts every step AND its final summary to
                # Telegram itself (say(resp.content)). Do NOT append to `final` —
                # _post_replies would post the summary a SECOND time. That double
                # post was the "Sol replies twice" bug.
                await run_sol_task(message, narrate=True, images=images, reply_thread_id=reply_thread_id)
            except Exception as exc:  # noqa: BLE001
                await post_as(agent.name, agent.role, f"Got stuck: {exc}")
            continue
        if not images:
            # First try a real OP — ticket create/advance/close (ANY agent) or a store
            # maintenance op (dedupe/cleanup/fix-prices/apply-design). So "open a ticket"
            # / "close the ticket" / "remove the duplicates" actually RUN. Falls through
            # to the role's normal action when the message isn't an op.
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
            elif agent.role == "Video Producer":
                reply = await _agent_act_video(agent, message, company)
        final.append((agent, reply))
    return await _post_replies(final, reply_thread_id=reply_thread_id)


# ── Two-way status ───────────────────────────────────────────────────────────
# Under Slack, two-way chat meant POLLING conversations.history for new human
# messages. Telegram is push-based instead: src/org/telegram.py's Application
# gets each of your messages handed to it directly and calls route_and_respond()
# itself the moment it arrives — there is nothing left to poll.
def two_way_enabled() -> bool:
    return telegram_enabled()
