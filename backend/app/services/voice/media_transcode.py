"""Transcode interview recordings to browser-friendly formats via ffmpeg."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from backend.app.core.logging_config import get_logger

logger = get_logger("services.voice.transcode")


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _run_ffmpeg(args: list[str], *, timeout: int = 180) -> bytes | None:
    if not ffmpeg_available():
        return None
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            logger.warning(
                "ffmpeg failed (%s): %s",
                result.returncode,
                (result.stderr or b"")[:500].decode(errors="replace"),
            )
            return None
        out_path = Path(args[-1])
        if not out_path.exists() or out_path.stat().st_size == 0:
            return None
        return out_path.read_bytes()
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("ffmpeg error: %s", exc)
        return None


def transcode_audio_to_mp3(audio_bytes: bytes, *, input_suffix: str = "webm") -> bytes | None:
    with tempfile.TemporaryDirectory() as tmp:
        inp = Path(tmp) / f"input.{input_suffix.lstrip('.')}"
        out = Path(tmp) / "output.mp3"
        inp.write_bytes(audio_bytes)

        attempts: list[list[str]] = [
            [
                "ffmpeg",
                "-y",
                "-i",
                str(inp),
                "-vn",
                "-acodec",
                "libmp3lame",
                "-q:a",
                "4",
                str(out),
            ],
            [
                "ffmpeg",
                "-y",
                "-fflags",
                "+discardcorrupt",
                "-err_detect",
                "ignore_err",
                "-i",
                str(inp),
                "-vn",
                "-acodec",
                "libmp3lame",
                "-q:a",
                "4",
                str(out),
            ],
            [
                "ffmpeg",
                "-y",
                "-f",
                "matroska",
                "-i",
                str(inp),
                "-vn",
                "-acodec",
                "libmp3lame",
                "-q:a",
                "4",
                str(out),
            ],
            [
                "ffmpeg",
                "-y",
                "-f",
                "webm",
                "-i",
                str(inp),
                "-vn",
                "-acodec",
                "libmp3lame",
                "-q:a",
                "4",
                str(out),
            ],
        ]

        for args in attempts:
            result = _run_ffmpeg(args, timeout=120)
            if result:
                return result
        return None


def transcode_video_to_mp4(video_bytes: bytes, *, input_suffix: str = "webm") -> bytes | None:
    with tempfile.TemporaryDirectory() as tmp:
        inp = Path(tmp) / f"input.{input_suffix.lstrip('.')}"
        out = Path(tmp) / "output.mp4"
        inp.write_bytes(video_bytes)
        return _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(inp),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "28",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                str(out),
            ],
            timeout=300,
        )
