"""
Telegram — the company's chat interface (replaces Slack).

Two directions:
  1. OUT — every agent action/message (post_as, Sol's tool-by-tool narration,
     meeting recaps, hires, rendered video review) is pushed to Telegram, the
     same role Slack used to play. `post_as` routes verbose tool-call/result
     lines to a separate "log" topic (TELEGRAM_LOG_THREAD_ID) when configured,
     so the main topic stays readable.
  2. IN — a python-telegram-bot Application polls Telegram for messages and
     feeds them straight into the real orchestrator, `route_and_respond`
     (src/org/conversation.py) — the same entry point Slack's two-way chat
     used to call. Plain chat messages are answered from anyone writing
     inside the ONE configured company chat (TELEGRAM_CHAT_ID), not just the
     owner — see `_is_group_message`. Commands (/agents, /manager, /report)
     and the media approve/reject buttons stay locked to TELEGRAM_ALLOWED_USER_ID
     (`_is_authorized`) since those touch production/publish state.

Setup:
  1. Message @BotFather on Telegram → /newbot → get the token → TELEGRAM_BOT_TOKEN.
  2. Message @userinfobot (or send /start to @get_id_bot) → it replies with
     your numeric id → TELEGRAM_ALLOWED_USER_ID. Only messages from this user
     id are read; everyone else is silently ignored.
  3. Send your bot ANY message first (Telegram won't let a bot message you
     until you've messaged it), then set TELEGRAM_CHAT_ID to that same chat —
     for a 1:1 DM with the bot this is the same number as your user id.
  4. Optional — a supergroup with Topics enabled: set TELEGRAM_MAIN_THREAD_ID
     for concise status updates and TELEGRAM_LOG_THREAD_ID for verbose
     tool-call/result logs, so the two stay visually separate. Get a topic's
     id by opening it and checking the invite link (.../c/<chat>/<thread_id>),
     or forward a message from it to @userinfobot.

Best-effort throughout, mirroring the old Slack module: if TELEGRAM_BOT_TOKEN
or TELEGRAM_CHAT_ID is unset, every outbound call is a silent no-op so the
autonomous loop never depends on Telegram being configured.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import re

from src.org.agent_feed import log_message, read_agent_messages  # noqa: F401  (re-exported)

logger = logging.getLogger(__name__)

_TELEGRAM_MSG_LIMIT = 4096
_SEND_CHUNK = 3800  # buffer under the hard limit for the header/formatting we add


# ── Config ───────────────────────────────────────────────────────────────────
def _token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


def _chat_id() -> str:
    return os.environ.get("TELEGRAM_CHAT_ID", "").strip()


def _thread_id(env_var: str) -> int | None:
    raw = os.environ.get(env_var, "").strip()
    return int(raw) if raw.lstrip("-").isdigit() else None


def _main_thread_id() -> int | None:
    return _thread_id("TELEGRAM_MAIN_THREAD_ID")


def _log_thread_id() -> int | None:
    return _thread_id("TELEGRAM_LOG_THREAD_ID")


def _allowed_user_id() -> int | None:
    raw = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "").strip()
    return int(raw) if raw.lstrip("-").isdigit() else None


def telegram_enabled() -> bool:
    return bool(_token() and _chat_id())


def _agent_token(name: str) -> str:
    """A per-agent bot token if provided — a genuinely separate Telegram bot/
    identity for that agent (own name + avatar in the chat), e.g.
    TELEGRAM_BOT_TOKEN_AVA. Falls back to the shared TELEGRAM_BOT_TOKEN —
    same pattern Slack used for per-agent identities."""
    per = os.environ.get(f"TELEGRAM_BOT_TOKEN_{name.upper()}", "").strip()
    return per or _token()


_bots: dict[str, object] = {}  # token -> lazily-built telegram.Bot, one per identity in use


def _get_bot(token: str | None = None):
    from telegram import Bot
    token = token or _token()
    bot = _bots.get(token)
    if bot is None:
        bot = Bot(token=token)
        _bots[token] = bot
    return bot


# ── Formatting ───────────────────────────────────────────────────────────────
# Slack-style :shortcode: emoji still used by callers (agent_loop.py, heartbeat.py,
# etc.) — converted to real Unicode so they render on Telegram. Unmatched codes are
# stripped, same behavior as Slack's own _clean_slack_text used to have.
_EMOJI_MAP = {
    "gear": "⚙️", "white_check_mark": "✅", "x": "❌", "warning": "⚠️",
    "hammer_and_wrench": "🛠️", "alarm_clock": "⏰", "wave": "👋",
    "busts_in_silhouette": "👥", "crown": "👑", "brain": "🧠",
    "office_worker": "🧑‍💼", "mega": "📣", "mag": "🔍", "art": "🎨",
    "clapper": "🎬", "loudspeaker": "📢", "hammer": "🔨",
}


def _emoji(text: str) -> str:
    return re.sub(r":([a-z0-9_+\-]+):", lambda m: _EMOJI_MAP.get(m.group(1), ""), text or "")


# Tool-call/result narration (agent_loop.py's _short_args/_result_line) always
# starts with one of these — route it to the log topic, keep the main topic
# readable (opener/thought/status/warning lines have no such prefix).
_LOG_LINE_PREFIXES = ("⚙️", "✅", "❌", ":gear:", ":white_check_mark:", ":x:")


def _is_log_line(text: str) -> bool:
    return (text or "").strip().startswith(_LOG_LINE_PREFIXES)


def _split_message(text: str, limit: int = _SEND_CHUNK) -> list[str]:
    """Chunk `text` under Telegram's 4096-char message cap, preferring to break
    on a line boundary so code blocks/lists don't get sliced mid-line when avoidable."""
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit)
        if cut < limit * 0.4:  # no reasonable line break — hard cut
            cut = limit
        parts.append(remaining[:cut])
        remaining = remaining[cut:].lstrip("\n")
    if remaining:
        parts.append(remaining)
    return parts


