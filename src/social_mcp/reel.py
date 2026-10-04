"""Reels from the store's EXISTING product videos — no video generation.

The store already has real clips on its products (CJ listing clips etc., stored as
Shopify VIDEO media). This module:
  list_store_videos()  → every product video with a direct https .mp4 source
  make_reel()          → crop to 9:16, trim to <=15s, add a hook line (+ optional CTA at the
                         end) as burned-in text, drop the source audio, upload the result to
                         Shopify Files and return a PUBLIC https URL for draft_post.

Text is drawn with Pillow into transparent PNGs and overlaid, because the ffmpeg build used
here has no drawtext/libass (see src/video/assembler.py). Source audio is removed on purpose:
supplier clips often carry music we have no licence for. Pick a trending sound in the
Facebook/Instagram app when you publish — platforms do not expose it through the API.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

W, H = 1080, 1920
MAX_SECONDS = 15.0
MIN_SECONDS = 6.0          # shorter clips are looped up to this length
_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Hebrew Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
]


class ReelError(RuntimeError):
    pass


# ── Shopify ──────────────────────────────────────────────────────────────────

_GQL_VIDEOS = """
query storeVideos($first: Int!, $query: String) {
  products(first: $first, query: $query, sortKey: UPDATED_AT, reverse: true) {
    nodes {
      id title handle status onlineStoreUrl
      media(first: 10) { nodes {
        mediaContentType alt
        ... on Video { duration sources { url mimeType width height } }
      } }
    }
  }
}
"""

_GQL_STAGED = """
mutation staged($input: [StagedUploadInput!]!) {
  stagedUploadsCreate(input: $input) {
    stagedTargets { url resourceUrl parameters { name value } }
    userErrors { field message }
  }
}
"""
_GQL_FILE_CREATE = """
mutation fileCreate($files: [FileCreateInput!]!) {
  fileCreate(files: $files) {
    files { id fileStatus }
    userErrors { field message }
  }
}
"""
_GQL_FILE_STATUS = """
query f($id: ID!) { node(id: $id) { ... on GenericFile { url fileStatus } } }
"""


def _best_source(sources: list[dict]) -> dict | None:
    mp4 = [s for s in sources or [] if "mp4" in (s.get("mimeType") or "") and s.get("url", "").startswith("https://")]
    if not mp4:
        return None
    # highest quality up to 1080 tall; otherwise the smallest above it
    ok = [s for s in mp4 if (s.get("height") or 0) <= 1920]
    return max(ok or mp4, key=lambda s: s.get("height") or 0)


async def list_store_videos(limit: int = 30, query: str = "") -> list[dict]:
    """Products that already have a video. `query` is a Shopify product search (e.g. 'title:*romper*')."""
    from src.mcp_tools.shopify import _shopify_gql

    # Only products that are live: ACTIVE and published to the Online Store (onlineStoreUrl is null otherwise).
    q = "status:active published_status:published" + (f" AND ({query})" if query else "")
    data = await _shopify_gql(_GQL_VIDEOS, {"first": min(max(limit, 1), 100), "query": q})
    out: list[dict] = []
    # Customers use the storefront domain (Hydrogen), not the Shopify checkout host onlineStoreUrl points at.
    base = (os.environ.get("STORE_PUBLIC_URL") or "https://alphaforbaby.com").rstrip("/")
    for p in data.get("products", {}).get("nodes", []):
        if p.get("status") != "ACTIVE" or not p.get("onlineStoreUrl"):
            continue
        for m in (p.get("media") or {}).get("nodes", []):
            if m.get("mediaContentType") != "VIDEO":
                continue
            src = _best_source(m.get("sources") or [])
            if not src:
                continue
            out.append({
                "product_id": p["id"], "product_title": p["title"], "status": p.get("status"),
                "product_url": f"{base}/products/{p['handle']}",
                "tracked_url": f"{base}/products/{p['handle']}?utm_source=social&utm_medium=organic&utm_campaign=reel",
                "video_url": src["url"], "width": src.get("width"), "height": src.get("height"),
                "duration_s": (m.get("duration") or 0) / 1000 if (m.get("duration") or 0) > 1000 else m.get("duration"),
                "alt": m.get("alt") or "",
            })
    return out


async def host_video(path: Path, alt: str = "") -> str:
    """Upload an MP4 to Shopify Files and return its public https URL."""
    from src.mcp_tools.shopify import _shopify_gql

    data = path.read_bytes()
    staged = await _shopify_gql(_GQL_STAGED, {"input": [{
        "resource": "FILE", "filename": path.name, "mimeType": "video/mp4",
        "fileSize": str(len(data)), "httpMethod": "PUT",
    }]})
    st = staged.get("stagedUploadsCreate", {})
    if st.get("userErrors") or not st.get("stagedTargets"):
        raise ReelError(f"stagedUploadsCreate failed: {st.get('userErrors') or staged}")
    target = st["stagedTargets"][0]
    headers = {"Content-Type": "video/mp4"}
    for prm in target.get("parameters") or []:
        if prm["name"].lower() in {"content_type", "x-goog-content-length-range", "content-length"}:
            continue
        headers[prm["name"]] = prm["value"]
    async with httpx.AsyncClient(timeout=180) as c:
        r = await c.put(target["url"], content=data, headers=headers)
        if r.status_code >= 300:
            raise ReelError(f"upload to staged target failed: HTTP {r.status_code}")
    created = await _shopify_gql(_GQL_FILE_CREATE, {"files": [{
        "originalSource": target["resourceUrl"], "contentType": "FILE", "alt": alt[:120]}]})
    fc = created.get("fileCreate", {})
    if fc.get("userErrors") or not fc.get("files"):
        raise ReelError(f"fileCreate failed (needs the write_files scope?): {fc.get('userErrors') or created}")
    fid = fc["files"][0]["id"]
    for _ in range(30):
        await asyncio.sleep(2)
        node = (await _shopify_gql(_GQL_FILE_STATUS, {"id": fid})).get("node") or {}
        if node.get("url"):
            return node["url"]
        if node.get("fileStatus") == "FAILED":
            raise ReelError("Shopify could not process the uploaded video")
    raise ReelError("Shopify is still processing the uploaded video — retry make_reel in a minute")


# ── Rendering ────────────────────────────────────────────────────────────────

def tools_ok() -> dict:
    """What this machine can do — used by the capability report."""
    try:
        import PIL  # noqa: F401
        pil = True
    except Exception:  # noqa: BLE001
        pil = False
    return {"ffmpeg": bool(shutil.which("ffmpeg")), "ffprobe": bool(shutil.which("ffprobe")), "pillow": pil}


def _font(size: int):
    from PIL import ImageFont

    for f in _FONTS:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size)


_HEBREW = re.compile(r"[֐-׿]")


def _display(line: str) -> str:
    """Pillow without libraqm draws Hebrew left-to-right; flip those lines so they read correctly."""
    from PIL import features

    if _HEBREW.search(line) and not features.check("raqm"):
        return line[::-1]
    return line


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split():
            trial = f"{cur} {word}".strip()
            if draw.textlength(_display(trial), font=font) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return [l for l in lines if l]


def render_text_png(text: str, out: Path, *, position: str = "top", size: int = 66) -> Path:
    """Transparent 1080x1920 PNG with centred, outlined text in the platform-safe area."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = _font(size)
    lines = _wrap(d, text.strip(), font, W - 200)[:5]
    line_h = int(size * 1.25)
    block = line_h * len(lines)
    y = 250 if position == "top" else H - 520 - block      # clear of the top bar and the bottom UI
    for ln in lines:
        s = _display(ln)
        x = (W - d.textlength(s, font=font)) / 2
        d.text((x, y), s, font=font, fill=(255, 255, 255, 255), stroke_width=5, stroke_fill=(0, 0, 0, 255))
        y += line_h
    img.save(out)
    return out


