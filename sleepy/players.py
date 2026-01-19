"""Content player implementations."""

import logging
import random
from abc import ABC, abstractmethod
from pathlib import Path

from sleepy.audio import AudioPlayer
from sleepy.constants import SPECIAL_KEYS, NON_TERMINATING_KEYS, SPECIAL_ACTIONS, Action
from sleepy.models import PlaylistConfig
from sleepy.state import StateContainer

LOGGER = logging.getLogger(__name__)


class ContentPlayer(ABC):
    """Base class for playing content."""
    
    def __init__(self, audio_player: AudioPlayer):
        self.audio_player = audio_player
        self.current_index = 0
    
    @abstractmethod
    def play(self, state: StateContainer) -> str:
        """Play content from playlist.
        
        Args:
            state: The Programs state
            
        Returns:
            a the special key pressed, or empty string if completed normally.
        """
        raise NotImplementedError


class YouTubePlayer(ContentPlayer):
    """Plays content from YouTube playlists."""
    
    def __init__(self, audio_player: AudioPlayer, youtube_auth):
        super().__init__(audio_player)
        self.youtube_auth = youtube_auth
    
    def play(self, state: StateContainer) -> str:
        """Play a YouTube video from the playlist."""
        # Get the count of items in the playlist
        item_count = self.youtube_auth.get_playlist_item_count(state.selected_playlist.id)
        
        if not item_count or item_count == 0:
            LOGGER.warning("Playlist is empty")
            self.audio_player.play_sound("error.wav")
            return ""
        
        # Choose the index (first or random)
        idx = self._get_index(item_count, state.selected_playlist.randomize)
        
        # Fetch only the specific item at this index
        item = self.youtube_auth.get_playlist_item_by_index(state.selected_playlist.id, idx)
        
        if not item:
            LOGGER.warning("Failed to fetch playlist item at index %d", idx)
            self.audio_player.play_sound("error.wav")
            return ""
        
        video_id = item['contentDetails']['videoId']
        playlist_item_id = item['id']
        state.current_video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Get title from snippet or fetch from API if needed
        title = item.get('snippet', {}).get('title')
        if not title:
            title = self.youtube_auth.get_video_title(video_id)
        
        LOGGER.info("Now playing item %d: %s (%s)", idx, title, video_id)
        pressed_key = self.audio_player.stream_video_sound_cancellable(
            state, SPECIAL_KEYS, NON_TERMINATING_KEYS
        )
        
        # Handle post-play actions
        if (pressed_key == "" or SPECIAL_ACTIONS.get(pressed_key) == Action.SKIP_DELETE) and state.selected_playlist.delete_after_play:
            self.youtube_auth.remove_playlist_item(playlist_item_id)
        else:
            self.current_index += 1

        return pressed_key
    
    @staticmethod
    def _get_index(size: int, randomize: bool) -> int:
        """Get the next index to play."""
        if randomize:
            return random.randrange(size)
        return 0


class LocalPlayer(ContentPlayer):
    """Plays content from local filesystem."""
    
    def play(self, state: StateContainer) -> str:
        """Play an audio file from local directory."""
        folder_path = Path(state.selected_playlist.id)
        
        try:
            items = list(folder_path.iterdir())
            if not items:
                LOGGER.warning("Folder is empty: %s", folder_path)
                self.audio_player.play_sound("error.wav")
                return ""
        except Exception as e:
            LOGGER.error("Failed to read folder %s: %s", folder_path, e)
            self.audio_player.play_sound("error.wav")
            return ""
        
        idx = self._get_index(len(items), state.selected_playlist.randomize)
        selected_file = items[idx]
        
        LOGGER.info("Now playing: %s", selected_file)
        pressed_key = self.audio_player.play_sound_cancellable(
            str(selected_file), SPECIAL_KEYS, NON_TERMINATING_KEYS
        )
        
        # Handle post-play actions
        if pressed_key == "" and state.selected_playlist.delete_after_play:
            try:
                selected_file.unlink()
                LOGGER.info("Deleted file: %s", selected_file)
            except Exception as e:
                LOGGER.error("Failed to delete file %s: %s", selected_file, e)
        else:
            self.current_index += 1
        
        return pressed_key
    
    @staticmethod
    def _get_index(size: int, randomize: bool) -> int:
        """Get the next index to play."""
        if randomize:
            return random.randrange(size)
        return 0
