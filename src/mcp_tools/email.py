"""
Gmail API — send + read customer support email as the active store's mailbox.

Lets Sol correspond with store customers through Gmail, using each store's own
OAuth2 refresh-token credentials (StoreConfig.email_credentials) and its own
"From" address (StoreConfig.support_email). Credentials are per-store on purpose:
there is no global/default mailbox fallback, so one store's agent can never send
mail through — or read the inbox of — another store's Gmail account.

Auth model: a refresh-token OAuth2 client (the standard pattern for a long-lived
server process to call the Gmail API without repeating interactive consent). The
refresh token is exchanged for a short-lived access token on every call via
_access_token() — access tokens are not cached here since Gmail calls from this
module are infrequent (support-inbox polling, occasional replies), not high volume.

Credentials shape (StoreConfig.email_credentials):
    {"client_id": "...", "client_secret": "...", "refresh_token": "..."}

The refresh token itself is generated once via Google Cloud Console + an OAuth2
consent flow — that flow is NOT built here; this module only consumes an
already-issued refresh token.
"""
from __future__ import annotations

import base64
from email.mime.text import MIMEText

import httpx

from src.stores import _current_store

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


async def _access_token(creds: dict) -> str | None:
    """
    Exchange a Gmail OAuth2 refresh token for a short-lived access token.

    POSTs to Google's token endpoint with grant_type=refresh_token. Returns the
    access_token string, or None if the exchange fails (expired/revoked refresh
    token, wrong client_id/secret, etc.) — callers are expected to turn a None
    into a user-facing {"error": ...} rather than let this raise.
    """
    if not (creds.get("client_id") and creds.get("client_secret") and creds.get("refresh_token")):
        return None
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                _TOKEN_URL,
                data={
                    "client_id": creds["client_id"],
                    "client_secret": creds["client_secret"],
                    "refresh_token": creds["refresh_token"],
                    "grant_type": "refresh_token",
                },
            )
        if resp.status_code >= 400:
            return None
        return resp.json().get("access_token")
    except Exception:
        return None


def _store_email_creds() -> tuple[dict, str] | None:
    """Fetch (email_credentials, support_email) for the active store, or None if
    there's no store in context or it has no email credentials configured. Never
    falls back to any other store's or global credentials."""
    store = _current_store.get(None)
    if not store or not store.email_credentials:
        return None
    return store.email_credentials, store.support_email


def _extract_body(payload: dict) -> str:
    """
    Pull a plain-text body out of a Gmail `payload` object.

    Gmail message bodies are base64url-encoded (no padding guaranteed) either
    directly in payload.body.data (simple messages) or nested under
    payload.parts[] for multipart messages (text/plain + text/html + attachments
    siblings) — parts can themselves be multipart (e.g. multipart/alternative
    inside multipart/mixed), so this walks recursively. Falls back to "" if no
    text/plain part is found; caller should fall back further to `snippet`.
    """
    def decode(data: str) -> str:
        # Gmail's base64url sometimes omits padding; add it back before decoding.
        padded = data + "=" * (-len(data) % 4)
        try:
            return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
        except Exception:
            return ""

    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")
    if mime_type == "text/plain" and body_data:
        return decode(body_data)

    for part in payload.get("parts", []) or []:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return decode(part["body"]["data"])

    # No direct text/plain part — recurse into nested multiparts.
    for part in payload.get("parts", []) or []:
        if part.get("parts"):
            text = _extract_body(part)
            if text:
                return text

    # Last resort: any part with body data at all (e.g. lone text/html).
    if body_data:
        return decode(body_data)
    for part in payload.get("parts", []) or []:
        if part.get("body", {}).get("data"):
            return decode(part["body"]["data"])
    return ""


async def send_email(to: str, subject: str, body: str, in_reply_to: str | None = None) -> dict:
    """
    Send an email as the active store's support mailbox.

    Args:
        to: Recipient address.
        subject: Subject line.
        body: Plain-text body.
        in_reply_to: Optional Gmail-style Message-ID (e.g. "<CAF...@mail.gmail.com>")
            of the message being replied to. When set, this stamps the RFC 2822
            In-Reply-To and References headers so Gmail (and the recipient's
            client) threads the reply under the original message instead of
            starting a new conversation. This is a *header* thread hint distinct
            from Gmail API's own `threadId` — see check_inbox for where a
            `thread_id` (used as the Gmail API threadId, not this header) comes
            from; this function doesn't take a thread_id because a brand-new
            outbound email has no existing Gmail thread to attach to.

    Returns {"message_id": ..., "thread_id": ...} on success, {"error": ...} on
    failure (no store, no credentials, failed token refresh, or non-2xx from
    Gmail).
    """
    creds_and_email = _store_email_creds()
    if not creds_and_email:
        return {"error": "no email credentials configured for this store"}
    creds, support_email = creds_and_email

    token = await _access_token(creds)
    if not token:
        return {"error": "failed to refresh Gmail access token"}

    msg = MIMEText(body)
    msg["To"] = to
    msg["From"] = support_email
    msg["Subject"] = subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to

    # Gmail requires the raw message base64url-encoded with no line breaks issues;
    # urlsafe_b64encode handles the URL-safe alphabet (- and _ instead of + and /)
    # correctly — using plain base64.b64encode here is a common bug (Gmail's API
    # rejects/mangles standard base64 padding chars in a URL query/JSON context).
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

    payload: dict = {"raw": raw}
    # threadId is only meaningful when replying inside an existing Gmail thread;
    # this function has no thread_id parameter (see docstring), so it's never set
    # here — callers wanting Gmail-API-level threading (vs. just header hints)
    # would need a variant that accepts one, sourced from check_inbox's thread_id.

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{_GMAIL_BASE}/messages/send",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
    except Exception as exc:
        return {"error": str(exc)}

    if resp.status_code >= 400:
        return {"error": resp.text[:200], "status_code": resp.status_code}
    data = resp.json()
    return {"message_id": data.get("id", ""), "thread_id": data.get("threadId", "")}


