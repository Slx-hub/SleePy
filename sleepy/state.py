import logging
from typing import Optional

from sleepy.constants import State
from sleepy.models import PlaylistConfig


LOGGER = logging.getLogger(__name__)


class StateContainer:
    """Container for passing state around"""
    def __init__(self):
        self.current_state = State.INIT
        self.selected_playlist: Optional[PlaylistConfig] = None

        self.current_video_url: Optional[str] = None
        self.do_download: bool = False

    @property
    def current_state(self):
        return self._current_state

    @current_state.setter
    def current_state(self, value):
        self._current_state = value
        LOGGER.info("State changed to %s", self.current_state)

    @property
    def selected_playlist(self):
        return self._selected_playlist

    @selected_playlist.setter
    def selected_playlist(self, value):
        self._selected_playlist = value
        LOGGER.debug("Selected Playlist changed to %s", self.selected_playlist)

    @property
    def current_video_url(self):
        return self._current_video_url

    @current_video_url.setter
    def current_video_url(self, value):
        self._current_video_url = value
        LOGGER.debug("Video URL changed to %s", self.current_video_url)

    @property
    def do_download(self):
        return self._do_download

    @do_download.setter
    def do_download(self, value):
        self._do_download = value
        LOGGER.debug("Download flag changed to %s", self.do_download)