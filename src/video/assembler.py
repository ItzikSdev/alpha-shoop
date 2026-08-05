"""Assembles per-scene Wan2.2 clips + voiceover into one final UGC MP4 via ffmpeg.

Per scene: mux the scene's voiceover audio onto its (silent) video clip, padding
or trimming the video to match the voiceover length so speech is never cut off.
Then concat all scenes into a single vertical MP4.

Captions: the locally-installed ffmpeg build has no drawtext/libass filter, so
burned-in captions are unavailable without reinstalling ffmpeg. `burn_captions`
is therefore a no-op placeholder for now (kept in the signature so callers don't
change when a caption-capable ffmpeg is installed).
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class AssemblyError(RuntimeError):
    pass


async def _run(cmd: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise AssemblyError(f"ffmpeg failed ({proc.returncode}): {stderr.decode(errors='ignore')[-800:]}")


async def mux_scene(video_path: Path, audio_path: Path, out_path: Path) -> Path:
    """Attach `audio_path` to `video_path`, making the result exactly as long as the
    audio (the video is looped/padded with its last frame if shorter, trimmed if
    longer) so the voiceover is always heard in full."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # -stream_loop on the video input covers the common case where the voiceover is
    # longer than the ~3.4s Wan clip; -shortest then cuts to the audio length.
    await _run([
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", str(video_path),
        "-i", str(audio_path),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(out_path),
    ])
    return out_path


async def concat_scenes(scene_paths: list[Path], out_path: Path) -> Path:
    """Concatenate muxed scene MP4s into the final video. Re-encodes (concat filter)
    rather than stream-copy so scenes with slightly different frame counts join cleanly."""
    if not scene_paths:
        raise AssemblyError("concat_scenes called with no scenes")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd: list[str] = ["ffmpeg", "-y"]
    for p in scene_paths:
        cmd += ["-i", str(p)]
    n = len(scene_paths)
    streams = "".join(f"[{i}:v:0][{i}:a:0]" for i in range(n))
    filtergraph = f"{streams}concat=n={n}:v=1:a=1[v][a]"
    cmd += ["-filter_complex", filtergraph, "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", str(out_path)]
    await _run(cmd)
    return out_path


async def extract_still_frame(video_path: Path, out_path: Path, timestamp_s: float = 0.5) -> Path:
    """Grab one frame from a rendered clip as a PNG still — used by Reel's image
    pipeline (src/video/image_pipeline.py) to turn a Wan2.2 render into a single
    product image. `timestamp_s` matters a lot: Wan2.2 I2V motion tends to be
    subtle in the first ~30-40% of a clip (it conditions frame 0 on the source
    photo and ramps up from there), so a frame grabbed too early looks nearly
    identical to the input — extract_still_frame's caller should pick a
    timestamp near the END of the clip for a visibly different result."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    await _run([
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-ss", f"{timestamp_s:.3f}", "-frames:v", "1",
        str(out_path),
    ])
    return out_path


async def burn_captions(video_path: Path, lines: list[str], out_path: Path) -> Path:
    """Placeholder — the installed ffmpeg lacks drawtext/libass, so this currently
    just returns the input unchanged. Wire up real captions once a caption-capable
    ffmpeg (built with --enable-libfreetype/--enable-libass) is installed."""
    logger.info("burn_captions: skipped (ffmpeg build has no drawtext/libass); returning video unchanged")
    return video_path
