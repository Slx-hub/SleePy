"""Audio playback and sound effects management."""

import logging
import subprocess
import time
from pathlib import Path
from typing import List, Tuple

from sleepy.constants import (
    AUDIO_SOUND_DIR,
    AUDIO_VOLUME_LEVEL,
)
from sleepy.input_handler import KeyboardPoller

LOGGER = logging.getLogger(__name__)


class AudioPlayer:
    """Handles audio playback and sound effects."""

    APLAY_CMD = 'aplay'
    MPV_CMD = 'mpv'
    
    RIGHT_ARROW = '\x1b[C'
    
    def __init__(self, mute: bool = False):
        self.mute = mute
        self._set_system_volume()
    
    @staticmethod
    def _set_system_volume() -> None:
        """Set system ALSA volume on startup."""
        try:
            subprocess.run(
                ['amixer', 'sset', 'Master', f'{AUDIO_VOLUME_LEVEL}%'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
            LOGGER.info("System volume set to %d%%", AUDIO_VOLUME_LEVEL)
        except Exception as e:
            LOGGER.warning("Failed to set system volume: %s", e)
    
    def play_sound(self, sound_file: str) -> None:
        """Play a sound effect file."""
        if self.mute:
            return
        
        sound_path = Path(AUDIO_SOUND_DIR) / sound_file
        try:
            subprocess.run(
                [self.APLAY_CMD, str(sound_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
        except FileNotFoundError:
            LOGGER.error("Audio player not found: %s", self.APLAY_CMD)
        except Exception as e:
            LOGGER.error("Failed to play sound %s: %s", sound_file, e)
    
    def play_sound_cancellable(self, filepath: str, action_keys: List[str], non_terminating_keys: List[str] = None) -> str:
        """Play a sound file, allowing cancellation via special keys.
        
        Args:
            filepath: Path to the sound file.
            action_keys: Keys that can cancel playback.
            non_terminating_keys: Keys that don't stop playback (default: empty list).
        """
        if non_terminating_keys is None:
            non_terminating_keys = []
        return self._run_cancellable_process(
            [self.APLAY_CMD, str(filepath)],
            action_keys,
            non_terminating_keys
        )[0]
    
    def stream_video_sound_cancellable(
        self, url: str, action_keys: List[str], non_terminating_keys: List[str] = None
    ) -> Tuple[str, bool]:
        """Stream video audio, allowing cancellation via special keys.
        
        Args:
            url: YouTube URL to stream.
            action_keys: Keys that can cancel playback.
            non_terminating_keys: Keys that don't stop playback (default: empty list).
        """
        if non_terminating_keys is None:
            non_terminating_keys = []
        return self._run_cancellable_process(
            [
                self.MPV_CMD,
                '--no-video',
                url
            ],
            action_keys,
            non_terminating_keys
        )
    
    @staticmethod
    def _run_cancellable_process(cmd: List[str], action_keys: List[str], non_terminating_keys: List[str] = None) -> Tuple[str, bool]:
        """Run a process, allowing cancellation via special keys.
        
        Args:
            cmd: Command to execute.
            action_keys: Keys that can cancel playback.
            non_terminating_keys: Keys that don't stop playback (default: empty list).
        
        Returns:
            The key pressed to cancel, or empty string if process completed normally.
        """
        if non_terminating_keys is None:
            non_terminating_keys = []

        doDownload = False

        try:
            import os
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setpgrp if hasattr(os, 'setpgrp') else None
            )
        except Exception as e:
            LOGGER.error("Failed to start process %s: %s", ' '.join(cmd), e)
            return "", doDownload
        
        LOGGER.info(
            "Started process: %s. Waiting for keys: %s",
            ' '.join(cmd), action_keys
        )
        
        try:
            with KeyboardPoller() as kp:
                while proc.poll() is None:
                    if kp.kbhit():
                        key = kp.getch()
                        if  key in non_terminating_keys:
                            LOGGER.info("Key '%s' pressed (non-terminating).", key)
                            # Return the key but don't terminate the process
                            doDownload = True
                        elif key in action_keys:
                            LOGGER.info("Key '%s' pressed, terminating process.", key)
                            proc.terminate()
                            try:
                                proc.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                LOGGER.warning("Process did not terminate, killing.")
                                proc.kill()
                            return key, doDownload
                    time.sleep(0.1)
        except Exception as e:
            LOGGER.error("Error while monitoring process: %s", e)
            proc.terminate()
        
        return non_terminating_action, doDownload
