"""Configuration management."""

import logging
from pathlib import Path
from typing import Dict

import yaml

from sleepy.models import PlaylistConfig

LOGGER = logging.getLogger(__name__)


class ConfigManager:
    """Manages application configuration."""
    
    CONFIG_FILE = 'config.yaml'
    
    def __init__(self):
        self.playlists: Dict[str, PlaylistConfig] = {}
        self.log_level = 'INFO'
    
    def load(self) -> bool:
        """Load configuration from YAML file.
        
        Returns:
            True if successful, False otherwise.
        """
        try:
            with open(self.CONFIG_FILE) as f:
                config = yaml.safe_load(f)
                if not config:
                    LOGGER.error("Configuration file is empty")
                    return False
            
            # Load log level
            self.log_level = config.get('LogLevel', 'INFO').upper()
            log_level = getattr(logging, self.log_level, logging.INFO)
            logging.basicConfig(level=log_level)
            LOGGER.setLevel(log_level)
            LOGGER.info("Log level set to %s", self.log_level)
            
            # Load playlists
            self.playlists = {}
            playlist_data = config.get('Playlists', {})
            
            for key, data in playlist_data.items():
                try:
                    playlist = PlaylistConfig(
                        key=key,
                        name=data.get('name', f'Playlist {key}'),
                        id=data.get('id', ''),
                        delete_after_play=data.get('delete_after_play', False),
                        shutdown_after_play=data.get('shutdown_after_play', False),
                        randomize=data.get('randomize', False)
                    )
                    if not playlist.id:
                        LOGGER.warning("Playlist '%s' has no ID, skipping", key)
                        continue
                    self.playlists[key] = playlist
                except Exception as e:
                    LOGGER.error("Failed to load playlist '%s': %s", key, e)
            
            LOGGER.info("Configuration loaded with %d playlists", len(self.playlists))
            return True
        
        except FileNotFoundError:
            LOGGER.error("Configuration file not found: %s", self.CONFIG_FILE)
            return False
        except Exception as e:
            LOGGER.error("Failed to load configuration: %s", e)
            return False
