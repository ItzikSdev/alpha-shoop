"""Design lock — agents must not change the live store's theme/design.

Owner instruction (2026-10-03): "שלא ישנו עיצוב של חנות". Every code path that can
WRITE to a Shopify theme (asset PUT/POST/DELETE, theme create/publish, GraphQL
theme mutations, the apply-design route) checks `theme_writes_blocked()` first.
Reads (GET) stay allowed. To lift the lock deliberately, set ALLOW_THEME_CHANGES=on.
"""
from __future__ import annotations

import os
import re

_THEME_PATH = re.compile(r"(^|/)themes(/|\.json|$)", re.I)


def theme_writes_blocked() -> bool:
    return os.environ.get("ALLOW_THEME_CHANGES", "off").strip().lower() not in ("on", "1", "true", "yes")


def is_theme_write(method: str, path: str) -> bool:
    """True for a REST call that would modify a theme (anything but GET/HEAD on themes/…)."""
    if method.upper() in ("GET", "HEAD"):
        return False
    return bool(_THEME_PATH.search(path.split("?", 1)[0]))


def is_theme_graphql_write(query: str) -> bool:
    return bool(re.search(r"\bmutation\b", query or "", re.I) and re.search(r"\btheme\w*", query or "", re.I))


LOCKED = {"ok": False, "status": 403, "error": "design locked: the owner forbids theme/design changes "
          "(set ALLOW_THEME_CHANGES=on to lift)"}