# ── Outbound send ────────────────────────────────────────────────────────────
async def _send_chunk(chunk: str, thread_id: int | None, token: str | None = None) -> bool:
    from telegram.constants import ParseMode
    from telegram.error import BadRequest, RetryAfter, TelegramError
    bot = _get_bot(token)
    try:
        await bot.send_message(chat_id=_chat_id(), text=chunk, message_thread_id=thread_id,
                                parse_mode=ParseMode.MARKDOWN)
        return True
    except RetryAfter as exc:
        await asyncio.sleep(exc.retry_after + 0.2)
        try:
            await bot.send_message(chat_id=_chat_id(), text=chunk, message_thread_id=thread_id,
                                    parse_mode=ParseMode.MARKDOWN)
            return True
        except TelegramError as exc2:
            logger.warning("Telegram send failed after rate-limit wait: %s", exc2)
            return False
    except BadRequest:
        # Dynamic text (file paths, JSON args, prices) often has unbalanced
        # markdown entities — fall back to plain text so delivery never fails
        # just because formatting couldn't parse.
        try:
            await bot.send_message(chat_id=_chat_id(), text=chunk, message_thread_id=thread_id)
            return True
        except TelegramError as exc:
            logger.warning("Telegram send failed (plain-text fallback): %s", exc)
            return False
    except TelegramError as exc:
        logger.warning("Telegram send failed: %s", exc)
        return False


async def _simulate_typing(text: str, thread_id: int | None, token: str | None = None) -> None:
    """A brief 'typing…' flash before a message lands, so every agent feels
    like a person composing a reply rather than a bot instantly dumping text.
    Best-effort — a failed chat-action call never blocks the actual send."""
    from telegram.constants import ChatAction
    try:
        await _get_bot(token).send_chat_action(chat_id=_chat_id(), message_thread_id=thread_id, action=ChatAction.TYPING)
    except Exception:
        pass
    # Telegram's own typing indicator lasts ~5s; scale the pause with message
    # length so short pings feel snappy and longer messages feel genuinely typed.
    await asyncio.sleep(min(2.5, max(0.5, len(text) / 140)))


async def _send(text: str, thread_id: int | None, token: str | None = None) -> bool:
    if not telegram_enabled() or not text:
        return False
    text = _emoji(text)
    ok = True
    for i, chunk in enumerate(_split_message(text)):
        if i > 0:
            await asyncio.sleep(0.4)  # keep chunked sends well under Telegram's rate limit
        await _simulate_typing(chunk, thread_id, token)
        ok = await _send_chunk(chunk, thread_id, token) and ok
    return ok


