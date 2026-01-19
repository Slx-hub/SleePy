"""YouTube API authentication and management."""

import logging
import os
import pickle
from pathlib import Path
from typing import Dict, List, Optional

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from sleepy.constants import YOUTUBE_SCOPE
import time

LOGGER = logging.getLogger(__name__)


class YouTubeAuthenticator:
    """Handles YouTube API authentication and credential management."""
    
    CREDENTIALS_FILE = 'cred.json'
    TOKEN_FILE = 'token.pickle'
    
    def __init__(self, audio_player=None):
        self.audio_player = audio_player
        self.client = None
    
    def authenticate(self) -> Optional[object]:
        """Authenticate with YouTube API.
        
        Returns:
            YouTube API client, or None if authentication failed.
        """
        creds = self._load_existing_credentials()
        
        if not creds or not creds.valid:
            creds = self._refresh_or_acquire_credentials(creds)
        
        if creds:
            try:
                self.client = build('youtube', 'v3', credentials=creds)
                LOGGER.info("YouTube API authenticated successfully")
                return self.client
            except Exception as e:
                LOGGER.error("Failed to build YouTube client: %s", e)
        
        return None
    
    def _load_existing_credentials(self) -> Optional[object]:
        """Load credentials from token file if available."""
        if not Path(self.TOKEN_FILE).exists():
            return None
        
        try:
            with open(self.TOKEN_FILE, 'rb') as f:
                creds = pickle.load(f)
                LOGGER.info("Loaded credentials from %s", self.TOKEN_FILE)
                if hasattr(creds, 'expiry'):
                    LOGGER.info("Token expiry: %s", creds.expiry)
                return creds
        except Exception as e:
            LOGGER.error("Failed to load credentials: %s", e)
            return None
    
    def _refresh_or_acquire_credentials(self, creds: Optional[object]) -> Optional[object]:
        """Refresh existing credentials or acquire new ones."""
        # Try to refresh
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                LOGGER.info("Credentials refreshed successfully")
                return creds
            except Exception as e:
                LOGGER.error("Failed to refresh credentials: %s", e)
        
        # Acquire new credentials
        if self.audio_player:
            self.audio_player.play_sound("error.wav")
        
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.CREDENTIALS_FILE,
                YOUTUBE_SCOPE
            )
            creds = flow.run_console()
            
            if not creds:
                LOGGER.warning("No credentials obtained from authentication flow")
                return None
            
            LOGGER.info("New credentials acquired")
            
            # Save credentials
            with open(self.TOKEN_FILE, 'wb') as f:
                pickle.dump(creds, f)
            LOGGER.info("Credentials saved to %s", self.TOKEN_FILE)
            
            return creds
        except (KeyboardInterrupt, EOFError):
            LOGGER.warning("Authentication cancelled by user")
            return None
        except Exception as e:
            LOGGER.error("Authentication failed: %s", e)
            return None
    
    def get_playlist_items(self, playlist_id: str) -> Optional[List[Dict]]:
        """Fetch items from a YouTube playlist.
        
        Args:
            playlist_id: YouTube playlist ID.
            
        Returns:
            List of playlist items or None if failed.
        """
        if not self.client:
            LOGGER.error("YouTube client not initialized")
            return None
        
        try:
            request = self.client.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=playlist_id,
                maxResults=50
            )
            response = request.execute()
            items = response.get('items', [])
            LOGGER.info("Found %d items in playlist", len(items))
            return items
        except Exception as e:
            LOGGER.error("Failed to fetch playlist items: %s", e)
            return None
    
    def get_video_title(self, video_id: str) -> Optional[str]:
        """Get the title of a YouTube video by ID.
        
        Args:
            video_id: YouTube video ID.
            
        Returns:
            The video title or None if failed.
        """
        if not self.client:
            LOGGER.error("YouTube client not initialized")
            return None
        
        try:
            request = self.client.videos().list(
                part="snippet",
                id=video_id
            )
            response = request.execute()
            videos = response.get('items', [])
            if videos:
                title = videos[0]['snippet']['title']
                LOGGER.info("Fetched video title for %s: %s", video_id, title)
                return title
            return None
        except Exception as e:
            LOGGER.error("Failed to fetch video title for %s: %s", video_id, e)
            return None
    
    def get_playlist_item_count(self, playlist_id: str) -> Optional[int]:
        """Get the count of items in a YouTube playlist.
        
        Args:
            playlist_id: YouTube playlist ID.
            
        Returns:
            Count of items in the playlist, or None if failed.
        """
        if not self.client:
            LOGGER.error("YouTube client not initialized")
            return None
        
        try:
            request = self.client.playlists().list(
                part="contentDetails",
                id=playlist_id
            )
            response = request.execute()
            playlists = response.get('items', [])
            if playlists:
                count = playlists[0]['contentDetails']['itemCount']
                LOGGER.info("Playlist %s has %d items", playlist_id, count)
                return count
            return None
        except Exception as e:
            LOGGER.error("Failed to fetch playlist count: %s", e)
            return None
    
    def get_playlist_item_by_index(self, playlist_id: str, index: int) -> Optional[Dict]:
        """Get a specific item from a YouTube playlist by index.
        
        Args:
            playlist_id: YouTube playlist ID.
            index: Zero-based index of the item to fetch.
            
        Returns:
            The playlist item or None if failed.
        """
        if not self.client:
            LOGGER.error("YouTube client not initialized")
            return None
        
        try:
            # Calculate page number (50 items per page)
            page_num = index // 50
            index_in_page = index % 50
            
            request = self.client.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=playlist_id,
                maxResults=50
            )
            
            # Paginate to the correct page
            for _ in range(page_num):
                response = request.execute()
                page_token = response.get('nextPageToken')
                if not page_token:
                    return None
                request = self.client.playlistItems().list(
                    part="snippet,contentDetails",
                    playlistId=playlist_id,
                    maxResults=50,
                    pageToken=page_token
                )
            
            response = request.execute()
            items = response.get('items', [])
            if len(items) > index_in_page:
                LOGGER.info("Fetched item at index %d from playlist", index)
                return items[index_in_page]
            return None
        except Exception as e:
            LOGGER.error("Failed to fetch playlist item at index %d: %s", index, e)
            return None
    
    def remove_playlist_item(self, item_id: str) -> bool:
        """Remove an item from a YouTube playlist.
        
        Args:
            item_id: YouTube playlist item ID.
            
        Returns:
            True if successful, False otherwise.
        """
        if not self.client:
            LOGGER.error("YouTube client not initialized")
            return False
        
        try:
            self.client.playlistItems().delete(id=item_id).execute()
            # If execute() completes without exception, deletion succeeded
            time.sleep(1)
            LOGGER.info("Removed playlist item: %s", item_id)
            return True
        except Exception as e:
            LOGGER.error("Failed to remove playlist item %s: %s", item_id, e)
            raise
