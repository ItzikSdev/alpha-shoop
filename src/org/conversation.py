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


async def _agent_reply(agent: Agent, message: str, author: str, company,
                       images: list[str] | None = None) -> str:
    system = (
        f"You are {agent.name}, the {agent.role} of Alpha, an autonomous "
        "e-commerce company of AI agents. Stay in character and answer in FIRST "
        "PERSON, 1-3 sentences, concrete and grounded in your role.\n"
        f"Write in {company_language()} by default; only switch if the message is "
        "clearly in another language, then match it.\n"
        "If image(s) are attached, look at them and respond to what they show.\n"
        f"Your job (skill): {agent.skill}\n"
        f"Company values: {company.culture.get('values', []) if company else []}\n"
        f"Company goals: {company.goals if company else []}\n"
        f"Recent lessons you've learned: {agent.memory.get('lessons', [])[-2:]}"
    )
    caption = message or "(no caption — see the attached image)"
    user = f"{author} wrote in the team channel:\n\"{caption}\"\n\nReply as {agent.name}."
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

Pick by fit: coding / Shopify API / technical "do this on the store" tasks →
Developer (Grace); store strategy/product/build → CTO; hiring/people/culture →
HR; strategy/vision/money/general direction or an ambiguous greeting → CEO.
If the message NAMES a person (e.g. "Grace, ..."), THAT person answers.

Write each chosen person's reply in FIRST PERSON, 1-3 sentences, in the SAME
LANGUAGE as the message (Hebrew → natural Hebrew). Output ONLY JSON:
{"responders":[{"role":"CEO","reply":"..."}]}"""


# Agents allowed to execute Shopify directly (full freedom, no approval gate).
_SHOPIFY_DOERS = {"Developer", "CTO"}


async def _agent_act_shopify(agent: Agent, message: str, company) -> str:
    """Let Grace/Linus actually RUN a Shopify call in chat (no approval) and
    report the result, instead of only talking about it."""
    system = (
        f"You are {agent.name} ({agent.role}) at Alpha. You have FULL DIRECT "
        "Shopify Admin API access — NO approval needed, you act yourself.\n"
        f"Answer in {company_language()}. If the request needs a Shopify call, "
        "include it. Output ONLY JSON:\n"
        '{"reply":"<short first-person reply>","shopify_request":null OR '
        '{"method":"GET|POST|PUT|DELETE","path":"<e.g. products/count.json>","body":<obj or null>}}'
    )
    try:
        role = "developer" if agent.role == "Developer" else "executive"
        llm = get_llm(role, temperature=0.3, max_tokens=900)
        resp = await llm.ainvoke([SystemMessage(content=system),
                                  HumanMessage(content=f"{author_q(message)}")])
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
    user = (
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

    # Grace/Linus actually EXECUTE Shopify (full freedom) rather than just talk.
    final: list[tuple[Agent, str]] = []
    for agent, reply in items:
        if agent.role in _SHOPIFY_DOERS and not images:
            reply = await _agent_act_shopify(agent, message, company)
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
