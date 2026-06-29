"""
Slack channel for the company — where you and all the agents share a feed.

The living company narrates itself into one Slack channel: every meeting posts
its summary + decisions, and every hire announces itself. You sit in that
channel and watch (and steer) the agents like a real team chat.

MVP is one-way (incoming webhook → channel). It is fully best-effort: if
SLACK_WEBHOOK_URL is unset or Slack is unreachable, every call is a silent
no-op, so the autonomous loop never depends on Slack being up.

Setup:
  1. In Slack: create an app → Incoming Webhooks → add to your channel.
  2. Put the webhook URL in `.env` as SLACK_WEBHOOK_URL=https://hooks.slack.com/...

Next step (two-way, not in this MVP): a Slack Events API bot so you can reply in
the channel and the agents act on it — that needs a public bot endpoint + OAuth.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Local persistent log of every agent message (separate from Slack, which is
# best-effort and external). This is what the dashboard reads to show the agents
# talking to each other outside the chat. Append-only JSONL under data/ (a mounted
# volume, so it survives restarts).
_MSG_LOG = Path(__file__).resolve().parents[2] / "data" / "agent_messages.jsonl"


def _log_message(name: str, role: str, text: str) -> None:
    """Best-effort append of one agent message to the local feed."""
    try:
        _MSG_LOG.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": datetime.now(timezone.utc).isoformat(), "name": name, "role": role, "text": text}
        with _MSG_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass  # never let logging break the post


def read_agent_messages(limit: int = 200) -> list[dict]:
    """Most-recent `limit` agent messages (oldest→newest) for the dashboard feed."""
    if not _MSG_LOG.exists():
        return []
    try:
        lines = _MSG_LOG.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []
    out = []
    for ln in lines[-limit:]:
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def _webhook_url() -> str:
    return os.environ.get("SLACK_WEBHOOK_URL", "").strip()


def _channel_id() -> str:
    """Channel id, tolerating a pasted Slack URL (extracts the C… id)."""
    raw = os.environ.get("SLACK_CHANNEL", "").strip()
    m = re.search(r"(C[A-Z0-9]{8,})", raw)
    return m.group(1) if m else raw


def _clean_slack_text(text: str) -> str:
    """Strip Slack markup so the LLM reads clean prose: <url|label>→label,
    <url>→url, :emoji:→removed, &amp;→&."""
    t = text or ""
    t = re.sub(r"<([^|>]+)\|([^>]+)>", r"\2", t)   # <url|label> → label
    t = re.sub(r"<([^>]+)>", r"\1", t)              # <url> → url
    t = re.sub(r":[a-z0-9_+\-]+:", "", t)           # :emoji:
    t = t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return t.strip()


async def fetch_channel_history(limit: int = 12) -> list[dict]:
    """Recent channel messages, OLDEST→NEWEST, so agents reply WITH context instead
    of to a single message in isolation. Returns [{author, text, is_bot}]; [] on any
    failure (caller then behaves as before). Needs channels:history on the bot."""
    ch = _channel_id()
    tok = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    if not (ch and tok):
        return []
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            r = await client.get(
                "https://slack.com/api/conversations.history",
                headers={"Authorization": f"Bearer {tok}"},
                params={"channel": ch, "limit": max(1, min(limit, 50))},
            )
        d = r.json()
        if not d.get("ok"):
            logger.warning("conversations.history failed: %s", d.get("error"))
            return []
    except Exception as exc:
        logger.warning("conversations.history error: %s", exc)
        return []
    out: list[dict] = []
    for m in reversed(d.get("messages", []) or []):   # Slack returns newest-first
        if m.get("subtype") in ("channel_join", "channel_leave"):
            continue
        is_bot = bool(m.get("bot_id") or m.get("username"))
        author = m.get("username") or ("Itzik" if not is_bot else "system")
        text = _clean_slack_text(m.get("text", ""))
        if text:
            out.append({"author": author, "text": text, "is_bot": is_bot})
    return out


def _agent_token(name: str) -> str:
    """A per-agent bot token if provided (truly separate bot identity), e.g.
    SLACK_BOT_TOKEN_ADA. Falls back to the shared SLACK_BOT_TOKEN."""
    per = os.environ.get(f"SLACK_BOT_TOKEN_{name.upper()}", "").strip()
    return per or os.environ.get("SLACK_BOT_TOKEN", "").strip()


def slack_enabled() -> bool:
    return bool(_webhook_url())


# Each role appears in Slack as its own person (distinct name + avatar emoji).
_ROLE_ICON = {
    "CEO": ":crown:",
    "CTO": ":brain:",
    "HR": ":office_worker:",
    "marketer": ":mega:",
    "store_builder": ":hammer_and_wrench:",
    # 5-role autonomous e-commerce flow (docs/prompt.md).
    "Product Hunter": ":mag:",
    "UX & Content": ":art:",
    "Shopify Developer": ":hammer_and_wrench:",
    "Growth Marketer": ":mega:",
}


async def _post_payload(payload: dict) -> bool:
    """POST a webhook payload. Best-effort; retries once on Slack's 429."""
    url = _webhook_url()
    if not url:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 429:
                wait = float(resp.headers.get("retry-after", 1)) + 0.2
                await asyncio.sleep(min(wait, 5))
                resp = await client.post(url, json=payload)
        return resp.status_code == 200
    except Exception as exc:
        logger.warning("Slack post failed: %s", exc)
        return False


