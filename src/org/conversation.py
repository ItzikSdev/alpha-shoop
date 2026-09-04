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
from src.org.models import Agent, get_company, list_agents
from src.org.telegram import post_as, post_to_telegram, show_typing_as, telegram_enabled
from src.tracing import agent_log

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


def _capability_block(exclude: str = "") -> str:
    """The team's capability directory (src/org/directory.py), best-effort — a
    prompt must still render if the roster lookup hiccups."""
    try:
        from src.org.directory import capability_directory
        return capability_directory(exclude=exclude)
    except Exception:  # noqa: BLE001
        return "(teammate directory unavailable)"


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
    English). They still switch to match a message that's clearly in another
    language.

    Read through Settings, not os.environ: `.env` is never loaded into the
    process environment, so the old os.environ read could only ever return its
    own default and silently ignored ORG_LANGUAGE=English."""
    from src.config import get_settings
    try:
        return get_settings().org_language.strip() or "English"
    except Exception:  # noqa: BLE001
        return os.environ.get("ORG_LANGUAGE", "English").strip() or "English"


def _parse_json(text: str) -> dict:
    # Strip qwen3's reasoning block first. It's a REASONING model, so its raw
    # output can be "<think>…</think>{json}" — and any brace inside that prose
    # (it often drafts the JSON there) would otherwise be what the regex below
    # locks onto, yielding a half-written object instead of the real answer.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"^.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)  # unclosed/truncated
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
        # Who else is on the team and what they can actually RUN. Without this an
        # agent only ever saw its own charter, so it couldn't hand anything over
        # or even say accurately who owns a problem.
        f"YOUR TEAMMATES — refer people to the right one by name:\n"
        f"{_capability_block(agent.name)}\n"
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

The team is several specialist agents — ALWAYS pick the SPECIALIST whose domain
the message is about; do NOT funnel everything to the CEO. Use the EXACT role string:
- "Product Sourcer & Copywriter" (Sol) → ANY mention of CJ / sourcing / finding
  products / prices / margins / "get products" / "add products" / "push products
  to the store" / product copywriting / SEO titles+descriptions. Sol runs his own
  tool loop — actually sources from CJ and pushes to Shopify himself.
- "Video Producer" (Reel)    → ad video generation/status, product video ideas,
  the video review/approve-reject queue.
- "Customer Support" (Nora)  → customer emails/tickets, support inbox questions,
  refund/complaint handling status.
- "Growth Marketing Analyst" (Kai) → TikTok Ads Manager data — spend, ROAS, CTR,
  impressions, conversions, campaign performance, connecting/authorizing TikTok
  Ads, or pasting back a TikTok auth code. ALSO Microsoft Clarity data — site
  traffic/visitor counts, session recordings, heatmaps, rage/dead clicks,
  scroll depth, UX friction/drop-off. Read-only reporting only — Kai never
  creates or edits a campaign, and never edits the site based on a UX finding
  himself (that's a ticket for whoever owns the code).
- "CEO" (Ava)                → ONLY strategy/direction/money/vision, a build-or-
  launch decision, or a genuinely ambiguous greeting. NOT the default dumping ground.
If the message NAMES a person (e.g. "Sol, ..."), THAT person answers. When in
doubt between the CEO and a specialist, pick the specialist. For a group greeting
("hi all", "hey team") EVERY agent above must answer, one per line in "responders".

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
        "needs a Shopify call, include it. Two ways to make one — pick whichever fits:\n"
        '- shopify_graphql: {"query":"<GraphQL query/mutation>","variables":{...}} — '
        "use this for ANY lookup/search (e.g. \"does a product with this title exist\"): "
        'query { products(first: 5, query: "title:*Foo*") { nodes { id title } } }. '
        "Shopify's REST API has NO product-search-by-title endpoint — don't invent one.\n"
        '- shopify_request: {"method":"GET|POST|PUT|DELETE","path":"<e.g. products/count.json>",'
        '"body":<obj or null>} — for simple REST calls by a KNOWN Shopify id.\n'
        "CRITICAL: a CJ supplier product id (from product_mappings/RAG, often 16-19 digits) "
        "is NEVER a Shopify product id (Shopify's are shorter, ~10-13 digits) — never call "
        "products/{id}.json with a CJ id, you'll get a false 404 and wrongly conclude the "
        "product doesn't exist. Look it up by title/handle via shopify_graphql instead. "
        "Only one of shopify_graphql/shopify_request should be set (or neither). "
        "Output ONLY JSON: {\"reply\":\"<short first-person reply>\","
        '"shopify_graphql":null OR {...},"shopify_request":null OR {...}}'
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
        gql = parsed.get("shopify_graphql")
    except Exception:
        return await _agent_reply(agent, message, "You", company)
    if isinstance(gql, dict) and gql.get("query"):
        from src.org.proposals import execute_shopify_graphql
        res = await execute_shopify_graphql(gql["query"], gql.get("variables"))
        reply = (reply + "\n" if reply else "") + f"→ graphql: {res.get('status')} {str(res.get('body',''))[:300]}"
    elif isinstance(req, dict) and req.get("path"):
        from src.org.proposals import execute_shopify
        res = await execute_shopify(req.get("method", "GET"), req["path"], req.get("body"))
        reply = (reply + "\n" if reply else "") + f"→ {req.get('method','GET')} {req['path']}: {res.get('status')} {str(res.get('body',''))[:300]}"
    return reply or "Done."


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
                  ("open a ticket to ..."); or advance/close an EXISTING one
                  ("close the ticket ...", "mark X done/doing/blocked"). A message that
                  literally starts with "create_ticket:" or "close_ticket:" (an agent's own
                  self-directed decision, e.g. Nova's, not owner chat) is ALWAYS this op —
                  don't require it to read like a natural sentence; everything after the
                  colon is the ticket_title (create) or ticket_query (close/advance).

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
                return (reply + "\n" if reply else "") + "⚠️ A similar ticket is already open."
            return (reply + "\n" if reply else "") + f"✅ Opened ticket '{t.title}' — assignee {t.assignee}, {t.priority}, deadline {t.due_at[:16]}."
        q = ticket_query.lower()
        cand = [t for t in list_tickets() if t["status"] != "done"
                and (q in t["title"].lower() or q in t["id"].lower() or not q)]
        if not cand:
            return (reply + "\n" if reply else "") + f"⚠️ No open ticket found matching '{ticket_query}'."
        upd = [t for t in cand if update_ticket(t["id"], status=ticket_status or "done")]
        return (reply + "\n" if reply else "") + f"✅ Updated {len(upd)} ticket(s) to {ticket_status or 'done'}: " + ", ".join(t["title"][:40] for t in upd)
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
            note = f"Removed {res['deleted']} duplicate(s) (of {res['duplicate_count']} found)."
        elif op == "cleanup":
            from src.mcp_tools.shopify import cleanup_bad_products
            res = await cleanup_bad_products(dry_run=False)
            note = f"Cleaned up {res['deleted']} bad product(s) (no image / invalid title) out of {res['scanned']}."
        elif op == "fix_prices":
            from src.mcp_tools.shopify import fix_zero_prices
            res = await fix_zero_prices(dry_run=False)
            note = f"Fixed $0 prices: repriced {res['repriced']} product(s), removed {res['deleted']} with no price."
        elif op == "remove_out_of_stock":
            from src.mcp_tools.shopify import cleanup_out_of_stock_products
            res = await cleanup_out_of_stock_products(dry_run=False)
            note = f"Removed {res['deleted']} out-of-stock product(s), unpurchasable (out of {res['scanned']} checked)."
        elif op == "remove_stale":
            from src.mcp_tools.shopify import audit_stale_products, delete_shopify_product
            audit = await audit_stale_products(max_age_years=3)
            to_remove = await _classify_non_baby(audit["candidates"])
            removed = 0
            for gid in to_remove:
                if await delete_shopify_product(gid):
                    removed += 1
            note = (f"Checked {audit['candidate_count']} product(s) 3+ years old; "
                    f"removed {removed} that aren't baby items.")
        else:  # apply_design
            from src.mcp_tools.shopify_design import apply_site_design, apply_product_design
            r1 = await apply_site_design(slug)
            r2 = await apply_product_design(slug)
            note = f"Applied the template live — homepage {'✓' if r1.get('ok') else '✗'}, product page {'✓' if r2.get('ok') else '✗'}."
    except Exception as exc:
        return (reply + "\n" if reply else "") + f"⚠️ Operation failed: {exc}"
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
    parsed = await _classify_with_retry(agent, system, human, model_role="executive",
                                        temperature=0.3, max_tokens=800)
    if parsed is None:
        agent_log(f"⚠️ {agent.name}: sourcing classifier failed twice — fell back to "
                  "generic reply, no action taken", "warning")
        return await _agent_reply(agent, message, "You", company)
    reply = str(parsed.get("reply", "")).strip()
    category = str(parsed.get("category", "")).strip()
    push = bool(parsed.get("push_to_store"))
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


async def _classify_with_retry(
    agent: Agent, system: str, human: str, model_role: str = "executive",
    temperature: float = 0.3, max_tokens: int = 800,
) -> dict | None:
    """Run a classifier call (system+human → parsed JSON) with ONE retry on
    failure, /no_think appended so a reasoning model (qwen3) doesn't burn its
    whole token budget on a <think> block before ever writing the JSON —
    exactly the failure mode that made _agent_act_video silently substitute a
    plain chat reply for a real render: max_tokens=300, no /no_think, and the
    response got cut off mid-string with no start_render/media/style fields.

    Returns the parsed dict, or None if BOTH attempts failed to produce
    parseable JSON. None is a real failure a caller must surface loudly (see
    each _agent_act_*'s fallback-to-_agent_reply site) — it is NOT the same
    thing as "nothing to do", which the classifier expresses inside its own
    JSON (e.g. start_render:false), not by failing to parse."""
    human_nt = human if human.rstrip().endswith("/no_think") else human + " /no_think"
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            llm = get_llm(model_role, temperature=temperature, max_tokens=max_tokens)
            resp = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=human_nt)])
            raw = str(resp.content).strip()
            if not raw:
                raise ValueError("model returned an empty response")
            return _parse_json(raw)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning("%s classifier attempt %d/2 failed: %s", agent.name, attempt + 1, exc)
    logger.warning("%s classifier failed after retry, giving up: %s", agent.name, last_exc)
    return None


async def _agent_act_video(agent: Agent, message: str, company) -> str:
    """Reel ACTS in chat: when asked to make/create/render a video OR a
    baby-outfit image, picks a product and kicks off a REAL render (the same
    pipelines as POST /videos/generate and POST /images/generate) instead of just
    talking about it. One intent-classification call decides media type (rotation
    video vs image) plus image style, then delegates to the matching starter.

    The old full-ad-video path (AVATAR_UGC / PRODUCT_3D_SHOWCASE, Wan2.2/ComfyUI)
    is retired as of 2026-08-20 — the owner deleted Wan2.2 (render quality wasn't
    good enough, switched to paying for Veo/Gemini instead). Veo's wrapper
    (src/video/veo_video.py) is purpose-built for one fixed 4s no-person rotation
    shot, not a drop-in for a multi-scene scripted talking-avatar ad — replacing
    the ad-video pipeline would be a real rebuild, not a redirect, so that video
    type is disabled here rather than silently routed to a pipeline that can't
    actually produce it."""
    system = (
        f"You are {agent.name} ({agent.role}) at Alpha — Video Producer, and you also "
        "generate product IMAGES two ways. You have FULL access to the store's products "
        "and all pipelines; NEVER say you lack access or ask which product — if the owner "
        "didn't name one, YOU pick it. You do NOT have a scripted/talking-avatar ad-video "
        "pipeline anymore (that was Wan2.2, retired) — only a short rotation video and "
        "images. If the owner asks for a talking-avatar or full ad video, say plainly "
        "that pipeline was retired and offer a rotation video or image instead.\n"
        "You also have a READ-ONLY status check (no render) for 'does this product "
        "already have a video/enough images', 'is it published', 'what's its media "
        "status' type questions — use check_status for those instead of guessing "
        "or saying you'll look into it.\n"
        f"Answer in {company_language()}. From the owner's message decide: (0) is this "
        "a STATUS/CHECK question about EXISTING media (check_status=true, name/infer "
        "the product) rather than a request to make something new; (1) if not a status "
        "question, do they want you to START something NOW (e.g. 'make a video', 'spin "
        "it around', 'make an image', 'just take one/any product') versus just chatting; "
        "(2) if starting, is it a ROTATION VIDEO or an IMAGE, and if an image, which kind.\n"
        "Rotation video (media=rotation_video): a short (~4s) 360-degree turntable clip of "
        "JUST the product (no person, no text) — pick this for any video request. "
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
        '{"reply":"<short first-person line>","check_status":true|false,'
        '"start_render":true|false,'
        '"media":"rotation_video"|"image",'
        '"image_style":"LIFESTYLE"|"THREED"|"BABY_SWAP"}'
    )
    transcript = await _recent_transcript(message)
    human = (f"Recent conversation (oldest first):\n{transcript}\n\n" if transcript else "") + author_q(message)
    parsed = await _classify_with_retry(agent, system, human, model_role="video_producer",
                                        temperature=0.2, max_tokens=800)
    if parsed is None:
        agent_log(f"⚠️ {agent.name}: video classifier failed twice — fell back to "
                  "generic reply, no action taken", "warning")
        return await _agent_reply(agent, message, "You", company)
    reply = str(parsed.get("reply", "")).strip()
    if parsed.get("check_status"):
        gid = _extract_product_gid(message)
        if not gid:
            from src.mcp_tools.shopify import get_products_for_video
            try:
                products = await get_products_for_video()
                product, _err = _resolve_target_product(message, products)
                gid = product["id"] if product else None
            except Exception:
                gid = None
        if not gid:
            return (reply + "\n" if reply else "") + "⚠️ Couldn't identify which product to check."
        from src.mcp_tools.shopify import check_media_status
        status = await check_media_status(gid)
        if status.get("error"):
            return (reply + "\n" if reply else "") + f"⚠️ Status check failed: {status['error']}"
        gap = ("no gap — clears the storefront gate" if status["clears_storefront_gate"]
               else "; ".join(status["publish_blockers"]))
        return (
            (reply + "\n" if reply else "")
            + f"📋 *{status['title']}* — {status['image_count']} image(s), "
            f"{status['video_count_real']} real video(s)"
            + (f", {status['video_count_supplier_clip']} supplier clip(s)"
               if status['video_count_supplier_clip'] else "")
            + f". Gap: {gap}"
        )
    start = bool(parsed.get("start_render"))
    media = str(parsed.get("media", "rotation_video")).strip().lower()
    image_style = str(parsed.get("image_style", "LIFESTYLE")).strip().upper()
    if image_style == "BABY_SWAP":
        engine, gemini_style = "baby_swap", "lifestyle"
    elif image_style == "THREED":
        engine, gemini_style = "gemini", "3d_showcase"
    else:
        engine, gemini_style = "gemini", "lifestyle"
    if not start:
        return reply or "Got it."
    if media == "image":
        return await _agent_act_image(message, reply, engine=engine, style=gemini_style)
    return await _agent_act_rotation_video(message, reply)


def _extract_product_gid(message: str) -> str:
    """Pull an explicit Shopify product gid out of a request, e.g. an
    ask_teammate question naming exactly which product to generate media
    for. Only a full gid counts — a bare number is too ambiguous (could be
    a CJ PID, a price, anything) to match against."""
    m = re.search(r"gid://shopify/Product/\d+", message)
    return m.group(0) if m else ""


def _resolve_target_product(message: str, products: list[dict]) -> tuple[dict | None, str]:
    """Which product a media request targets. If the request named an
    explicit gid, it MUST match exactly — no name/first-match fallback.
    That fallback is what silently substituted the wrong product before:
    asked to generate a video for one gid, it queued one for an unrelated
    "first eligible" product instead and reported the requested name back
    as if it had used it. Returns (product, error); product is None with a
    message in error when a named gid isn't in the eligible list at all —
    that must surface as a loud failure, not a silent substitution."""
    gid = _extract_product_gid(message)
    if not gid:
        return (products[0] if products else None), ""
    for p in products:
        if p.get("id") == gid:
            return p, ""
    return None, f"product not found: {gid} (not in the eligible list — check it exists and has an image)"


def _extract_auth_code(message: str) -> str:
    """Pull a TikTok OAuth `auth_code` out of a chat message — either an
    explicit `auth_code=...` (pasted straight from the redirect URL) or, if
    the whole message is one bare token-looking string with no spaces, that."""
    m = re.search(r"auth_code=([\w\-.]+)", message)
    if m:
        return m.group(1)
    stripped = message.strip()
    if stripped and " " not in stripped and len(stripped) > 10:
        return stripped
    return ""


async def _ads_export_report() -> str:
    """Format the newest hand-exported Ads Manager report, or "" if there is
    none. Used while the TikTok Developer app is still pending approval — the
    Marketing API needs an OAuth access token for every call, so this file is
    the only route to the numbers the owner already sees in his browser."""
    from src import tiktok_mcp
    try:
        data = await tiktok_mcp.read_ads_export()
    except Exception as exc:  # noqa: BLE001
        logger.warning("TikTok export read failed: %s", exc)
        return ""
    if not isinstance(data, dict) or data.get("error"):
        return ""

    m = data.get("metrics", {}) or {}
    d = data.get("derived", {}) or {}
    span = (f" ({data['start_date']} → {data['end_date']})"
            if data.get("start_date") else "")
    lines = [f"TikTok Ads{span} — from your export `{data.get('file')}` "
             f"({data.get('rows_counted')} rows). API isn't connected yet, so these are "
             "read straight out of the file you downloaded:"]
    for key, label, fmt in (
        ("spend", "Spend", "${:,.2f}"), ("impressions", "Impressions", "{:,.0f}"),
        ("clicks", "Clicks", "{:,.0f}"), ("conversions", "Conversions", "{:,.0f}"),
        ("revenue", "Purchase value", "${:,.2f}"),
    ):
        if key in m:
            lines.append(f"  {label}: {fmt.format(m[key])}")
    for key, label, fmt in (
        ("ctr_pct", "CTR", "{:.2f}%"), ("cpc", "CPC", "${:,.3f}"),
        ("cpm", "CPM", "${:,.2f}"), ("cpa", "CPA", "${:,.2f}"), ("roas", "ROAS", "{:.2f}x"),
    ):
        if key in d:
            lines.append(f"  {label}: {fmt.format(d[key])}")
    if "roas" not in d:
        lines.append("  ROAS: not in this export — add 'Total purchase value' to the "
                     "report columns in Ads Manager and re-export.")

    # Per-ad ranking — the actual decision the owner needs ("which creative do I
    # put more money behind?"), which an account-level total can't answer.
    ads = data.get("ads") or []
    if ads:
        lines.append(f"\nPer-{data.get('grouped_by') or 'ad'} — ranked by "
                     f"{data.get('ranking_metric')}:")
        for i, row in enumerate(ads, 1):
            am, ad_ = row.get("metrics", {}), row.get("derived", {})
            bits = []
            if "spend" in am:
                bits.append(f"spend ${am['spend']:,.2f}")
            for key, label, fmt in (("roas", "ROAS", "{:.2f}x"), ("cpa", "CPA", "${:,.2f}"),
                                    ("ctr_pct", "CTR", "{:.2f}%")):
                if key in ad_:
                    bits.append(f"{label} {fmt.format(ad_[key])}")
            if "conversions" in am:
                bits.append(f"{am['conversions']:,.0f} conv")
            lines.append(f"  {i}. {row['ad']} — " + " · ".join(bits))
        best = data.get("best_ad")
        if best:
            lines.append(f"\n✅ Put the budget behind: **{best}** — it wins on "
                         f"{data.get('ranking_metric')}.")
            worst = data.get("worst_ad")
            if worst and worst != best:
                lines.append(f"❌ Weakest right now: {worst}.")
        if len(ads) < 2:
            lines.append("(Only one ad in this export — export a range covering both "
                         "ads if you want them compared.)")
    return "\n".join(lines)


async def _agent_act_ads(agent: Agent, message: str, company) -> str:
    """Kai ACTS in chat: pulls REAL TikTok Ads data (src/tiktok_mcp, a genuine
    MCP client, see that folder's README) instead of talking about it —
    read-only, never creates/edits/pauses a campaign. If TikTok isn't
    connected yet, says so plainly (with the connect steps) rather than
    guessing a number; if the message looks like it's handing back an
    auth_code, completes the OAuth exchange instead of running a report."""
    from datetime import datetime, timedelta, timezone
    from src import tiktok_mcp

    try:
        status = await tiktok_mcp.auth_status()
    except Exception as exc:
        return f"⚠️ Couldn't reach the TikTok Ads MCP server: {exc}"

    if not status.get("authenticated"):
        code = _extract_auth_code(message)
        if code:
            try:
                result = await tiktok_mcp.complete_auth(code)
            except Exception as exc:
                return f"⚠️ TikTok auth exchange failed: {exc}"
            if result.get("authenticated"):
                return (f"✅ TikTok Ads connected (advertiser {result.get('advertiser_ids')}). "
                        "Ask me for spend/CTR/ROAS any time.")
            return f"⚠️ TikTok auth exchange failed: {result.get('error', result)}"
        # Before admitting defeat: the owner can export the exact report he sees
        # in his browser out of Ads Manager, and that needs no app approval. Real
        # numbers from his own account beat "I'm not connected yet".
        export = await _ads_export_report()
        if export:
            return export

        try:
            login = await tiktok_mcp.login()
        except Exception as exc:
            return f"TikTok Ads isn't connected yet, and I couldn't start OAuth: {exc}"
        try:
            where = (await tiktok_mcp.ads_export_status()).get("export_dir", "data/tiktok_exports")
        except Exception:  # noqa: BLE001
            where = "data/tiktok_exports"
        manual = ("\n\nMeanwhile, if you don't want to wait for app approval: export the "
                  f"report from Ads Manager and drop the CSV in `{where}` — I'll read the "
                  "real numbers straight out of it.")
        if "error" in login:
            return f"TikTok Ads isn't connected yet — {login['error']}{manual}"
        return (
            "TikTok Ads isn't connected yet — I have no real data to give you. "
            "One-time setup: open this, approve access, then send me back the "
            f"`auth_code` from the redirect URL:\n{login['authorize_url']}{manual}"
        )

    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=7)
    try:
        report = await tiktok_mcp.get_ads_report(str(start), str(end))
    except Exception as exc:
        return f"⚠️ TikTok report fetch failed: {exc}"
    if "error" in report:
        return f"⚠️ TikTok report fetch failed: {report['error']}"
    rows = report.get("rows", [])
    if not rows:
        return f"TikTok Ads ({start} to {end}): no data returned for the account yet."
    m = rows[0].get("metrics", rows[0])
    lines = [f"TikTok Ads — last 7 days ({start} to {end}):"]
    for key, label in (
        ("spend", "Spend"), ("impressions", "Impressions"), ("clicks", "Clicks"),
        ("ctr", "CTR"), ("conversion", "Conversions"), ("cost_per_conversion", "CPA"),
    ):
        if key in m:
            lines.append(f"  {label}: {m[key]}")
    return "\n".join(lines)


# Keywords that route a Growth Marketing Analyst message to the Clarity/UX
# report instead of the TikTok Ads report — checked before falling through to
# ads (the existing default), so "how's spend looking" still goes to TikTok
# unchanged, but "how's the site traffic / any UX friction" goes to Clarity.
_CLARITY_KEYWORDS = (
    "clarity", "heatmap", "session record", "rage click", "dead click",
    "scroll depth", "site traffic", "web traffic", "visitors", "bounce",
    "ux friction", "user experience", "drop off", "drop-off",
)


async def _agent_act_growth(agent: Agent, message: str, company) -> str:
    """Kai's single entry point for both real data sources he has: TikTok Ads
    (spend/CTR/ROAS) and Clarity (site traffic + UX-friction signals). Keyword
    routing on the incoming message, not a guess — defaults to ads (the
    original, longer-standing behavior) when nothing Clarity-specific is
    mentioned."""
    low = message.lower()
    if any(kw in low for kw in _CLARITY_KEYWORDS):
        return await _agent_act_analytics(agent, message, company)
    return await _agent_act_ads(agent, message, company)


async def _agent_act_analytics(agent: Agent, message: str, company) -> str:
    """Kai ACTS in chat: pulls REAL Microsoft Clarity data (Data Export API,
    src/mcp_tools/clarity.py) — real session/traffic counts and UX-friction
    signals (dead clicks, rage clicks, excessive scroll), never a guessed or
    invented number. If no CLARITY_API_TOKEN is configured, says so plainly
    with the exact setup step rather than pretending to have data."""
    from src.mcp_tools.clarity import get_clarity_report

    result = await get_clarity_report(days=3)
    status = result.get("status")
    if status == "not_connected":
        return f"Clarity isn't connected yet — {result['setup']}"
    if status == "error":
        return f"⚠️ Clarity report fetch failed: {result.get('detail')}"

    summary = result.get("summary") or {}
    if not summary:
        return (
            "Clarity is connected, but I couldn't find any of the metrics I "
            "normally report in this response (its response shape may have "
            "changed — see src/mcp_tools/clarity.py's field-name caveat). "
            f"Raw data has {len(result.get('raw') or [])} metric(s) — ask me to "
            "dig into the raw payload if you want it."
        )

    lines = ["Clarity — last 3 days (real session-recording data):"]
    if "sessions" in summary:
        lines.append(f"  Sessions: {summary['sessions']}")
    if "distinct_users" in summary:
        lines.append(f"  Distinct visitors: {summary['distinct_users']}")
    friction = []
    for key, label in (
        ("dead_clicks", "Dead clicks"), ("rage_clicks", "Rage clicks"),
        ("excessive_scroll_sessions", "Excessive-scroll sessions"),
        ("quickback_clicks", "Quickback clicks"), ("script_errors", "Script errors"),
    ):
        if key in summary:
            friction.append(f"  {label}: {summary[key]}")
    if friction:
        lines.append("UX friction signals:")
        lines.extend(friction)
        # Interpretation stays a plain observation of the real numbers just
        # printed above, not a claim about a cause not in the data.
        if summary.get("rage_clicks", 0) > 0 or summary.get("dead_clicks", 0) > 0:
            lines.append(
                "  → Rage/dead clicks mean visitors clicked something that "
                "didn't respond the way they expected — worth a look at which "
                "page in the Clarity dashboard, not something I can pinpoint "
                "from these totals alone."
            )
    return "\n".join(lines)


def _org_docs_context() -> str:
    """Nova's grounding context — the two root docs (DECISIONS_LOG: what's
    already been diagnosed/tried; VISION_ROADMAP: current phase + the explicit
    out-of-scope/deferred list), read fresh every call (they're small, and
    stale grounding is worse than a file read). Empty string if neither exists
    yet — never blocks the turn."""
    from src.mcp_tools.org_docs import read_org_docs
    docs = read_org_docs()
    parts = []
    if docs.get("decisions_log"):
        parts.append(
            "=== docs/DECISIONS_LOG.md (what's already been diagnosed/tried — "
            "newest entry first; do NOT re-suggest something already tried today) ===\n"
            + docs["decisions_log"]
        )
    if docs.get("vision_roadmap"):
        parts.append(
            "=== docs/VISION_ROADMAP.md (current phase + the EXPLICITLY OUT-OF-SCOPE/"
            "deferred list; never propose anything on that list as a current move) ===\n"
            + docs["vision_roadmap"]
        )
    return "\n\n".join(parts)


async def _agent_act_nova(agent: Agent, message: str, company) -> str:
    """Nova ACTS in chat: answers grounded in the two org-context docs
    (docs/DECISIONS_LOG.md, docs/VISION_ROADMAP.md — read_org_docs) so she never
    re-suggests something already tried today or something explicitly deferred,
    and runs a REAL web search (Serper, src/mcp_tools/market.py) for outside
    context our own store/CJ data can't give — competitor pricing, marketing
    trends, industry benchmarks. Strictly read-only: this only INFORMS a
    create_ticket/record_lesson/flag_blocker, it grants no new action power."""
    docs_context = _org_docs_context()
    system = (
        f"You are {agent.name} ({agent.role}) at Alpha. {docs_context}\n\n"
        "Answer the owner's message using the two docs above as grounding — cite the "
        "specific fact you're relying on (e.g. what DECISIONS_LOG says the current "
        "blocker is, or what VISION_ROADMAP lists as out of scope) rather than "
        "answering generically. Do NOT re-suggest anything DECISIONS_LOG already "
        "shows was tried today, and do NOT propose anything on VISION_ROADMAP's "
        "explicitly-out-of-scope/deferred list as a current move.\n"
        "Separately, decide ONE concrete web search query that would pull real "
        "OUTSIDE information relevant to the message (competitor pricing, a "
        "marketing trend, an industry benchmark) — leave it empty if no outside "
        "lookup would actually help; most status/strategy questions don't need one.\n"
        f"Answer in {company_language()}. Output ONLY JSON:\n"
        '{"reply":"<your grounded answer, citing the doc fact(s) you used>",'
        '"query":"<concrete web search query, or empty>"}'
    )
    transcript = await _recent_transcript(message)
    human = (f"Recent conversation (oldest first):\n{transcript}\n\n" if transcript else "") + author_q(message)
    parsed = await _classify_with_retry(agent, system, human, model_role="executive",
                                        temperature=0.2, max_tokens=900)
    if parsed is None:
        agent_log(f"⚠️ {agent.name}: Nova classifier failed twice — fell back to "
                  "generic reply, no action taken", "warning")
        return await _agent_reply(agent, message, "You", company)
    reply = str(parsed.get("reply", "")).strip()
    query = str(parsed.get("query", "")).strip()
    if not query:
        return reply or "Nothing to look up outside for this one."
    try:
        from src.mcp_tools.market import search_web
        results = await search_web(query)
    except Exception as exc:
        return (reply + "\n" if reply else "") + f"⚠️ Web search failed: {exc}"
    hits = results.get("results", [])
    if not hits:
        return (reply + "\n" if reply else "") + f"No web results for '{query}'."
    lines = [
        f"• {h.get('title', '')[:70]} — {h.get('snippet', '')[:120]} ({h.get('link', '')})"
        for h in hits[:5]
    ]
    out = (reply + "\n" if reply else "") + f"Web search — '{query}':\n" + "\n".join(lines)
    if results.get("answer_box"):
        out += f"\n\nQuick answer: {results['answer_box']}"
    return out


async def _agent_act_rotation_video(message: str, reply: str) -> str:
    """Queues a Veo 360-rotation video for the requested product (exact gid
    match if the request named one — see _resolve_target_product) or the
    store's first eligible product otherwise. COST GATE: this only creates an
    awaiting_cost_approval row (POST /videos/generate, engine='veo_rotation'),
    it never spends money on its own. The owner must separately approve via
    POST /videos/{id}/approve-render or the dashboard's Videos page before the
    paid Veo call actually fires."""
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
    product, err = _resolve_target_product(message, products)
    if err:
        return (reply + "\n" if reply else "") + f"⚠️ {err}"
    if not product:
        return (reply + "\n" if reply else "") + "Every eligible product already has a video queued/rendered — nothing new to make one for."
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


async def _agent_act_image(message: str, reply: str, engine: str = "gemini", style: str = "lifestyle") -> str:
    """Starts a real product image render (POST /images/generate) for the
    requested product (exact gid match if the request named one — see
    _resolve_target_product) or the store's first eligible product otherwise —
    the image half of _agent_act_video's dispatch.
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
    product, err = _resolve_target_product(message, products)
    if err:
        return (reply + "\n" if reply else "") + f"⚠️ {err}"
    if not product:
        return (reply + "\n" if reply else "") + "Every eligible product already has an image queued/rendered — nothing new to make one for."
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
    parsed = await _classify_with_retry(agent, system, human, model_role="executive",
                                        temperature=0.4, max_tokens=1200)
    if parsed is None:
        agent_log(f"⚠️ {agent.name}: design classifier failed twice — fell back to "
                  "generic reply, no action taken", "warning")
        return await _agent_reply(agent, message, "You", company)
    reply = str(parsed.get("reply", "")).strip()
    changes = parsed.get("changes") or []
    changelog = str(parsed.get("changelog", "")).strip()
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
            # The hand-written routing table above lists roles but not what each
            # agent can actually run, and drifts whenever the roster or tools
            # change. Append the live directory so routing is based on real
            # current capability.
            + "\n\nLIVE CAPABILITY DIRECTORY (authoritative — generated from the "
              "real roster and tool catalog; prefer it over the summary above if "
              f"they ever disagree):\n{_capability_block()}"
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
            elif agent.role == "Growth Marketing Analyst":
                reply = await _agent_act_growth(agent, message, company)
            elif agent.role == "Nova":
                reply = await _agent_act_nova(agent, message, company)
        final.append((agent, reply))
    return await _post_replies(final, reply_thread_id=reply_thread_id)


# ── Agent → agent delegation ─────────────────────────────────────────────────
# Until now every one of these execution paths could ONLY be reached by a human
# writing in Telegram: route_and_respond was the sole caller. That meant the CEO
# had no way to hand work to anyone — her whole action menu was build/hire/goal —
# so she set the same goal every hour instead of managing. This is the missing
# link: one teammate hands a concrete task to another and it actually RUNS,
# through the exact same handlers your own messages go through.


async def dispatch_to_agent(name: str, task: str, requested_by: str = "Ava",
                            return_reply: bool = False) -> str:
    """Hand `task` to the teammate called `name` (name OR role) and let them DO it.

    No router LLM call — the caller already chose who. Returns a short
    human-readable result line for the action log.

    `return_reply=True` returns the teammate's OWN answer instead of that log line
    — what their model actually said after running their tools. That's what makes
    this a conversation rather than a fire-and-forget assignment: the agent who
    asked can read the answer and act on it. Never fabricate a reply here; if the
    teammate produced nothing, say so and let the asker deal with it."""
    agents = list_agents(active_only=True)
    target = name.strip().lower()
    agent = next(
        (a for a in agents if a.name.lower() == target or a.role.lower() == target), None
    )
    if agent is None:
        roster = ", ".join(a.name for a in agents)
        return f"assign skipped — no teammate named {name!r} (roster: {roster})"
    if agent.name.lower() == requested_by.strip().lower():
        return f"assign skipped — {requested_by} tried to assign to themselves"

    # Explicitly re-scope tracing to the TARGET agent before any LLM call this
    # dispatch makes. Without this, every downstream call (Sol's tool loop, the
    # _agent_act_* handlers) inherited whatever current_thread_id/current_node
    # was last set by an unrelated prior tick — confirmed via llm_calls: Milo's
    # own turn-shaped prompts were showing up filed under heartbeat-CEO,
    # heartbeat-Video Producer, heartbeat-Growth Marketing Analyst threads that
    # had nothing to do with Milo, purely because those threads' contextvar
    # values were still ambient from whatever ran right before. dispatch_to_agent
    # is the shared hub nearly everything routes through, so fixing it here
    # covers the calls _agent_take_turn's own thread-scoping (set by its
    # callers) doesn't reach.
    from src.tracing import current_node, current_thread_id
    current_thread_id.set(f"heartbeat-{agent.role}")
    current_node.set(f"agent:{agent.role}")

    company = get_company()
    message = f"{requested_by} asked you to do this now: {task}"

    # Record it so /manager and the next standup show a REAL current task instead
    # of "(nothing assigned)" for everyone.
    def _note_task(a: Agent, task: str = task, by: str = requested_by) -> None:
        a.memory["assigned_task"] = f"{task} (from {by})"
    try:
        from src.org.models import update_agent
        update_agent(agent.agent_id, _note_task)
    except Exception:  # noqa: BLE001
        pass  # bookkeeping must never block the actual work

    # Sol is a real tool-using agent — he runs the full loop and narrates himself.
    if agent.name == "Sol":
        from src.org.agent_loop import run_sol_task
        # Log the ASSIGNED edge before attempting the run, not after — every path
        # below this point `return`s (success AND exception), so a log_delegation
        # call placed after the try/except (like the shared one further down this
        # function) would NEVER run for a Sol target. This was silently dropping
        # every Reel/Kai/etc → Sol delegation from the knowledge graph even when
        # the ask and Sol's run both genuinely happened. The delegation itself is
        # true regardless of whether Sol's run then succeeds or fails, so it's
        # logged unconditionally here rather than duplicated in both branches.
        try:
            from src.graph.knowledge_graph import log_delegation
            await log_delegation(requested_by, agent.name, task)
        except Exception:  # noqa: BLE001
            pass
        try:
            result = await run_sol_task(message, store_slug="alphaforbaby", narrate=True, max_steps=20)
            if return_reply:
                # run_sol_task's "final" is his model's closing message.
                return str((result or {}).get("final") or "(Sol finished without a closing answer)")
            return f"assign({agent.name}): {task[:70]}"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Delegated task to Sol failed: %s", exc)
            return f"assign({agent.name}) FAILED: {exc}"

    try:
        reply = await _agent_act_ops(agent, message, company)
        if reply is None:
            if agent.role in _SHOPIFY_DOERS:
                reply = await _agent_act_shopify(agent, message, company)
            elif agent.role == "Video Producer":
                reply = await _agent_act_video(agent, message, company)
            elif agent.role == "Growth Marketing Analyst":
                reply = await _agent_act_growth(agent, message, company)
            elif agent.role == "Product Hunter":
                reply = await _agent_act_sourcing(agent, message, company)
            elif agent.role == "UX & Content":
                reply = await _agent_act_design(agent, message, company)
            elif agent.role == "Nova":
                reply = await _agent_act_nova(agent, message, company)
            else:
                # No specialist execution path (e.g. Nora, whose real work is the
                # inbox poll) — they still answer in-persona so the hand-off is visible.
                reply = await _agent_reply(agent, message, requested_by, company)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Delegated task to %s failed: %s", agent.name, exc)
        return f"assign({agent.name}) FAILED: {exc}"

    if reply:
        await _post_replies([(agent, reply)])

    # Draw the hand-off in the knowledge graph so the org chart is visible at
    # http://localhost:3002 — before agent→agent delegation existed there was
    # no ASSIGNED edge to draw, which is part of why the graph only ever showed
    # Sol running tools. Best-effort: never let observability break the work.
    try:
        from src.graph.knowledge_graph import log_delegation
        await log_delegation(requested_by, agent.name, task)
    except Exception:  # noqa: BLE001
        pass
    if return_reply:
        # The asker gets what the teammate's model actually said — including
        # "nothing", which is real information (a silent agent is a problem to
        # report, not something to paper over with a synthetic answer).
        return reply or f"{agent.name} ({agent.role}) ran the task but said nothing back"
    return f"assign({agent.name}): {task[:70]}"


# ── Two-way status ───────────────────────────────────────────────────────────
# Under Slack, two-way chat meant POLLING conversations.history for new human
# messages. Telegram is push-based instead: src/org/telegram.py's Application
# gets each of your messages handed to it directly and calls route_and_respond()
# itself the moment it arrives — there is nothing left to poll.
def two_way_enabled() -> bool:
    return telegram_enabled()
