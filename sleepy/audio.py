"""Audio playback and sound effects management."""

import logging
import subprocess
import time
from pathlib import Path
from typing import List

from sleepy.input_handler import KeyboardPoller

LOGGER = logging.getLogger(__name__)


class AudioPlayer:
    """Handles audio playback and sound effects."""
    
    SOUND_DIR = Path('./sounds')
    APLAY_CMD = 'aplay'
    MPV_CMD = 'mpv'
    
    # Volume control settings
    APLAY_VOLUME = 100  # Percentage (0-100)
    MPV_VOLUME = 100    # Percentage (0-100)
    
    def __init__(self, mute: bool = False):
        self.mute = mute
    
    def play_sound(self, sound_file: str) -> None:
        """Play a sound effect file."""
        if self.mute:
            return
        
        sound_path = self.SOUND_DIR / sound_file
        try:
            subprocess.run(
                [self.APLAY_CMD, '-v', str(self.APLAY_VOLUME), str(sound_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
        except FileNotFoundError:
            LOGGER.error("Audio player not found: %s", self.APLAY_CMD)
        except Exception as e:
            LOGGER.error("Failed to play sound %s: %s", sound_file, e)
    
    def play_sound_cancellable(self, filepath: str, action_keys: List[str]) -> str:
        """Play a sound file, allowing cancellation via special keys."""
        return self._run_cancellable_process(
            [self.APLAY_CMD, '-v', str(self.APLAY_VOLUME), filepath],
            action_keys
        )
    
    def stream_video_sound_cancellable(
        self, url: str, action_keys: List[str]
    ) -> str:
        """Stream video audio, allowing cancellation via special keys."""
        return self._run_cancellable_process(
            [
                self.MPV_CMD,
                '--no-video',
                f'--volume={self.MPV_VOLUME}',
                url
            ],
            action_keys
        )
    
    @staticmethod
    def _run_cancellable_process(cmd: List[str], action_keys: List[str]) -> str:
        """Run a process, allowing cancellation via special keys.
        
        Returns:
            The key pressed to cancel, or empty string if process completed normally.
        """
        try:
            import os
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setpgrp if hasattr(os, 'setpgrp') else None
            )
        except Exception as e:
            LOGGER.error("Failed to start process %s: %s", ' '.join(cmd), e)
            return ""
        
        LOGGER.info(
            "Started process: %s. Waiting for keys: %s",
            ' '.join(cmd), action_keys
        )
        
        try:
            with KeyboardPoller() as kp:
                while proc.poll() is None:
                    if kp.kbhit():
                        key = kp.getch()
                        if key in action_keys:
                            LOGGER.info("Key '%s' pressed, terminating process.", key)
                            proc.terminate()
                            try:
                                proc.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                LOGGER.warning("Process did not terminate, killing.")
                                proc.kill()
                            return key
                    time.sleep(0.1)
        except Exception as e:
            LOGGER.error("Error while monitoring process: %s", e)
            proc.terminate()
        
        return ""
