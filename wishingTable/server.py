"""Local server that downloads a YouTube video's audio and transfers it to SleePy via scp.

The audio is kept in YouTube's own format (usually Opus, ~1 MB per minute)
rather than converted to WAV, which was ~10x bigger with no quality gain.
"""

import glob
import logging
import os
import re
import subprocess
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)

app = FastAPI()

# Only listen on 127.0.0.1 — still allow any origin so the Violentmonkey
# request (which may arrive without an Origin header or from the extension
# context) is not blocked.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

_YOUTUBE_RE = re.compile(r"^https://(www\.)?youtube\.com/watch\?")
_SCP_DEST = "SleePy:~/Music/local/input/"
_DOWNLOAD_TIMEOUT = 600   # seconds for yt-dlp
_FFMPEG_TIMEOUT = 300     # seconds for the trim pass
# scp gets a fixed allowance plus time proportional to the file size. The Pi
# (3B+ on Wi-Fi) takes uploads at ~3.4 MB/s; budgeting for 1 MB/s leaves ~3x
# headroom. A killed scp leaves a truncated file on the Pi, so err on the long side.
_SCP_BASE_TIMEOUT = 60
_SCP_MIN_BYTES_PER_SEC = 1_000_000
_MAX_START_SECONDS = 86400
# Shorter than this after trimming means the cut ate the whole file, i.e. the
# start offset landed past the end of the video.
_MIN_TRIMMED_SECONDS = 1.0

# Prepend common choco-installed tool paths so yt-dlp subprocess finds node + ffmpeg
_EXTRA_PATHS = [
    r"C:\Program Files\nodejs",
    r"C:\ProgramData\chocolatey\bin",
    r"C:\ffmpeg\bin",
]
_ENV = os.environ.copy()
_ENV["PATH"] = os.pathsep.join(_EXTRA_PATHS) + os.pathsep + _ENV.get("PATH", "")


class DownloadRequest(BaseModel):
    url: str
    start_seconds: float = 0.0

    @field_validator("url")
    @classmethod
    def must_be_youtube_watch(cls, v: str) -> str:
        if not _YOUTUBE_RE.match(v):
            raise ValueError("Only YouTube watch URLs are accepted")
        return v

    @field_validator("start_seconds")
    @classmethod
    def must_be_a_sane_offset(cls, v: float) -> float:
        if v < 0:
            raise ValueError("start_seconds must not be negative")
        if v > _MAX_START_SECONDS:
            raise ValueError("start_seconds is unreasonably large")
        return v


def _duration(file_path: Path) -> float:
    """Length of an audio file in seconds, or 0 if ffprobe can't tell."""
    probe = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env=_ENV,
    )
    try:
        return float(probe.stdout.strip())
    except ValueError:
        return 0.0


def _trim_audio(file_path: Path, start_seconds: float) -> None:
    """Drop the first `start_seconds` of an audio file, in place.

    An input seek plus a stream copy needs no re-encode; the cut lands on the
    nearest packet boundary (20 ms for Opus). The trimmed file takes over the
    original name so the clean video title is what lands on the Pi.
    """
    trimmed = file_path.with_name(f"{file_path.stem}.trimmed{file_path.suffix}")
    LOGGER.info(f"Trimming {start_seconds:g}s off the start of {file_path.name}")

    ff = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-ss", f"{start_seconds:.3f}",
            "-i", str(file_path),
            "-c", "copy",
            str(trimmed),
        ],
        capture_output=True,
        text=True,
        timeout=_FFMPEG_TIMEOUT,
        env=_ENV,
    )

    LOGGER.debug(f"ffmpeg stderr: {ff.stderr}")
    LOGGER.debug(f"ffmpeg returncode: {ff.returncode}")

    if ff.returncode != 0:
        trimmed.unlink(missing_ok=True)
        LOGGER.error(f"ffmpeg trim failed: {ff.stderr.strip()}")
        raise HTTPException(
            status_code=500,
            detail=f"Trim failed: {ff.stderr.strip()[:200]}"
        )

    length = _duration(trimmed) if trimmed.exists() else 0.0
    if length < _MIN_TRIMMED_SECONDS:
        trimmed.unlink(missing_ok=True)
        LOGGER.error(f"Trim left only {length:.1f}s of {file_path.name}")
        raise HTTPException(
            status_code=400,
            detail=f"Nothing left after cutting {start_seconds:g}s "
                   f"— is the start time past the end of the video?"
        )

    trimmed.replace(file_path)
    LOGGER.info(f"Trimmed {file_path.name} down to {length:.0f}s")