async def post_to_telegram(text: str) -> bool:
    """Post a plain company message (no per-agent identity) to the main topic."""
    return await _send(text, thread_id=_main_thread_id())


async def show_typing_as(name: str, thread_id: int | None = None) -> None:
    """Fire ONE 'typing…' chat action AS this agent's own bot identity, right
    now — so you see who received your message and is composing a reply
    BEFORE their answer is actually ready (a tool call or another LLM round
    trip can take several seconds). Best-effort, never raises."""
    from telegram.constants import ChatAction
    try:
        await _get_bot(_agent_token(name)).send_chat_action(
            chat_id=_chat_id(), message_thread_id=thread_id, action=ChatAction.TYPING)
    except Exception:
        pass


# A little visual identity per role so the chat reads like distinct people, not
# a wall of identical bold headers. Matched by keyword since roles are free text
# (e.g. "Product Sourcer & Copywriter") — falls back to a generic 🤖 otherwise.
_ROLE_ICONS = (
    ("ceo", "👑"), ("cto", "🧠"), ("hr", "🧑‍💼"), ("market", "📣"),
    ("sourc", "🛒"), ("copy", "🛒"), ("shopify", "🛠️"), ("develop", "🛠️"),
    ("design", "🎨"), ("ux", "🎨"), ("video", "🎬"), ("support", "🎧"),
    ("build", "🏗️"), ("fulfill", "📦"), ("finance", "💰"), ("content", "🎨"),
)


def _icon_for_role(role: str) -> str:
    low = (role or "").lower()
    return next((icon for key, icon in _ROLE_ICONS if key in low), "🤖")


def _topic_creator_token() -> str:
    """Ava creates the topics (she's the one with 'Manage Topics' admin rights
    in the group) — falls back to the main shared bot if Ava has no dedicated
    token configured."""
    return _agent_token("Ava")


async def _get_or_create_agent_topic(name: str) -> int | None:
    """Each agent gets its OWN forum topic (auto-created on first use via
    Ava's bot, which must be a group admin with 'Manage Topics'), persisted on
    the Company record (company.daemon['agent_topics']) so it's only created
    once. General is reserved for meeting/status recaps (post_to_telegram),
    never per-agent chatter. None if topics aren't usable (not a forum-mode
    group, Ava not admin, etc.) — callers fall back to the plain main topic."""
    from src.org.models import Company, get_company, update_company
    company = get_company()
    if not company:
        return None
    topics = company.daemon.get("agent_topics", {})
    existing = topics.get(name)
    if existing:
        return existing
    try:
        topic = await _get_bot(_topic_creator_token()).create_forum_topic(chat_id=_chat_id(), name=name)
        thread_id = topic.message_thread_id
        def _save_topic(c: Company, name: str = name, thread_id: int = thread_id) -> None:
            topics = c.daemon.setdefault("agent_topics", {})
            topics[name] = thread_id
            c.daemon["agent_topics"] = topics
        update_company(_save_topic)
        return thread_id
    except Exception as exc:
        logger.warning("Couldn't create a Telegram topic for %s: %s", name, exc)
        return None


_UNSET = object()  # distinguishes "no thread_override given" from "override = None (General)"


async def post_as(name: str, role: str, text: str, thread_override=_UNSET) -> bool:
    """Post AS a specific agent. Default destination is THEIR OWN topic
    (auto-created — see _get_or_create_agent_topic); pass `thread_override`
    to force a specific topic instead (None means General specifically) —
    used for REPLIES, so an answer lands wherever you asked (General ->
    General, an agent's topic -> that topic) rather than always redirecting
    into that agent's default topic. If TELEGRAM_BOT_TOKEN_<NAME> is set,
    this is also a REAL separate Telegram bot — its own name + avatar in the
    chat's member list, like a distinct person (same pattern Slack used for
    per-agent tokens). Otherwise falls back to the shared bot with a text
    header. A configured log topic still wins for tool-call/result narration
    over either of the above, so verbose noise can be centralized."""
    log_message(name, role, text)  # local feed first — independent of Telegram delivery
    if _is_log_line(text) and _log_thread_id() is not None:
        thread = _log_thread_id()
    elif thread_override is not _UNSET:
        thread = thread_override  # may legitimately be None -> General
    else:
        thread = await _get_or_create_agent_topic(name)
        if thread is None:
            thread = _main_thread_id()  # topics unusable — fall back to the plain main topic
    token = _agent_token(name)
    body = text or ""
    if token == _token():  # no dedicated bot for this agent — the text header IS the identity
        body = f"{_icon_for_role(role)} *{name}*\n_{role}_\n\n" + body
    return await _send(body, thread_id=thread, token=token)


