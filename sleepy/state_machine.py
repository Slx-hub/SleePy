"""State machine implementation."""

import logging
import os
import subprocess
import time
from typing import Optional

from sleepy.state import StateContainer
from sleepy.audio import AudioPlayer
from sleepy.config import ConfigManager
from sleepy.constants import SPECIAL_KEYS, SPECIAL_ACTIONS, Action, State
from sleepy.downloader import YouTubeDownloader
from sleepy.input_handler import KeyboardPoller
from sleepy.models import PlaylistConfig
from sleepy.players import LocalPlayer, YouTubePlayer
from sleepy.youtube import YouTubeAuthenticator

LOGGER = logging.getLogger(__name__)


class StateMachine:
    """Main application state machine."""
    
    def __init__(
        self,
        config: ConfigManager,
        audio_player: AudioPlayer,
        youtube_auth: YouTubeAuthenticator
    ):
        self.config = config
        self.audio_player = audio_player
        self.youtube_auth = youtube_auth
        self.youtube_player = YouTubePlayer(audio_player, youtube_auth)
        self.local_player = LocalPlayer(audio_player)
        self.downloader = YouTubeDownloader(audio_player)
        self.state = StateContainer()
    
    def run(self) -> None:
        """Run the application state machine."""
        try:
            while self.state.current_state != State.QUIT:
                try:
                    self._execute_state()
                except Exception as e:
                    LOGGER.error("Error in state %s: %s", self.state.current_state, e)
                    self.state.current_state = State.QUIT
        except KeyboardInterrupt:
            LOGGER.info("Interrupted by user")
    
    def _execute_state(self) -> None:
        """Execute the current state's logic."""
        if self.state.current_state == State.INIT:
            self._state_init()
        elif self.state.current_state == State.SELECT:
            self._state_select()
        elif self.state.current_state == State.PLAY:
            self._state_play()
        elif self.state.current_state == State.WAIT:
            self._state_wait()
        elif self.state.current_state == State.SHUTDOWN:
            self._state_shutdown()
    
    def _state_init(self) -> None:
        """Initialize the application."""
        LOGGER.info("Initializing application")
        self.config.load()
        self.audio_player.play_sound("up.wav")
        
        self.youtube_auth.authenticate()
        self.state.current_state = State.SELECT
        
    
    def _state_select(self) -> None:
        """Select a playlist."""
        LOGGER.info("Waiting for playlist selection")
        self.youtube_player.current_index = 0
        self.local_player.current_index = 0
        
        self.audio_player.play_sound("ping.wav")
        self.state.selected_playlist = None
        
        while not self.state.selected_playlist:
            key = self._wait_for_key()
            
            if key in self.config.playlists:
                self.state.selected_playlist = self.config.playlists[key]
                LOGGER.info("Selected playlist: %s", self.state.selected_playlist.name)
            elif self._handle_action_key(key, State.SELECT):
                return
            else:
                LOGGER.warning("Invalid key: %s", key)
                self.audio_player.play_sound("error.wav")
        
        self.state.current_state = State.PLAY
        self.audio_player.play_sound("ok.wav")
    
    def _state_play(self) -> None:
        """Play content from selected playlist."""
        if not self.state.selected_playlist:
            LOGGER.error("No playlist selected")
            self.state.current_state = State.SELECT
            return
        
        player = (
            self.local_player if self.state.selected_playlist.is_local()
            else self.youtube_player
        )
        
        try:
            pressed_key = player.play(self.state)

            if self.state.do_download and self.state.current_video_url:
                self.downloader.download(self.state.current_video_url)
                self.state.current_video_url = None
                self.state.do_download = False

            if not self._handle_action_key(pressed_key, State.PLAY) and self.state.selected_playlist.shutdown_after_play:
                self.state.current_state = State.WAIT

        except Exception as e:
            LOGGER.error("Error during PLAY:", e)
            self.state.current_state = State.QUIT
    
    def _state_wait(self) -> None:
        """Wait before shutdown."""
        LOGGER.info("Waiting before shutdown")
        pressed_key = self.audio_player.play_sound_cancellable(
            "./sounds/wait.wav", SPECIAL_KEYS
        )
        if not self._handle_action_key(pressed_key, State.PLAY):
            self.audio_player.set_mute(True)
            self.state.current_state = State.SHUTDOWN
    
    def _state_shutdown(self) -> None:
        """Shutdown the system."""
        LOGGER.info("Shutting down")
        self.audio_player.play_sound("shutdown.wav")
        try:
            subprocess.Popen(["sudo", "shutdown", "-h", "+1"])
            self.audio_player.set_mute(True)
        except Exception as e:
            LOGGER.error("Shutdown command failed: %s", e)
        self.state.current_state = State.QUIT
    
    def _state_quit(self) -> None:
        """Exit the application."""
        LOGGER.info("Exiting application")
        self.audio_player.play_sound("down.wav")
    
    def _handle_action_key(self, key: str, next_state: Optional[State] = None) -> bool:
        """Handle special action keys.
        
        Args:
            key: The key that was pressed.
            next_state: The state to transition to on SKIP or DOWNLOAD action.
            
        Returns:
            True if the key was handled, False otherwise.
        """
        action = SPECIAL_ACTIONS.get(key)
        if not action:
            return False
        
        if action == Action.SHUTDOWN:
            self.state.current_state = State.SHUTDOWN
            return True
        elif action == Action.QUIT:
            self.state.current_state = State.QUIT
            return True
        elif action == Action.SELECT:
            self.state.current_state = State.SELECT
            return True
        elif (action == Action.SKIP or action == Action.SKIP_DELETE) and next_state:
            self.state.current_state = next_state
            return True
        
        return False
    
    @staticmethod
    def _wait_for_key() -> str:
        """Wait for a key press."""
        with KeyboardPoller() as kp:
            while True:
                if kp.kbhit():
                    return kp.getch()
                time.sleep(0.1)
