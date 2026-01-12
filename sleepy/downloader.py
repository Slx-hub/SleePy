"""YouTube video downloader."""

import logging
import subprocess
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
        if self.audio_player:
            self.audio_player.play_sound("ping.wav")
        
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
                if self.audio_player:
                    self.audio_player.play_sound("ok.wav")
                return True
            else:
                LOGGER.error("Video download failed: %s", result.stderr.decode())
                if self.audio_player:
                    self.audio_player.play_sound("error.wav")
                return False
        except subprocess.TimeoutExpired:
            LOGGER.error("Video download timed out")
            if self.audio_player:
                self.audio_player.play_sound("error.wav")
            return False
        except Exception as e:
            LOGGER.error("Failed to download video: %s", e)
            if self.audio_player:
                self.audio_player.play_sound("error.wav")
            return False
