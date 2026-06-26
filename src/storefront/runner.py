"""Host-side Shopify Theme Runner.

A standalone FastAPI app — SEPARATE from the main Alpha Shoop API — that runs
directly on the HOST (not in Docker), bound to 127.0.0.1:8788. It manages
per-store **Shopify CLI Liquid themes** (Online Store 2.0) under
``<repo>/stores/shopify/{slug}/`` using the official ``shopify theme`` commands
(https://shopify.dev/docs/api/shopify-cli/theme) so stores get ALL native
Shopify features (theme editor, sections, app blocks, metafields, real-time dev).

Flow per store:
  pull   → ``shopify theme pull``  (download the store's current LIVE theme)
  run    → ``shopify theme dev``   (localhost preview + real-time push to a dev theme)
  deploy → ``shopify theme push``  (upload local changes back to Shopify)

Auth is non-interactive: the store's Admin API token is used as
``SHOPIFY_CLI_THEME_TOKEN`` together with ``--store``. The runner fetches that
token server-to-server from the Docker API (so it never passes through the
browser) via GET /stores/{id}/theme-creds.

Run with:
    uvicorn src.storefront.runner:app --host 127.0.0.1 --port 8788 --reload
or:
    python -m src.storefront.runner
"""
from __future__ import annotations

import json
import logging
import os
import re
import signal
import socket
import subprocess
import urllib.request
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Repo root: src/storefront/runner.py -> parents[2] == repo root
ROOT = Path(__file__).resolve().parents[2]
STOREFRONTS_DIR = ROOT / "stores" / "shopify"

# Docker API (on the host's published port) — used to fetch per-store theme creds.
ALPHA_API_URL = os.environ.get("ALPHA_API_URL", "http://localhost:8000/api/v1")

# In-memory registry of running `theme dev` servers:
# {store_id: {"pid": int, "port": int, "slug": str, "process": Popen}}
_RUNNING: dict[str, dict] = {}

app = FastAPI(title="Alpha Shoop — Storefront Runner", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request models ──────────────────────────────────────────────────────────
class PullBody(BaseModel):
    slug: str


class RunBody(BaseModel):
    slug: str
    force_pull: bool = False  # re-pull the live theme even if files already exist
    store_password: str | None = None  # storefront password, required while password-protected (e.g. dev stores)


class DeployBody(BaseModel):
    slug: str
    publish: bool = False  # False → push to an unpublished theme (safe); True → push --live


# ── Helpers ─────────────────────────────────────────────────────────────────
def _theme_dir(slug: str) -> Path:
    return STOREFRONTS_DIR / slug


def _is_theme(slug: str) -> bool:
    """A Liquid theme is present once its canonical files exist."""
    d = _theme_dir(slug)
    return (d / "config" / "settings_schema.json").exists() or (d / "layout" / "theme.liquid").exists()


def _log_path(slug: str) -> Path:
    return _theme_dir(slug) / ".runner.log"


def _append_log(slug: str, text: str) -> None:
    if not text:
        return
    try:
        d = _theme_dir(slug)
        d.mkdir(parents=True, exist_ok=True)
        with _log_path(slug).open("a", encoding="utf-8") as fh:
            fh.write(text)
            if not text.endswith("\n"):
                fh.write("\n")
    except Exception as exc:  # logging must never crash the request
        logger.warning("Failed to write runner log for %s: %s", slug, exc)


def _fetch_theme_creds(store_id: str) -> dict:
    """Fetch {domain, theme_token, live_theme_id} from the Docker API (server-to-server)."""
    url = f"{ALPHA_API_URL}/stores/{store_id}/theme-creds"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.load(resp)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch theme creds from Alpha API ({url}): {exc}",
        )
    if not data.get("theme_token") or not data.get("domain"):
        raise HTTPException(status_code=502, detail="Alpha API returned incomplete theme creds")
    return data


def _cli_env(token: str) -> dict:
    env = os.environ.copy()
    env["SHOPIFY_CLI_THEME_TOKEN"] = token       # non-interactive auth
    env["SHOPIFY_CLI_NO_ANALYTICS"] = "1"
    env["CI"] = "1"                               # suppress interactive prompts
    return env