async def post_escalation(name: str, role: str, text: str) -> bool:
    """A GENUINE 'a human needs to look at this' escalation — distinct from the
    routine tool-narration/status pings `post_as` sends into an agent's own
    topic, which you don't necessarily open every day. Lands in the MAIN topic
    instead (same place CEO reports/standups already post), and is prefixed so
    it reads as urgent at a glance rather than blending into routine chatter."""
    body = text if text.strip().startswith("🚨") else f"🚨 *ESCALATION*\n{text}"
    return await post_as(name, role, body, thread_override=_main_thread_id())


async def post_as_role(role: str, text: str) -> bool:
    """Post a message AS whichever active agent currently holds `role`."""
    name = role
    try:
        from src.org.models import list_agents
        holder = next((a for a in list_agents(active_only=True) if a.role.lower() == role.lower()), None)
        if holder:
            name = holder.name
    except Exception:
        pass
    return await post_as(name, role, text)


async def post_hire(name: str, role: str, skill: str, hired_by: str) -> bool:
    """A new teammate introduces THEMSELVES — posted as their own identity."""
    return await post_as(
        name, role,
        f"👋 Hi team, I'm {name} — just joined as {role} (hired by {hired_by}). My job: {skill}",
    )


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
    if not telegram_enabled():
        return False
    lines = [f"👥 *Alpha {kind} meeting*"]
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
    return await post_to_telegram("\n".join(lines))


async def post_video_as(name: str, role: str, file_path: str, caption: str,
                        review_id: str = "") -> str:
    """Upload a local video file to Telegram as a specific agent, for human
    review (the video pipeline's approve/reject gate). Pass `review_id` (the
    ProductVideo id) to attach ✅/❌ buttons that actually decide it. Returns the
    sent message id (stored so a later approve/reject can reference it), or ""
    on failure/not-configured."""
    from pathlib import Path
    if not telegram_enabled():
        logger.info("post_video_as: Telegram not configured — skipping upload")
        return ""
    path = Path(file_path)
    if not path.is_file():
        logger.warning("post_video_as: %s not found", file_path)
        return ""
    from telegram.constants import ParseMode
    from telegram.error import TelegramError
    token = _agent_token(name)
    bot = _get_bot(token)
    full_caption = caption if token != _token() else f"*{name} · {role}*\n{caption}"
    try:
        with path.open("rb") as f:
            msg = await bot.send_video(
                chat_id=_chat_id(), video=f, caption=full_caption[:1024],
                parse_mode=ParseMode.MARKDOWN, message_thread_id=_main_thread_id(),
                reply_markup=review_keyboard("v", review_id) if review_id else None,
            )
        log_message(name, role, f"[video] {caption}")
        return str(msg.message_id)
    except TelegramError as exc:
        logger.warning("post_video_as failed: %s", exc)
        return ""


