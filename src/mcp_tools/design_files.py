"""
Design-file access for Grace / Linus — read & write the templates that drive the
storefronts, under the approved `stores/` directory.

Each store lives at stores/shopify/<slug>/ with:
  - style/      the design files (site.json, product.json, *.liquid, design.html)
  - readme/     README.md — the source-of-truth rules
  - changelog/  CHANGELOG.md — every change, newest on top

This is the controlled exception to the "agents don't touch files" rule: the agents
may read and write ONLY inside stores/. Every path is validated to stay inside it;
.json content is validated before writing; nothing else on disk is reachable. This
lets Grace edit the design templates herself and Linus scaffold new stores.
"""
from __future__ import annotations

import json
from pathlib import Path

_STYLES_ROOT = (Path(__file__).resolve().parents[2] / "stores").resolve()


def _safe(path: str) -> Path | None:
    """Resolve `path` (relative to styles/, or absolute) and confirm it stays inside
    styles/. Returns None if it escapes the sandbox."""
    raw = Path(path)
    p = (raw if raw.is_absolute() else _STYLES_ROOT / raw).resolve()
    try:
        p.relative_to(_STYLES_ROOT)
    except ValueError:
        return None
    return p


def list_design_files(subdir: str = "") -> dict:
    """List every file under styles/ (or a subdir), so the agents can see what
    templates exist (per store)."""
    base = _safe(subdir) or _STYLES_ROOT
    if not base.exists():
        return {"root": str(_STYLES_ROOT), "files": []}
    files = sorted(str(f.relative_to(_STYLES_ROOT)) for f in base.rglob("*") if f.is_file())
    return {"root": str(_STYLES_ROOT), "files": files}


def read_design_file(path: str) -> dict:
    """Read a template file under styles/. Returns {path, content} or {error}."""
    p = _safe(path)
    if not p or not p.exists() or not p.is_file():
        return {"error": f"not found or outside styles/: {path}"}
    return {"path": str(p.relative_to(_STYLES_ROOT)), "content": p.read_text(encoding="utf-8", errors="ignore")}


def write_design_file(path: str, content: str) -> dict:
    """Write a template file under styles/ (creating folders as needed). JSON files
    are validated first. Returns {ok, path, bytes} or {error}. After this, call
    apply_site_design / apply_product_design to push the change live."""
    p = _safe(path)
    if not p:
        return {"error": f"path escapes styles/ sandbox: {path}"}
    if p.suffix.lower() == ".json":
        try:
            json.loads(content)
        except Exception as exc:
            return {"error": f"invalid JSON, not written: {exc}"}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(p.relative_to(_STYLES_ROOT)), "bytes": len(content)}


# ── Store docs: the README (source-of-truth rules) + CHANGELOG (every change) ──
# This is the "changelog skill" the agents operate by: they READ these before
# changing the store and the system LOGS every change here so nothing is invisible.

def _store_dir(store_slug: str) -> Path:
    """stores/shopify/<slug>/, tolerant to naming (e.g. slug 'timeforbaby' matches a
    folder 'timeforbaby.alpha-tech.live'). Falls back to the only store folder when
    there's exactly one, so callers never need the exact on-disk name."""
    base = _STYLES_ROOT / "shopify"
    want = "".join(c for c in (store_slug or "").lower() if c.isalnum())
    dirs = []
    try:
        dirs = [d for d in base.iterdir() if d.is_dir()]
    except Exception:
        dirs = []
    for d in dirs:
        dn = "".join(c for c in d.name.lower() if c.isalnum())
        if want and (dn in want or want in dn):
            return d
    if len(dirs) == 1:
        return dirs[0]
    return base / (store_slug or "timeforbaby")


def read_store_docs(store_slug: str = "timeforbaby", changelog_chars: int = 1600) -> dict:
    """Return the store's CLAUDE.md (build guide) + README + OWNER + the most recent
    CHANGELOG tail, for the agents to READ before they change anything. Empty strings
    if a file doesn't exist yet.

    CLAUDE.md is the authoritative "how to build this store like the template" guide —
    it's loaded first so every agent uses the template + the read/build/log rules."""
    d = _store_dir(store_slug)
    claude = (d / "CLAUDE.md")
    readme = (d / "readme" / "README.md")
    changelog = (d / "changelog" / "CHANGELOG.md")
    owner = (d / "readme" / "OWNER.md")
    cl = claude.read_text(encoding="utf-8", errors="ignore") if claude.exists() else ""
    rt = readme.read_text(encoding="utf-8", errors="ignore") if readme.exists() else ""
    ct = changelog.read_text(encoding="utf-8", errors="ignore") if changelog.exists() else ""
    ot = owner.read_text(encoding="utf-8", errors="ignore") if owner.exists() else ""
    # CHANGELOG is newest-on-top, so the HEAD is the recent history.
    return {"claude": cl, "readme": rt, "changelog_recent": ct[:changelog_chars],
            "owner": ot, "dir": str(d)}


def append_changelog(
    title: str, changed: str, by: str = "system", context: str = "",
    store_slug: str = "timeforbaby",
) -> dict:
    """Prepend one entry to the store's CHANGELOG.md (newest-on-top), timestamped in
    Asia/Jerusalem. This is how EVERY store change gets recorded — call it right
    after a design write/apply. Returns {ok, path} or {error}."""
    from datetime import datetime, timezone, timedelta
    # Asia/Jerusalem is UTC+3 (IDT) in summer; fall back to a fixed offset if the
    # zoneinfo db isn't present in the container.
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Jerusalem"))
        tz = "Asia/Jerusalem"
    except Exception:
        now = datetime.now(timezone(timedelta(hours=3)))
        tz = "UTC+3"
    stamp = now.strftime("%Y-%m-%d %H:%M")
    entry = (
        f"## {stamp} ({tz}) — {title}\n"
        f"**By:** {by}\n"
        + (f"**Context:** {context}\n" if context else "")
        + f"**Changed:** {changed}\n\n"
    )
    d = _store_dir(store_slug) / "changelog"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "CHANGELOG.md"
    header = "# TIMEFOR BABY — Store Changelog\n\nEvery change to the store is recorded here. **Newest on top.**\n\n---\n\n"
    if f.exists():
        body = f.read_text(encoding="utf-8", errors="ignore")
        marker = "---\n\n"
        idx = body.find(marker)
        if idx != -1:
            cut = idx + len(marker)
            new = body[:cut] + entry + body[cut:]
        else:
            new = body.rstrip() + "\n\n" + entry
    else:
        new = header + entry
    f.write_text(new, encoding="utf-8")
    return {"ok": True, "path": str(f.relative_to(_STYLES_ROOT))}
