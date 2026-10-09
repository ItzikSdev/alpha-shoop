"""One-time connection helper — run it in YOUR terminal so tokens never pass through chat.

    python -m src.social_mcp.connect meta      Facebook Page + Instagram
    python -m src.social_mcp.connect tiktok    TikTok organic posting
    python -m src.social_mcp.connect status    what is connected right now

meta: paste a user token from developers.facebook.com/tools/explorer (hidden input).
  It is exchanged for a long-lived user token, then for the PAGE token of META_PAGE_ID — a page
  token made from a long-lived user token does not expire. Saved: FB_PAGE_ACCESS_TOKEN and
  (when an Instagram Business account is linked) META_IG_USER_ID, written to .env.
tiktok: paste the client key/secret + redirect URI of your TikTok for Developers app, open the
  printed link, approve, paste the `code` from the redirect URL. Tokens are written to .env.
"""
from __future__ import annotations

import asyncio
import getpass
import os
import sys

import httpx

from src.social_mcp import meta, publish, tiktok

PERMS = ("pages_show_list, pages_manage_posts, pages_read_engagement, pages_read_user_content, "
         "instagram_basic, instagram_content_publish, instagram_manage_comments, instagram_manage_insights")


def _ask(label: str, secret: bool = False, default: str = "") -> str:
    shown = f"{label}{f' [{default}]' if default else ''}: "
    v = (getpass.getpass(shown) if secret else input(shown)).strip()
    return v or default


async def connect_meta() -> int:
    page = meta.page_id() or _ask("Facebook Page ID")
    print(f"\nGet a USER token at https://developers.facebook.com/tools/explorer with: {PERMS}")
    print("(pick your app, 'Get User Access Token', tick the permissions above, Generate)\n")
    user = os.environ.get("META_ACCESS_TOKEN_ALPHA_FOR_BABY", "").strip()
    if user:
        print("Using the user token from META_ACCESS_TOKEN_ALPHA_FOR_BABY (.env).")
    else:
        user = _ask("User access token (hidden)", secret=True)
    app_id = os.environ.get("META_APP_ID", "").strip() or _ask("Meta App ID")
    app_secret = os.environ.get("META_APP_SECRET", "").strip() or _ask("Meta App Secret (hidden)", secret=True)
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{meta.GRAPH}/oauth/access_token", params={
            "grant_type": "fb_exchange_token", "client_id": app_id, "client_secret": app_secret,
            "fb_exchange_token": user})
        long_user = meta._check(r)["access_token"]
        accounts = meta._check(await c.get(f"{meta.GRAPH}/me/accounts", params={
            "access_token": long_user, "fields": "id,name,access_token,instagram_business_account", "limit": 100}))
        pages = accounts.get("data", [])
        match = next((p for p in pages if p["id"] == page), None)
        if not match:
            # Pages granted through a Business portfolio / New Pages Experience are
            # often missing from /me/accounts even though the token can manage them —
            # ask for the page directly.
            r2 = await c.get(f"{meta.GRAPH}/{page}", params={
                "access_token": long_user, "fields": "id,name,access_token,instagram_business_account"})
            if r2.status_code == 200 and r2.json().get("access_token"):
                match = r2.json()
        if not match:
            print(f"\nPage {page} is not among the pages this token can manage:")
            for p in pages:
                print(f"  {p['id']}  {p['name']}")
            print("Pick the right one (META_PAGE_ID in .env) or generate the token with an account that is an admin of the page.")
            return 1
        kv = {"FB_PAGE_ACCESS_TOKEN": match["access_token"], "META_APP_ID": app_id, "META_APP_SECRET": app_secret,
              "META_PAGE_ID": page}
        ig = (match.get("instagram_business_account") or {}).get("id", "")
        if ig:
            kv["META_IG_USER_ID"] = ig
        tiktok._persist(**kv)
    print(f"\n✓ Saved Page token for '{match['name']}'" + (f" and Instagram account {ig}" if ig else
          "\n! No Instagram Business account is linked to this Page — link it in Meta Business Suite for Instagram posting."))
    return 0


async def connect_tiktok() -> int:
    print("Create an app at https://developers.tiktok.com (Login Kit + Content Posting API, "
          "scopes user.info.basic, video.publish, video.list).")
    kv = {
        "TIKTOK_CLIENT_KEY": os.environ.get("TIKTOK_CLIENT_KEY", "").strip() or _ask("Client key"),
        "TIKTOK_CLIENT_SECRET": os.environ.get("TIKTOK_CLIENT_SECRET", "").strip() or _ask("Client secret (hidden)", True),
        "TIKTOK_CONTENT_REDIRECT_URI": os.environ.get("TIKTOK_CONTENT_REDIRECT_URI", "").strip()
        or _ask("Redirect URI registered in the app"),
    }
    tiktok._persist(**kv)
    print("\nOpen this link while logged in as the store's TikTok account and approve:\n")
    lu = tiktok.login_url()
    print(lu.get("authorize_url") or lu)
    code = _ask("\nPaste the `code` value from the URL you were redirected to")
    res = await tiktok.complete_auth(code)
    print("✓ TikTok connected" if res.get("ok", True) else f"✗ {res}")
    return 0 if res.get("ok", True) else 1


async def show_status() -> int:
    st = await publish.all_status()
    for name, s in st.items():
        mark = "✓" if s.get("ok") else "✗"
        extra = s.get("error") or (f"missing: {', '.join(s['missing_env'])}" if s.get("missing_env") else s.get("account", ""))
        print(f"{mark} {name}: {extra}")
    return 0


def main() -> int:
    from dotenv import load_dotenv
    load_dotenv()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    fn = {"meta": connect_meta, "tiktok": connect_tiktok, "status": show_status}.get(cmd)
    if not fn:
        print(__doc__)
        return 2
    return asyncio.run(fn())


if __name__ == "__main__":
    raise SystemExit(main())