# ── Inbound: the bot that reads YOUR messages ───────────────────────────────
async def post_photo_group_as(name: str, role: str, image_paths: list[str], caption: str,
                              review_id: str = "") -> str:
    """Upload local image files to Telegram as an album (one message with multiple
    photos), as a specific agent, for human review — Reel's image-pipeline
    approve/reject gate. Posting the original product photo + the generated
    baby-outfit image together lets the owner compare them side by side. Returns
    the first sent message's id (stored so a later approve/reject can reference
    it), or "" on failure/not-configured."""
    from pathlib import Path
    if not telegram_enabled():
        logger.info("post_photo_group_as: Telegram not configured — skipping upload")
        return ""
    paths = [Path(p) for p in image_paths if Path(p).is_file()]
    if not paths:
        logger.warning("post_photo_group_as: none of %s found", image_paths)
        return ""
    from telegram import InputMediaPhoto
    from telegram.constants import ParseMode
    from telegram.error import TelegramError
    token = _agent_token(name)
    bot = _get_bot(token)
    full_caption = caption if token != _token() else f"*{name} · {role}*\n{caption}"
    try:
        files = [p.open("rb") for p in paths]
        try:
            media = [
                InputMediaPhoto(
                    f, caption=full_caption[:1024] if i == 0 else None,
                    parse_mode=ParseMode.MARKDOWN if i == 0 else None,
                )
                for i, f in enumerate(files)
            ]
            messages = await bot.send_media_group(
                chat_id=_chat_id(), media=media, message_thread_id=_main_thread_id(),
            )
        finally:
            for f in files:
                f.close()
        # An album can't carry an inline keyboard (Telegram allows reply_markup on
        # single messages only), so the ✅/❌ buttons ride on a short follow-up
        # message that replies to the album.
        if review_id:
            try:
                await bot.send_message(
                    chat_id=_chat_id(), text="Approve this image for the store?",
                    message_thread_id=_main_thread_id(),
                    reply_to_message_id=messages[0].message_id if messages else None,
                    reply_markup=review_keyboard("i", review_id),
                )
            except TelegramError as exc:
                logger.warning("review buttons for image %s failed: %s", review_id, exc)
        log_message(name, role, f"[photo] {caption}")
        return str(messages[0].message_id) if messages else ""
    except TelegramError as exc:
        logger.warning("post_photo_group_as failed: %s", exc)
        return ""


async def _download_image(bot, file_id: str) -> str | None:
    """Download a Telegram photo/image file and return it as a base64 data URL
    for the vision model (same shape route_and_respond already expects from
    the old Slack image path). None if it can't be read."""
    try:
        tg_file = await bot.get_file(file_id)
        raw = await tg_file.download_as_bytearray()
        return f"data:image/jpeg;base64,{base64.b64encode(bytes(raw)).decode()}"
    except Exception as exc:
        logger.warning("Telegram image download failed: %s", exc)
        return None


async def _extract_images(update, bot, max_images: int = 3) -> list[str]:
    out: list[str] = []
    if update.message and update.message.photo:
        largest = update.message.photo[-1]  # Telegram sends smallest→largest
        data = await _download_image(bot, largest.file_id)
        if data:
            out.append(data)
    if update.message and update.message.document and (update.message.document.mime_type or "").startswith("image/"):
        data = await _download_image(bot, update.message.document.file_id)
        if data:
            out.append(data)
    return out[:max_images]


async def _keep_typing(bot, chat_id, thread_id, stop: asyncio.Event) -> None:
    """Telegram's 'typing…' indicator expires after ~5s — refresh it while the
    orchestrator is still working (which for Sol's full tool loop can be minutes)."""
    from telegram.constants import ChatAction
    while not stop.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, message_thread_id=thread_id, action=ChatAction.TYPING)
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            pass


def _is_authorized(update) -> bool:
    allowed = _allowed_user_id()
    return bool(allowed and update.effective_user and update.effective_user.id == allowed)


def _is_group_message(update) -> bool:
    """True if this message came from inside the ONE configured company chat
    (TELEGRAM_CHAT_ID) — i.e. anyone already in that group/topic, not just the
    owner. Lets teammates other than the owner ask questions in the shared
    channel and get answered, without opening the bot up to arbitrary 1:1 DMs
    from strangers (a stranger's own chat with the bot has a different chat id
    and fails this check)."""
    chat = update.effective_chat
    configured = _chat_id()
    return bool(chat and configured and str(chat.id) == configured)


def _sender_name(update) -> str:
    """Display name for whoever sent this — "You" for the owner (existing
    behavior/history relies on that label), otherwise the Telegram sender's
    own name, so replies address a teammate by name instead of assuming
    they're the owner."""
    if _is_authorized(update):
        return "You"
    user = update.effective_user
    if not user:
        return "Someone in the channel"
    return user.full_name or (f"@{user.username}" if user.username else "Someone in the channel")


# ── Media review: ✅/❌ buttons on everything Reel posts ──────────────────────
# Reel posted every generated image/video to Telegram "for approval", but the bot
# had NO approve path at all — no inline buttons, no callback handler, no
# /approve command. Nine finished videos sat in `pending_review` because the
# owner's approvals had nowhere to land, and the media never reached the store.
# `callback_data` is capped at 64 bytes by Telegram; "v:a:<32-hex>" is 36.

