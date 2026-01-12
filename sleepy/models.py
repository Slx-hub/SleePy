"""Data models for SleePy application."""

from dataclasses import dataclass


@dataclass
class PlaylistConfig:
    """Configuration for a single playlist."""
    key: str
    name: str
    id: str
    delete_after_play: bool = False
    shutdown_after_play: bool = False
    randomize: bool = False
    download_after_play: bool = False
    
    def is_local(self) -> bool:
        """Check if this is a local file playlist."""
        return self.id.startswith('./')
