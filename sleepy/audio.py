"""Audio playback and sound effects management."""

import logging
import subprocess
import time
from pathlib import Path
from typing import List
from sleepy.state import StateContainer

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
        self.set_mute(mute)

    def set_mute(self, mute: bool = True):
        self.mute = mute
        if mute:
            self._set_system_volume(0)
        else:
            self._set_system_volume(AUDIO_VOLUME_LEVEL)
    
    @staticmethod
    def _set_system_volume(volume) -> None:
        """Set system ALSA volume on startup."""
        try:
            result = subprocess.run(
                ['amixer', 'sset', 'Master', f'{volume}%'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            if result.returncode != 0:
                LOGGER.warning("Failed to set system volume: %s", result.stderr.strip())
                return
            LOGGER.info("System volume set to %d%%", volume)
        except Exception as e:
            LOGGER.warning("Failed to set system volume: %s", e)

    def play_sound(self, sound_file: str) -> bool:
        """Play a sound effect file. Returns False if playback failed."""
        if self.mute:
            return True

        sound_path = Path(AUDIO_SOUND_DIR) / sound_file
        try:
            result = subprocess.run(
                [self.APLAY_CMD, str(sound_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
        except FileNotFoundError:
            LOGGER.error("Audio player not found: %s", self.APLAY_CMD)
            return False
        except Exception as e:
            LOGGER.error("Failed to play sound %s: %s", sound_file, e)
            return False

        if result.returncode != 0:
            LOGGER.error(
                "Failed to play sound %s (exit %d): %s",
                sound_file, result.returncode, result.stderr.strip()
            )
            return False
        return True
    
    def play_sound_cancellable(self, state: StateContainer, action_keys: List[str], non_terminating_keys: List[str] = []) -> str:
        """Play a sound file, allowing cancellation via special keys.
        
        Args:
            state: Program state containing the audio file path.
            action_keys: Keys that can cancel playback.
            non_terminating_keys: Keys that don't stop playback (default: empty list).
        """
        path = str(state.current_audio_file)
        # aplay only understands WAV (the UI sounds and older tracks); newer
        # tracks keep YouTube's compressed audio (Opus/M4A), which needs mpv.
        if path.lower().endswith('.wav'):
            cmd = [self.APLAY_CMD, path]
        else:
            cmd = [self.MPV_CMD, '--no-video', path]
        return self._run_cancellable_process(
            cmd,
            action_keys,
            non_terminating_keys,
            state
        )
    
    def stream_video_sound_cancellable(
        self, state: StateContainer, action_keys: List[str], non_terminating_keys: List[str] = []) -> str:
        """Stream video audio, allowing cancellation via special keys.
        
        Args:
            state: Program state for some happy little side effects.
            action_keys: Keys that can cancel playback.
            non_terminating_keys: Keys that don't stop playback (default: empty list).
        """

        return self._run_cancellable_process(
            [
                self.MPV_CMD,
                '--no-video',
                state.current_video_url
            ],
            action_keys,
            non_terminating_keys,
            state
        )
    
    @staticmethod
    def _run_cancellable_process(cmd: List[str], action_keys: List[str], non_terminating_keys: List[str] = [], state: StateContainer = None) -> str:
        """Run a process, allowing cancellation via special keys.
        
        Args:
            cmd: Command to execute.
            action_keys: Keys that can cancel playback.
            non_terminating_keys: Keys that don't stop playback (default: empty list).
        
        Returns:
            The key pressed to cancel, or empty string if process completed normally.
        """

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
                        if  key in non_terminating_keys:
                            LOGGER.info("Key '%s' pressed (non-terminating).", key)
                            if state:
                                state.do_download = True
                        elif key in action_keys:
                            LOGGER.info("Key '%s' pressed, terminating process.", key)
                            proc.terminate()
                            try:
                                proc.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                LOGGER.warning("Process did not terminate, killing.")
                                proc.kill()
                            return key
                    time.sleep(0.1)
            # stderr isn't captured here (long mpv runs could fill the pipe), so at least log the exit code
            if proc.returncode != 0:
                LOGGER.error("Process %s exited with code %d", cmd[0], proc.returncode)
        except Exception as e:
            LOGGER.error("Error while monitoring process: %s", e)
            proc.terminate()
        
        return ""
