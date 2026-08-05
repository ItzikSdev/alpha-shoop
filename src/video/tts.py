"""Voiceover synthesis for scene audio.

No neural TTS (Piper/Coqui/Kokoro/Bark) is installed on this machine, so v1 uses
macOS's built-in `say` — free, zero-setup, always available — piped through the
`ffmpeg` that's already installed to produce a clean wav. Swap the body of
`synthesize_voiceover` for a neural TTS call later; the signature won't need to change.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_VOICE = "Samantha"  # clear, natural-ish default macOS voice


class TTSError(RuntimeError):
    pass


async def _run(cmd: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise TTSError(f"{cmd[0]} failed ({proc.returncode}): {stderr.decode(errors='ignore')[:500]}")


async def synthesize_voiceover(text: str, out_path: Path, voice: str = _DEFAULT_VOICE, rate_wpm: int = 175) -> Path:
    """Renders `text` to a wav file at `out_path`. Raises TTSError on failure —
    callers should treat a missing voiceover as fatal for that scene, not silently
    ship a mute ad."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    aiff_path = out_path.with_suffix(".aiff")
    try:
        await _run(["say", "-v", voice, "-r", str(rate_wpm), "-o", str(aiff_path), text])
        await _run(["ffmpeg", "-y", "-i", str(aiff_path), "-ar", "44100", "-ac", "1", str(out_path)])
        return out_path
    finally:
        aiff_path.unlink(missing_ok=True)


async def voiceover_duration_s(path: Path) -> float:
    """ffprobe the rendered voiceover so the assembler can time video/caption cuts to it."""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise TTSError(f"ffprobe failed: {stderr.decode(errors='ignore')[:300]}")
    return float(stdout.decode().strip())
