"""Local server that downloads a YouTube video as WAV and transfers it to SleePy via scp."""

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
_SCP_TIMEOUT = 120        # seconds for scp
_FFMPEG_TIMEOUT = 300     # seconds for the trim pass
_MAX_START_SECONDS = 86400
# ~0.5 s of 44.1 kHz stereo PCM. Below this the cut ate the whole file, which
# means the start offset landed past the end of the video.
_MIN_WAV_BYTES = 100_000

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


def _trim_wav(file_path: Path, start_seconds: float) -> None:
    """Drop the first `start_seconds` of a WAV file, in place.

    PCM is constant-bitrate, so an input seek plus a stream copy is sample-exact
    and needs no re-encode. The trimmed file takes over the original name so the
    clean video title is what lands on the Pi.
    """
    trimmed = file_path.with_suffix(".trimmed.wav")
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

    size = trimmed.stat().st_size if trimmed.exists() else 0
    if size < _MIN_WAV_BYTES:
        trimmed.unlink(missing_ok=True)
        LOGGER.error(f"Trim left only {size} bytes of {file_path.name}")
        raise HTTPException(
            status_code=400,
            detail=f"Nothing left after cutting {start_seconds:g}s "
                   f"— is the start time past the end of the video?"
        )

    trimmed.replace(file_path)
    LOGGER.info(f"Trimmed {file_path.name} down to {size} bytes")


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
                "--extract-audio",
                "--audio-format", "wav",
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

        wav_files = list(job_dir.glob("*.wav"))
        LOGGER.info(f"Found {len(wav_files)} WAV files: {wav_files}")
        
        if not wav_files:
            LOGGER.error(f"No WAV files found in {job_dir}")
            raise HTTPException(status_code=500, detail="yt-dlp finished but no .wav file was found")

        transferred = []
        for file_path in wav_files:
            if req.start_seconds > 0:
                _trim_wav(file_path, req.start_seconds)

            LOGGER.info(f"Transferring {file_path} to {_SCP_DEST}")
            scp = subprocess.run(
                ["scp", str(file_path), _SCP_DEST],
                capture_output=True,
                text=True,
                timeout=_SCP_TIMEOUT,
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
