"""YouTube video downloader."""

import logging
import subprocess
from datetime import datetime
from pathlib import Path

from sleepy.constants import LOCAL_ASMR_DIR

LOGGER = logging.getLogger(__name__)


class YouTubeDownloader:
    """Handles downloading YouTube videos as audio files."""
    
    def __init__(self, audio_player=None):
        self.audio_player = audio_player
    
    def download(self, url: str) -> bool:
        """Download a YouTube video as audio.
        
        Args:
            url: The YouTube video URL to download.
            
        Returns:
            True if successful, False otherwise.
        """
        LOGGER.info("Downloading video: %s", url)
        
        try:
            # Ensure output directory exists
            Path(LOCAL_ASMR_DIR).mkdir(parents=True, exist_ok=True)
            
            cmd = [
                'yt-dlp',
                '--extract-audio',
                '--audio-format', 'wav',
                '-P', LOCAL_ASMR_DIR,
                url
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=300
            )
            
            if result.returncode == 0:
                LOGGER.info("Video downloaded successfully")
                return True
            else:
                error_msg = result.stderr.decode()
                LOGGER.error("Video download failed: %s", error_msg)
                self._write_download_failed_log(url, error_msg)
                return False
        except subprocess.TimeoutExpired:
            error_msg = "Download timed out"
            LOGGER.error("Video download timed out")
            self._write_download_failed_log(url, error_msg)
            return False
        except Exception as e:
            error_msg = str(e)
            LOGGER.error("Failed to download video: %s", error_msg)
            self._write_download_failed_log(url, error_msg)
            return False
    
    @staticmethod
    def _write_download_failed_log(url: str, reason: str) -> None:
        """Write a download failure log file.
        
        Args:
            url: The URL that failed to download.
            reason: The reason for the failure.
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"download_failed_{timestamp}.log"
            log_path = Path(LOCAL_ASMR_DIR) / log_filename
            
            with open(log_path, 'w') as f:
                f.write(f"URL: {url}\n")
                f.write(f"Reason: {reason}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            
            LOGGER.info("Download failure logged to %s", log_path)
        except Exception as e:
            LOGGER.error("Failed to write download failure log: %s", e)
