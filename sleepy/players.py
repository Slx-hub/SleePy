"""Content player implementations."""

import logging
import random
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple

from sleepy.audio import AudioPlayer
from sleepy.constants import SPECIAL_KEYS, NON_TERMINATING_KEYS
from sleepy.models import PlaylistConfig

LOGGER = logging.getLogger(__name__)


class ContentPlayer(ABC):
    """Base class for playing content."""
    
    def __init__(self, audio_player: AudioPlayer):
        self.audio_player = audio_player
        self.current_index = 0
    
    @abstractmethod
    def play(self, playlist: PlaylistConfig) -> Tuple[str, Optional[str]]:
        """Play content from playlist.
        
        Args:
            playlist: The playlist to play from.
            
        Returns:
            Tuple of (pressed_key, video_url) where video_url is only for YouTube videos.
            pressed_key is the special key pressed, or empty string if completed normally.
        """
        raise NotImplementedError


class YouTubePlayer(ContentPlayer):
    """Plays content from YouTube playlists."""
    
    def __init__(self, audio_player: AudioPlayer, youtube_auth):
        super().__init__(audio_player)
        self.youtube_auth = youtube_auth
    
    def play(self, playlist: PlaylistConfig) -> Tuple[str, Optional[str]]:
        """Play a YouTube video from the playlist."""
        items = self.youtube_auth.get_playlist_items(playlist.id)
        
        if not items:
            LOGGER.warning("Playlist is empty")
            self.audio_player.play_sound("error.wav")
            return "", None
        
        idx = self._get_index(len(items), playlist.randomize)
        item = items[idx]
        
        video_id = item['contentDetails']['videoId']
        playlist_item_id = item['id']
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        LOGGER.info("Now playing: %s", url)
        pressed_key = self.audio_player.stream_video_sound_cancellable(
            url, SPECIAL_KEYS, NON_TERMINATING_KEYS
        )
        
        # Handle post-play actions
        if (pressed_key == "" or SPECIAL_ACTIONS.get(pressed_key) == Action.SKIP_DELETE) and playlist.delete_after_play:
            self.youtube_auth.remove_playlist_item(playlist_item_id)
        else:
            self.current_index += 1
        
        return pressed_key, url
    
    @staticmethod
    def _get_index(size: int, randomize: bool) -> int:
        """Get the next index to play."""
        if randomize:
            return random.randrange(size)
        return 0


class LocalPlayer(ContentPlayer):
    """Plays content from local filesystem."""
    
    def play(self, playlist: PlaylistConfig) -> Tuple[str, Optional[str]]:
        """Play an audio file from local directory."""
        folder_path = Path(playlist.id)
        
        try:
            items = list(folder_path.iterdir())
            if not items:
                LOGGER.warning("Folder is empty: %s", folder_path)
                self.audio_player.play_sound("error.wav")
                return "", None
        except Exception as e:
            LOGGER.error("Failed to read folder %s: %s", folder_path, e)
            self.audio_player.play_sound("error.wav")
            return "", None
        
        idx = self._get_index(len(items), playlist.randomize)
        selected_file = items[idx]
        
        LOGGER.info("Now playing: %s", selected_file)
        pressed_key = self.audio_player.play_sound_cancellable(
            str(selected_file), SPECIAL_KEYS, NON_TERMINATING_KEYS
        )
        
        # Handle post-play actions
        if pressed_key == "" and playlist.delete_after_play:
            try:
                selected_file.unlink()
                LOGGER.info("Deleted file: %s", selected_file)
            except Exception as e:
                LOGGER.error("Failed to delete file %s: %s", selected_file, e)
        else:
            self.current_index += 1
        
        return pressed_key, None
    
    @staticmethod
    def _get_index(size: int, randomize: bool) -> int:
        """Get the next index to play."""
        if randomize:
            return random.randrange(size)
        return 0
