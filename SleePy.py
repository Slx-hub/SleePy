#!/usr/bin/env python3
"""
SleePy: A YouTube playlist automation tool for sleep and relaxation.

This application manages playlists and plays content with customizable
actions based on special key presses.
"""

import logging
import sys

from sleepy import (
    AudioPlayer,
    ConfigManager,
    StateMachine,
    YouTubeAuthenticator,
)


def setup_logging() -> None:
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%d.%m.%Y %H:%M:%S"
    )


def main() -> None:
    """Main entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        config = ConfigManager()
        audio_player = AudioPlayer(mute=False)
        youtube_auth = YouTubeAuthenticator(audio_player)
        state_machine = StateMachine(config, audio_player, youtube_auth)
        
        state_machine.run()
    except Exception as e:
        logger.error("Fatal error: %s", e)
        sys.exit(1)


if __name__ == '__main__':
    main()