def review_keyboard(kind: str, item_id: str):
    """Inline ✅ Approve / ❌ Reject keyboard for a video ('v') or image ('i')."""
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:
        return None
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"{kind}:a:{item_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"{kind}:r:{item_id}"),
    ]])


async def _handle_review_callback(update, context) -> None:
    """Run the approve/reject the owner tapped, then rewrite the caption with the
    real outcome — including the failure text, so a Shopify attach error is
    visible where the decision was made instead of only in the database."""
    query = update.callback_query
    if query is None:
        return
    if not _is_authorized(update):
        await query.answer("Not authorized", show_alert=True)
        return
    try:
        kind, action, item_id = (query.data or "").split(":", 2)
    except ValueError:
        await query.answer("Malformed button")
        return

    await query.answer("Working…")
    try:
        if kind == "v":
            from src.api.routes.videos import approve_video, reject_video
            result = await (approve_video(item_id) if action == "a" else reject_video(item_id))
        elif kind == "i":
            from src.api.routes.images import approve_image, reject_image
            result = await (approve_image(item_id) if action == "a" else reject_image(item_id))
        else:
            return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Review callback failed for %s %s", kind, item_id)
        result = {"error": str(exc)}

    status = result.get("status") or ""
    err = result.get("error") or ""
    if err:
        note = f"⚠️ {err}"
    elif status == "published":
        note = "✅ Approved — live on the store"
    elif status == "approved":
        note = "✅ Approved, but the Shopify upload failed — retry needed"
    elif status == "rejected":
        note = "❌ Rejected"
    else:
        note = f"status: {status or 'unknown'}"

    base = (query.message.caption if query.message and query.message.caption else "") or ""
    try:
        # Drop the buttons so the same decision can't be submitted twice.
        await query.edit_message_caption(caption=f"{base}\n\n{note}"[:1024], reply_markup=None)
    except Exception:  # noqa: BLE001
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:  # noqa: BLE001
            pass


async def _handle_start(update, context) -> None:
    if not _is_authorized(update):
        return
    lines = ["🤖 Alpha is online. Send me anything — I'll route it to the right teammate.\n"]
    lines += [f"/{cmd} — {desc}" for cmd, desc in _COMMANDS]
    await update.message.reply_text("\n".join(lines))


async def _handle_agents(update, context) -> None:
    """/agents — a plain, instant roster listing (name, role/skill, current
    task). No LLM call, unlike /manager's narrative report — this is just the
    raw facts, so it never fails/stalls even if the LLM proxy is down."""
    if not _is_authorized(update):
        return
    thread_id = _main_thread_id()
    try:
        from src.org.models import list_agents
        agents = list_agents(active_only=True)
    except Exception as exc:
        await _send(f"⚠️ Couldn't load the roster: {exc}", thread_id=thread_id)
        return
    if not agents:
        await _send("No active agents right now.", thread_id=thread_id)
        return
    blocks = [f"👥 *Roster* ({len(agents)})"]
    for a in agents:
        task = a.memory.get("assigned_task") or "_nothing assigned_"
        blocks.append(
            f"{_icon_for_role(a.role)} *{a.name}* — _{a.role}_\n"
            f"What they do: {a.skill}\n"
            f"Right now: {task}"
        )
    await _send("\n\n".join(blocks), thread_id=thread_id)


async def _handle_manager(update, context) -> None:
    """/manager — on-demand CEO status report (the same thing that also fires
    automatically once a day, see src/org/manager.py)."""
    if not _is_authorized(update):
        return
    bot = context.bot
    chat_id = _chat_id() or update.effective_chat.id
    thread_id = _main_thread_id()
    stop = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(bot, chat_id, thread_id, stop))
    try:
        from src.org.manager import post_manager_checkin
        res = await post_manager_checkin(label="Status check-in")
        if not res.get("posted"):
            await _send(f"⚠️ {res.get('note', 'status report failed')}", thread_id=thread_id)
    except Exception as exc:
        logger.exception("/manager command failed")
        await _send(f"⚠️ Something went wrong: {exc}", thread_id=thread_id)
    finally:
        stop.set()
        await typing_task


