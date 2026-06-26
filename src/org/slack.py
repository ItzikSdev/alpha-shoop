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
import logging
import os
import re

import httpx

logger = logging.getLogger(__name__)


def _webhook_url() -> str:
    return os.environ.get("SLACK_WEBHOOK_URL", "").strip()


def _channel_id() -> str:
    """Channel id, tolerating a pasted Slack URL (extracts the C… id)."""
    raw = os.environ.get("SLACK_CHANNEL", "").strip()
    m = re.search(r"(C[A-Z0-9]{8,})", raw)
    return m.group(1) if m else raw


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
