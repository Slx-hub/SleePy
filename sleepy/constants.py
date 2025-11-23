"""Constants and enums for SleePy application."""

from enum import Enum


class Action(str, Enum):
    """Special key actions."""
    SHUTDOWN = 'shutdown'
    QUIT = 'quit'
    SELECT = 'select'
    SKIP = 'skip'


class State(str, Enum):
    """Application states."""
    INIT = 'init'
    SELECT = 'select'
    PLAY = 'play'
    WAIT = 'wait'
    SHUTDOWN = 'shutdown'
    QUIT = 'quit'


SPECIAL_ACTIONS = {
    '*': Action.SHUTDOWN,
    '/': Action.QUIT,
    '-': Action.SELECT,
    '+': Action.SKIP,
}

SPECIAL_KEYS = list(SPECIAL_ACTIONS.keys())
YOUTUBE_SCOPE = ['https://www.googleapis.com/auth/youtube.force-ssl']

# Audio settings
AUDIO_VOLUME_LEVEL = 80
AUDIO_SOUND_DIR = './sounds'