@app.post("/download")
def download(req: DownloadRequest) -> dict:
    job_dir = Path(tempfile.gettempdir()) / f"sleepy_{uuid.uuid4().hex}"
    job_dir.mkdir()
    LOGGER.info(f"Download request for: {req.url}"
                f"{f' (cut first {req.start_seconds:g}s)' if req.start_seconds > 0 else ''}")
    LOGGER.info(f"Working dir: {job_dir}")

    try:
        dl = subprocess.run(
            [
                "yt-dlp",
                # Audio-only stream, extracted as-is (no --audio-format):
                # usually .opus, sometimes .m4a.
                "--format", "bestaudio/best",
                "--extract-audio",
                # A watch URL opened from a playlist also carries &list=...;
                # without this yt-dlp downloads the whole list.
                "--no-playlist",
                "-o", str(job_dir / "%(title)s.%(ext)s"),
                "--cookies-from-browser", "firefox",  # or chromium if Firefox not available
                req.url
            ],
            capture_output=True,
            text=True,
            timeout=_DOWNLOAD_TIMEOUT,
            env=_ENV,
        )

        LOGGER.debug(f"yt-dlp stdout: {dl.stdout}")
        LOGGER.debug(f"yt-dlp stderr: {dl.stderr}")
        LOGGER.debug(f"yt-dlp returncode: {dl.returncode}")

        if dl.returncode != 0:
            error_detail = dl.stderr.strip()
            LOGGER.error(f"yt-dlp failed: {error_detail}")
            
            # Provide helpful error messages
            if "n challenge solving failed" in error_detail:
                detail = "JavaScript runtime needed. Install Node.js or try a different video (Shorts may not have audio)."
            elif "nsig extraction failed" in error_detail or "Requested format is not available" in error_detail:
                detail = "Video format not available (may be Shorts or restricted). Try a music/podcast/ASMR video."
            else:
                detail = error_detail[:200]  # Cap error message length
            
            raise HTTPException(status_code=500, detail=detail)

        # yt-dlp deletes its intermediate download after extracting, so
        # whatever is left in the job dir is the audio.
        audio_files = [p for p in job_dir.iterdir() if p.is_file()]
        LOGGER.info(f"Found {len(audio_files)} audio files: {audio_files}")

        if not audio_files:
            LOGGER.error(f"No audio files found in {job_dir}")
            raise HTTPException(status_code=500, detail="yt-dlp finished but no audio file was found")

        transferred = []
        for file_path in audio_files:
            if req.start_seconds > 0:
                _trim_audio(file_path, req.start_seconds)

            scp_timeout = _SCP_BASE_TIMEOUT + file_path.stat().st_size // _SCP_MIN_BYTES_PER_SEC
            LOGGER.info(f"Transferring {file_path} to {_SCP_DEST} (timeout {scp_timeout}s)")
            scp = subprocess.run(
                ["scp", str(file_path), _SCP_DEST],
                capture_output=True,
                text=True,
                timeout=scp_timeout,
            )
            LOGGER.debug(f"scp stdout: {scp.stdout}")
            LOGGER.debug(f"scp stderr: {scp.stderr}")
            LOGGER.debug(f"scp returncode: {scp.returncode}")

            if scp.returncode != 0:
                LOGGER.error(f"scp failed for {file_path.name}: {scp.stderr.strip()}")
                raise HTTPException(status_code=500, detail=f"{file_path.name}: {scp.stderr.strip()}")

            transferred.append(file_path.name)
            LOGGER.info(f"Transferred: {file_path.name}")

        LOGGER.info(f"Success: {len(transferred)} file(s) transferred")
        return {
            "status": "ok",
            "file": transferred[0],
            "files": transferred,
            "start_seconds": req.start_seconds,
        }

    except HTTPException:
        raise
    except subprocess.TimeoutExpired as e:
        # The default message starts with the whole argv, which is all the
        # button has room to show.
        tool = Path(e.cmd[0]).stem
        LOGGER.error(f"{tool} timed out after {e.timeout:.0f}s")
        raise HTTPException(status_code=504, detail=f"{tool} timed out after {e.timeout:.0f}s")
    except Exception as e:
        LOGGER.exception(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        LOGGER.debug(f"Cleaning up {job_dir}")
        for f in job_dir.glob("*"):
            f.unlink(missing_ok=True)
        try:
            job_dir.rmdir()
        except OSError:
            pass
