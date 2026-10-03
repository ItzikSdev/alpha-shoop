r"""Draft queue for the social agent — the human approval gate lives here.

Lifecycle:  pending --(human approve)--> approved --(publish)--> published
                    \--(human reject / send back)--> rejected
                    \--(human hold)--> held --(approve)--> approved
A failed publish goes back to `approved` with `error` set, so it can be retried.

The MCP tools exposed to agents can create drafts and publish APPROVED drafts.
There is deliberately no agent-callable approve(). JSON file under data/.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

_PATH = Path(os.environ.get("SOCIAL_QUEUE_PATH", Path(__file__).resolve().parents[2] / "data" / "social_queue.json"))

# platform -> allowed kinds
KINDS: dict[str, set[str]] = {
    "facebook": {"text", "link", "photo", "reel"},
    "instagram": {"photo", "reel"},
    "tiktok": {"video"},
}
_NEEDS_MEDIA = {"photo", "reel", "video"}
_DECIDABLE = {"pending", "held"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> list[dict]:
    try:
        items = json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    for d in items:  # drafts written before multi-platform support were Facebook-only
        d.setdefault("platform", "facebook")
        d.setdefault("feedback", "")
    return items


def _save(items: list[dict]) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_PATH)


def add_draft(platform: str, kind: str, message: str, *, link: str = "", media_url: str = "",
              author: str = "social-agent", rationale: str = "") -> dict:
    platform = platform.strip().lower()
    if platform not in KINDS:
        raise ValueError(f"platform must be one of {sorted(KINDS)}")
    if kind not in KINDS[platform]:
        raise ValueError(f"{platform} supports kinds {sorted(KINDS[platform])}, not {kind!r}")
    if not message.strip():
        raise ValueError("message/caption is empty")
    if kind in _NEEDS_MEDIA and not media_url.startswith("https://"):
        raise ValueError(f"{kind} drafts need a PUBLIC https media_url")
    if kind == "link" and not link:
        raise ValueError("link drafts need a link")
    d = {"id": "post_" + uuid.uuid4().hex[:10], "platform": platform, "kind": kind,
         "message": message.strip(), "link": link, "media_url": media_url, "author": author,
         "rationale": rationale.strip(), "status": "pending", "created_at": _now(),
         "decided_at": None, "decided_by": None, "feedback": "",
         "published_at": None, "remote_id": None, "error": None}
    items = _load()
    items.append(d)
    _save(items)
    return d


def list_drafts(status: str = "", platform: str = "") -> list[dict]:
    return [d for d in _load()
            if (not status or d["status"] == status) and (not platform or d["platform"] == platform)]


def get_draft(draft_id: str) -> dict | None:
    return next((d for d in _load() if d["id"] == draft_id), None)


def _update(draft_id: str, **fields) -> dict | None:
    items = _load()
    for d in items:
        if d["id"] == draft_id:
            d.update(fields)
            _save(items)
            return d
    return None


def decide(draft_id: str, decision: str, by: str, feedback: str = "") -> dict | None:
    """HUMAN-ONLY (authenticated API route, never MCP). decision: approve | reject | hold."""
    status = {"approve": "approved", "reject": "rejected", "hold": "held"}.get(decision)
    d = get_draft(draft_id)
    if not status or not d or d["status"] not in _DECIDABLE:
        return None
    return _update(draft_id, status=status, decided_at=_now(), decided_by=by,
                   feedback=feedback.strip() or d.get("feedback", ""))


def mark_published(draft_id: str, remote_id: str) -> dict | None:
    return _update(draft_id, status="published", published_at=_now(), remote_id=remote_id, error=None)


def mark_failed(draft_id: str, error: str) -> dict | None:
    return _update(draft_id, status="approved", error=error[:500])