def _is_running(store_id: str) -> bool:
    info = _RUNNING.get(store_id)
    if not info:
        return False
    proc: subprocess.Popen = info["process"]
    if proc.poll() is not None:  # process exited — clean up stale entry
        _RUNNING.pop(store_id, None)
        return False
    return True


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _free_port(start: int = 9292) -> int:
    used = {info["port"] for info in _RUNNING.values() if _running_info(info)}
    port = start
    while port < start + 1000:
        if port not in used and not _port_in_use(port):
            return port
        port += 1
    raise RuntimeError("No free port found in range")


def _running_info(info: dict) -> bool:
    proc: subprocess.Popen | None = info.get("process")
    return bool(proc) and proc.poll() is None


def _run_oneshot(cmd: list[str], cwd: Path, slug: str, env: dict | None = None,
                 timeout: int = 600) -> subprocess.CompletedProcess:
    """Run a one-shot command, capturing combined output into the runner log."""
    _append_log(slug, f"$ {' '.join(cmd)}  (cwd={cwd})")
    result = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, env=env,
    )
    _append_log(slug, result.stdout or "")
    _append_log(slug, result.stderr or "")
    return result


def _do_pull(slug: str, creds: dict, force: bool = False) -> None:
    """`shopify theme pull` the store's live theme into stores/shopify/{slug}."""
    d = _theme_dir(slug)
    if _is_theme(slug) and not force:
        return  # already have the theme locally
    d.mkdir(parents=True, exist_ok=True)
    cmd = [
        "shopify", "theme", "pull",
        "--store", creds["domain"],
        "--path", str(d),
    ]
    if creds.get("live_theme_id"):
        cmd += ["--theme", str(creds["live_theme_id"])]
    else:
        cmd += ["--live"]
    pull_token = creds.get("theme_password") or creds["theme_token"]  # both work for pull
    result = _run_oneshot(cmd, cwd=ROOT, slug=slug, env=_cli_env(pull_token), timeout=600)
    if result.returncode != 0 and not _is_theme(slug):
        raise HTTPException(status_code=502, detail=f"theme pull failed: {(result.stderr or result.stdout)[-300:]}")


_URL_RE = re.compile(r"https?://[^\s\"'<>]+")


def _parse_urls(output: str) -> list[str]:
    return _URL_RE.findall(output or "")


# ── Endpoints ───────────────────────────────────────────────────────────────
@app.get("/health")
async def health() -> dict:
    return {"ok": True, "mode": "shopify-theme-cli"}


@app.get("/storefronts")
async def list_storefronts() -> list[dict]:
    """List tracked (running) themes AND every theme folder under stores/shopify."""
    seen: set[str] = set()
    out: list[dict] = []

    for store_id, info in list(_RUNNING.items()):
        slug = info["slug"]
        running = _is_running(store_id)
        port = info["port"] if running else None
        out.append({
            "store_id": store_id, "slug": slug,
            "scaffolded": _is_theme(slug), "running": running,
            "port": port, "url": f"http://127.0.0.1:{port}" if port else None,
        })
        seen.add(slug)

    if STOREFRONTS_DIR.exists():
        for child in sorted(STOREFRONTS_DIR.iterdir()):
            if not child.is_dir() or child.name in seen or child.name.startswith((".", "_")):
                continue
            out.append({
                "store_id": None, "slug": child.name,
                "scaffolded": _is_theme(child.name), "running": False,
                "port": None, "url": None,
            })
            seen.add(child.name)
    return out


@app.post("/storefronts/{store_id}/pull")
async def pull(store_id: str, body: PullBody) -> dict:
    """Download the store's current live theme into stores/shopify/{slug}."""
    creds = _fetch_theme_creds(store_id)
    _do_pull(body.slug, creds, force=True)
    return {"pulled": True, "slug": body.slug, "path": f"stores/shopify/{body.slug}"}