async def _handle_report(update, context) -> None:
    """/report — on-demand Daily CEO Report from Ava (Revenue, TikTok ad
    spend/ROAS, bottlenecks, executed agent commands). The same thing that
    also fires automatically once a day, see src/telegram/ceo_report.py."""
    if not _is_authorized(update):
        return
    bot = context.bot
    chat_id = _chat_id() or update.effective_chat.id
    thread_id = _main_thread_id()
    stop = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(bot, chat_id, thread_id, stop))
    try:
        from src.telegram.ceo_report import post_daily_ceo_report
        res = await post_daily_ceo_report(label="On-demand CEO report")
        if not res.get("posted"):
            await _send("⚠️ Couldn't post the report.", thread_id=thread_id)
    except Exception as exc:
        logger.exception("/report command failed")
        await _send(f"⚠️ Something went wrong: {exc}", thread_id=thread_id)
    finally:
        stop.set()
        await typing_task


async def _handle_message(update, context) -> None:
    owner = _is_authorized(update)
    if not owner and not _is_group_message(update):
        uid = update.effective_user.id if update.effective_user else "?"
        logger.warning("Ignored Telegram message from unauthorized user id %s", uid)
        return
    text = (update.message.text or update.message.caption or "").strip()
    has_media = bool(update.message.photo or update.message.document)
    if not text and not has_media:
        return

    sender = _sender_name(update)
    bot = context.bot
    chat_id = _chat_id() or update.effective_chat.id
    thread_id = _main_thread_id()
    if thread_id is None and update.message.message_thread_id:
        thread_id = update.message.message_thread_id  # honor the topic you actually wrote in

    log_message(sender, sender, text or "(image)")
    images = await _extract_images(update, bot) if has_media else []
    if has_media and not images and not text:
        text = "[Attached a file I can't read as an image — describe what you need.]"

    stop = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(bot, chat_id, thread_id, stop))
    thinking_msg = None
    try:
        thinking_msg = await bot.send_message(chat_id=chat_id, message_thread_id=thread_id, text="🤔 Thinking…")
    except Exception:
        pass

    try:
        from src.org.conversation import route_and_respond
        # reply_thread_id: answers land wherever you asked (General -> General,
        # an agent's own topic -> that topic), not each agent's default topic.
        replies = await route_and_respond(text, author=sender, images=images, reply_thread_id=thread_id)
        if not replies:
            await _send("(no response — check the litellm proxy is up)", thread_id=thread_id)
    except Exception as exc:
        logger.exception("route_and_respond failed for a Telegram message")
        await _send(f"⚠️ Something went wrong: {exc}", thread_id=thread_id)
    finally:
        stop.set()
        await typing_task
        if thinking_msg is not None:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=thinking_msg.message_id)
            except Exception:
                pass


_COMMANDS = (
    ("agents", "List everyone on the roster + what they're doing now"),
    ("manager", "Ask the manager for a status + next-steps report"),
    ("report", "Ava's Daily CEO Report — revenue, TikTok ads, bottlenecks, agent commands"),
    ("help", "Show this list"),
)


def _build_application():
    from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                              MessageHandler, filters)
    app = Application.builder().token(_token()).build()
    app.add_handler(CommandHandler("start", _handle_start))
    app.add_handler(CommandHandler("help", _handle_start))
    app.add_handler(CommandHandler("agents", _handle_agents))
    app.add_handler(CommandHandler("manager", _handle_manager))
    app.add_handler(CommandHandler("report", _handle_report))
    # ✅/❌ on Reel's media. Registered BEFORE the catch-all message handler so a
    # button tap is handled as a decision, not routed to an agent as chat.
    app.add_handler(CallbackQueryHandler(_handle_review_callback, pattern=r"^[vi]:[ar]:"))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.Document.IMAGE, _handle_message))
    return app


