"""
Local persistent log of every message in the company feed (agent replies AND
your own messages to the bot) — independent of whatever chat transport is
wired up (Telegram today, Slack before it). This is what the dashboard reads
to show the agents talking to each other outside the chat, and what the chat
transport reads to reconstruct "recent conversation" context since chat APIs
(Telegram bots especially) generally can't hand back arbitrary channel
history themselves. Append-only JSONL under data/ (a mounted volume, so it
survives restarts).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_MSG_LOG = Path(__file__).resolve().parents[2] / "data" / "agent_messages.jsonl"


def log_message(name: str, role: str, text: str) -> None:
    """Best-effort append of one message (agent OR human) to the local feed."""
    try:
        _MSG_LOG.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": datetime.now(timezone.utc).isoformat(), "name": name, "role": role, "text": text}
        with _MSG_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass  # never let logging break the caller


def read_agent_messages(limit: int = 200) -> list[dict]:
    """Most-recent `limit` messages (oldest→newest) for the dashboard feed."""
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