@app.post("/storefronts/{store_id}/run")
async def run(store_id: str, body: RunBody) -> dict:
    """Start `shopify theme dev` — localhost preview with real-time sync to a dev theme."""
    slug = body.slug

    if _is_running(store_id):
        info = _RUNNING[store_id]
        return {"url": f"http://127.0.0.1:{info['port']}", "port": info["port"], "running": True}

    creds = _fetch_theme_creds(store_id)
    # `shopify theme dev` (unlike pull/push) cannot use an Admin API token — it
    # requires a Theme Access password (from the Theme Access app) for the live
    # preview/hot-reload channel.
    dev_token = creds.get("theme_password")
    if not dev_token:
        raise HTTPException(
            status_code=400,
            detail=(
                "Run in localhost (shopify theme dev) needs a Theme Access password. "
                "Install the 'Theme Access' app in the store admin, generate a password "
                "(shptka_…), and add it on the store card."
            ),
        )
    _do_pull(slug, creds, force=body.force_pull)

    d = _theme_dir(slug)
    port = _free_port(9292)

    cmd = [
        "shopify", "theme", "dev",
        "--store", creds["domain"],
        "--path", str(d),
        "--port", str(port),
    ]
    if body.store_password:
        cmd += ["--store-password", body.store_password]
    _append_log(slug, f"$ {' '.join(cmd)}  (cwd={d})")
    log_fh = _log_path(slug).open("a", encoding="utf-8")
    popen_kwargs: dict = {
        "cwd": str(d),
        "stdout": log_fh,
        "stderr": subprocess.STDOUT,
        "env": _cli_env(dev_token),
    }
    if os.name == "posix":
        popen_kwargs["start_new_session"] = True  # own process group for clean group-kill
    proc = subprocess.Popen(cmd, **popen_kwargs)

    _RUNNING[store_id] = {"pid": proc.pid, "port": port, "slug": slug, "process": proc}
    return {"url": f"http://127.0.0.1:{port}", "port": port, "running": True,
            "editor_url": f"https://{creds['domain']}/admin/themes"}


@app.post("/storefronts/{store_id}/stop")
async def stop(store_id: str) -> dict:
    info = _RUNNING.pop(store_id, None)
    if not info:
        return {"running": False}
    proc: subprocess.Popen = info["process"]
    try:
        if os.name == "posix" and info.get("pid"):
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                proc.terminate()
        else:
            proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    proc.kill()
            else:
                proc.kill()
    except Exception as exc:
        logger.warning("Error stopping theme dev %s: %s", store_id, exc)
    return {"running": False}


@app.post("/storefronts/{store_id}/deploy")
async def deploy(store_id: str, body: DeployBody) -> dict:
    """Upload local theme changes to Shopify via `shopify theme push`.

    Default (publish=False) pushes to a NEW unpublished theme (safe — never
    overwrites the live theme). publish=True pushes directly to the live theme.
    """
    if not _is_theme(body.slug):
        raise HTTPException(status_code=404, detail=f"Theme {body.slug!r} not pulled locally yet")
    creds = _fetch_theme_creds(store_id)
    d = _theme_dir(body.slug)
    push_token = creds.get("theme_password") or creds["theme_token"]  # admin token works for push

    cmd = ["shopify", "theme", "push", "--store", creds["domain"], "--path", str(d), "--json"]
    if body.publish:
        cmd += ["--live", "--allow-live"]
    else:
        # New unpublished theme (named, so it never prompts). Safe — never touches live.
        cmd += ["--unpublished", "--theme", f"Alpha Shoop — {body.slug}"]

    try:
        result = _run_oneshot(cmd, cwd=d, slug=body.slug, env=_cli_env(push_token), timeout=600)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="theme push timed out after 600s")

    output = (result.stdout or "") + (result.stderr or "")
    # `--json` prints a {"theme": {...}} object; fall back to URL scraping.
    preview_url = ""
    theme_id = None
    try:
        for line in (result.stdout or "").splitlines():
            line = line.strip()
            if line.startswith("{"):
                obj = json.loads(line)
                theme = obj.get("theme", obj)
                theme_id = theme.get("id")
                preview_url = theme.get("preview_url") or theme.get("editor_url") or ""
                break
    except Exception:
        pass
    if not preview_url:
        urls = _parse_urls(output)
        preview_url = urls[-1] if urls else ""

    return {
        "ok": result.returncode == 0,
        "published": body.publish,
        "theme_id": theme_id,
        "url": preview_url,
        "output": "\n".join(output.splitlines()[-50:]),
    }


@app.get("/storefronts/{store_id}/logs")
async def logs(store_id: str, tail: int = 200) -> dict:
    info = _RUNNING.get(store_id)
    slug = info["slug"] if info else None
    if slug is None:
        raise HTTPException(status_code=404, detail=f"No tracked theme for store {store_id!r}")
    path = _log_path(slug)
    if not path.exists():
        return {"slug": slug, "lines": []}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return {"slug": slug, "lines": lines[-tail:]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8788)