async def post_to_slack(text: str) -> bool:
    """Post a plain company message (no per-agent identity)."""
    return await _post_payload({"text": text})


async def post_as(name: str, role: str, text: str) -> bool:
    """Post AS a specific agent — its own name + avatar — so each agent reads as a
    separate person in the channel.

    Preferred path: the bot token's `chat.postMessage` with a per-agent username
    + icon (needs the `chat:write.customize` scope on the Slack app). If a
    per-agent token (SLACK_BOT_TOKEN_<NAME>) is set, the message is sent by that
    agent's OWN bot app — a genuinely separate identity in the member list.
    Falls back to the incoming webhook if no bot token is configured.
    """
    _log_message(name, role, text)  # local feed first — independent of Slack delivery
    icon = _ROLE_ICON.get(role, ":robot_face:")
    username = f"{name} · {role}"
    token = _agent_token(name)
    channel = _channel_id()

    if token and channel:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"channel": channel, "text": text,
                          "username": username, "icon_emoji": icon},
                )
            data = resp.json()
            if data.get("ok"):
                return True
            # Most common: missing scope → username override silently ignored.
            logger.warning("chat.postMessage failed (%s) — falling back to webhook", data.get("error"))
        except Exception as exc:
            logger.warning("chat.postMessage error: %s — falling back to webhook", exc)

    return await _post_payload({"text": text, "username": username, "icon_emoji": icon})


async def post_as_role(role: str, text: str) -> bool:
    """Post a message AS whichever active agent currently holds `role`.

    The pipeline workers (Product Hunter / Shopify Developer / Growth Marketer …)
    don't know their own agent name — they know their role. This looks up the
    active holder of that role from the roster so the message reads as that
    person, and falls back to the bare role label if no one holds it. Best-effort
    like the rest of this module (silent no-op without a webhook/token)."""
    name = role
    try:
        from src.org.models import list_agents
        holder = next(
            (a for a in list_agents(active_only=True) if a.role.lower() == role.lower()),
            None,
        )
        if holder:
            name = holder.name
    except Exception:
        pass
    return await post_as(name, role, text)


def _fmt_decision(d: dict) -> str:
    dtype = d.get("type", "?")
    if dtype == "build_store":
        return f"🏗️ build store · _{d.get('niche', '')}_ (${d.get('budget_usd', 0):.0f})"
    if dtype == "boost_store":
        return f"📈 boost store · {str(d.get('store_id', ''))[:8]} [{d.get('mode', 'MARKETING')}]"
    if dtype == "hire":
        return f"🧑‍💼 hire · *{d.get('role', '')}* — {d.get('skill', '')[:60]}"
    if dtype == "train":
        return f"🎓 train · {d.get('target_role', '')} on _{d.get('topic', '')}_"
    if dtype == "set_goal":
        return f"🎯 goal · {d.get('goal', '')}"
    if dtype == "record_lesson":
        return f"📝 lesson · {d.get('lesson', '')}"
    return f"• {dtype}"


async def post_meeting(kind: str, notes: str, decisions: list[dict], actions: list[str]) -> bool:
    """Post a full meeting recap (summary + decisions + what actually happened)."""
    if not slack_enabled():
        return False
    lines = [f":busts_in_silhouette: *Alpha {kind} meeting*"]
    if notes:
        lines.append(f"> {notes}")
    if decisions:
        lines.append("*Decisions:*")
        lines += [f"  {_fmt_decision(d)}" for d in decisions]
    if actions:
        lines.append("*Done:*")
        lines += [f"  • {a}" for a in actions]
    if not decisions and not actions:
        lines.append("_No actions this cycle._")
    return await post_to_slack("\n".join(lines))


async def post_hire(name: str, role: str, skill: str, hired_by: str) -> bool:
    """A new teammate introduces THEMSELVES — posted as their own identity, so
    a join reads as that person speaking, not a faceless company announcement."""
    return await post_as(
        name, role,
        f":wave: Hi team, I'm {name} — just joined as {role} (hired by {hired_by}). "
        f"My job: {skill}",
    )