async def check_inbox(query: str = "is:unread", max_results: int = 10) -> dict:
    """
    List and fetch recent messages from the active store's Gmail inbox.

    Args:
        query: Gmail search query syntax (e.g. "is:unread", "from:someone@x.com",
            "newer_than:2d"). Defaults to unread mail only.
        max_results: Max messages to return (Gmail API's own cap is 500 per page;
            this is passed straight through as maxResults).

    Two-step Gmail API dance: messages.list only returns {id, threadId} pairs —
    it does NOT include headers/body — so each id is fetched individually via
    messages.get(format=metadata) for From/Subject, then the body is pulled from
    the same response if requested. To keep this to one extra call per message
    (not two), this uses format=full so From/Subject/body/snippet all come back
    together (fetching full bodies for every unread message is the point of an
    inbox check — Sol needs to read what the customer actually wrote).

    Returns {"messages": [{"thread_id", "message_id", "from", "subject",
    "snippet", "body"}, ...]} on success, {"error": ...} on failure.
    """
    creds_and_email = _store_email_creds()
    if not creds_and_email:
        return {"error": "no email credentials configured for this store"}
    creds, _ = creds_and_email

    token = await _access_token(creds)
    if not token:
        return {"error": "failed to refresh Gmail access token"}

    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            list_resp = await client.get(
                f"{_GMAIL_BASE}/messages",
                params={"q": query, "maxResults": max_results},
                headers=headers,
            )
            if list_resp.status_code >= 400:
                return {"error": list_resp.text[:200], "status_code": list_resp.status_code}
            ids = [m["id"] for m in (list_resp.json().get("messages") or [])]

            messages = []
            for msg_id in ids:
                msg_resp = await client.get(
                    f"{_GMAIL_BASE}/messages/{msg_id}",
                    params={"format": "full"},
                    headers=headers,
                )
                if msg_resp.status_code >= 400:
                    # Skip a single bad message rather than failing the whole
                    # inbox check (e.g. a message deleted between list + get).
                    continue
                body_json = msg_resp.json()
                payload_obj = body_json.get("payload", {}) or {}
                header_list = payload_obj.get("headers", []) or []
                from_addr = next((h["value"] for h in header_list if h.get("name") == "From"), "")
                subject = next((h["value"] for h in header_list if h.get("name") == "Subject"), "")
                snippet = body_json.get("snippet", "")
                extracted_body = _extract_body(payload_obj) or snippet
                messages.append({
                    "thread_id": body_json.get("threadId", ""),
                    "message_id": body_json.get("id", msg_id),
                    "from": from_addr,
                    "subject": subject,
                    "snippet": snippet,
                    "body": extracted_body,
                })
    except Exception as exc:
        return {"error": str(exc)}

    return {"messages": messages}


async def mark_handled(thread_id: str) -> dict:
    """
    Mark a Gmail thread as handled by removing the UNREAD label.

    This is the simplest durable "handled" signal available: it doesn't delete or
    archive anything, just makes the thread stop matching check_inbox's default
    `is:unread` query so Sol doesn't keep re-processing the same customer email.

    Returns {"ok": True} on success, {"error": ...} on failure.
    """
    creds_and_email = _store_email_creds()
    if not creds_and_email:
        return {"error": "no email credentials configured for this store"}
    creds, _ = creds_and_email

    token = await _access_token(creds)
    if not token:
        return {"error": "failed to refresh Gmail access token"}

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{_GMAIL_BASE}/threads/{thread_id}/modify",
                json={"removeLabelIds": ["UNREAD"]},
                headers={"Authorization": f"Bearer {token}"},
            )
    except Exception as exc:
        return {"error": str(exc)}

    if resp.status_code >= 400:
        return {"error": resp.text[:200], "status_code": resp.status_code}
    return {"ok": True}