async def _run(*cmd: str) -> str:
    p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await p.communicate()
    if p.returncode != 0:
        raise ReelError(f"{cmd[0]} failed: {err.decode(errors='ignore')[-500:]}")
    return out.decode(errors="ignore")


async def _duration(path: Path) -> float:
    out = await _run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path))
    return float(out.strip() or 0)


async def render_reel(src: Path, out: Path, *, hook: str, cta: str = "", start: float = 0.0,
                      max_seconds: float = MAX_SECONDS) -> dict:
    """9:16, <=max_seconds, silent AAC track, hook text all along, CTA in the last 3s."""
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise ReelError("ffmpeg/ffprobe are not installed on this machine")
    src_len = await _duration(src)
    start = max(0.0, min(start, max(0.0, src_len - 1.0)))
    avail = max(0.5, src_len - start)
    length = min(max_seconds, MAX_SECONDS)
    loops = 0
    if avail < MIN_SECONDS:                     # short clip: loop it up to ~MIN_SECONDS
        loops = int(MIN_SECONDS // avail)
        length = min(length, avail * (loops + 1))
    else:
        length = min(length, avail)
    work = out.parent
    hook_png = render_text_png(hook, work / f"{out.stem}_hook.png", position="top")
    inputs = ["-ss", f"{start:.2f}", *(["-stream_loop", str(loops)] if loops else []), "-i", str(src),
              "-i", str(hook_png)]
    fg = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps=30[v0];"
          f"[v0][1:v]overlay=0:0[v1]")
    last = "[v1]"
    if cta.strip():
        cta_png = render_text_png(cta, work / f"{out.stem}_cta.png", position="bottom", size=60)
        inputs += ["-i", str(cta_png)]
        fg += f";[v1][2:v]overlay=0:0:enable='gte(t,{max(0.0, length - 3):.2f})'[v2]"
        last = "[v2]"
    audio_idx = 3 if cta.strip() else 2
    inputs += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    await _run("ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", fg,
               "-map", last, "-map", f"{audio_idx}:a", "-t", f"{length:.2f}",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart", str(out))
    return {"path": str(out), "duration_s": round(await _duration(out), 2), "width": W, "height": H,
            "looped": bool(loops)}


async def make_reel(video_url: str, hook: str, cta: str = "", start: float = 0.0,
                    max_seconds: float = MAX_SECONDS, host: bool = True) -> dict:
    """Download an existing store video → render a reel → host it → return the public URL."""
    if not video_url.startswith("https://"):
        raise ReelError("video_url must be an https URL (take it from list_store_videos)")
    if not hook.strip():
        raise ReelError("a hook line is required — the first line viewers read")
    work = Path(tempfile.mkdtemp(prefix="reel_"))
    try:
        src = work / "source.mp4"
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as c:
            r = await c.get(video_url)
            r.raise_for_status()
            src.write_bytes(r.content)
        out = work / f"reel_{uuid.uuid4().hex[:8]}.mp4"
        info = await render_reel(src, out, hook=hook, cta=cta, start=start, max_seconds=max_seconds)
        info["source_url"] = video_url
        if host:
            info["media_url"] = await host_video(out, alt=hook)
        return info
    finally:
        if host:
            shutil.rmtree(work, ignore_errors=True)