async def _roll_call() -> None:
    """Every active agent checks in with a short greeting when the bot comes
    online — so a (re)start is visible as the whole roster showing up, not
    silence. The CEO manages the team day-to-day (route_and_respond already
    sends ambiguous/strategy messages to them, see _DISPATCH_SYS in
    conversation.py); they check in first here too."""
    try:
        from src.org.models import list_agents
        agents = list_agents(active_only=True)
        agents.sort(key=lambda a: 0 if a.role == "CEO" else 1)
    except Exception:
        logger.warning("Roll call: couldn't load the roster", exc_info=True)
        return
    for i, a in enumerate(agents):
        if i > 0:
            await asyncio.sleep(1.0)
        try:
            ok = await post_as(a.name, a.role, "Hi 👋 — online and ready.")
            if not ok:
                logger.warning("Roll call: %s's greeting did not send", a.name)
        except Exception:
            logger.warning("Roll call: %s's greeting raised", a.name, exc_info=True)


async def start_telegram_bot():
    """Start polling for your messages in the background. No-op (returns None)
    if TELEGRAM_BOT_TOKEN or TELEGRAM_ALLOWED_USER_ID isn't set, OR if Telegram
    can't be reached right now (bad token, DNS hiccup, network blip) — this must
    never take the rest of the app down with it, same best-effort contract Slack
    used to have. Uses logger.warning (not .info) for the lifecycle messages so
    they're visible even when the process hasn't called logging.basicConfig."""
    if not _token():
        logger.warning("TELEGRAM_BOT_TOKEN not set — Telegram bot not started")
        return None
    if not _allowed_user_id():
        logger.warning("TELEGRAM_ALLOWED_USER_ID not set — Telegram bot not started (would accept anyone)")
        return None
    try:
        app = _build_application()
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        from telegram import BotCommand
        await app.bot.set_my_commands([BotCommand(cmd, desc) for cmd, desc in _COMMANDS])
    except Exception:
        logger.warning("Telegram bot failed to start — continuing without it", exc_info=True)
        return None
    logger.warning("Telegram bot polling started")
    asyncio.create_task(_roll_call())

    # Agents with their OWN bot token post under their own identity — and Telegram
    # delivers a button tap to the bot that SENT that message, not to the main
    # one. Reel posts every image/video for review, so without a poller on his
    # token his ✅/❌ buttons were dead: the tap went to a bot nobody was
    # listening to and simply did nothing. Give every per-agent bot a minimal
    # callback-only Application so its buttons actually work.
    #
    # Tracked in a module-level list, NOT as an attribute on `app`:
    # telegram.ext.Application defines __slots__, so assigning a new attribute
    # raises AttributeError and takes the whole server's startup down with it.
    global _agent_callback_apps
    _agent_callback_apps = await _start_agent_callback_apps()
    return app


_agent_callback_apps: list = []  # per-agent callback pollers, for clean shutdown


async def _start_agent_callback_apps() -> list:
    """One tiny polling Application per distinct per-agent bot token, handling
    ONLY review callbacks (no commands, no chat) — those still belong to the
    main bot. Best-effort: a failure here must not stop the app."""
    from telegram.ext import Application, CallbackQueryHandler

    main = _token()
    seen: set[str] = {main}
    apps: list = []
    for name in ("Ava", "Sol", "Reel", "Nora", "Milo", "Kai", "Nova"):
        token = os.environ.get(f"TELEGRAM_BOT_TOKEN_{name.upper()}", "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        try:
            sub = Application.builder().token(token).build()
            sub.add_handler(CallbackQueryHandler(_handle_review_callback, pattern=r"^[vi]:[ar]:"))
            await sub.initialize()
            await sub.start()
            # allowed_updates: only callback_query — these bots must never
            # consume chat messages, which are the main bot's job.
            await sub.updater.start_polling(drop_pending_updates=False,
                                            allowed_updates=["callback_query"])
            apps.append(sub)
            logger.warning("Callback poller started for %s's bot", name)
        except Exception:
            logger.warning("Couldn't start callback poller for %s", name, exc_info=True)
    return apps


async def stop_telegram_bot(app) -> None:
    if app is None:
        return
    # Stop the per-agent callback pollers too — a leftover poller keeps holding
    # getUpdates for that bot and makes the next start fail with a Conflict.
    global _agent_callback_apps
    for sub in _agent_callback_apps:
        try:
            await sub.updater.stop()
            await sub.stop()
            await sub.shutdown()
        except Exception:
            logger.warning("Error stopping an agent callback poller", exc_info=True)
    _agent_callback_apps = []
    try:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
    except Exception:
        logger.exception("Error stopping Telegram bot")
