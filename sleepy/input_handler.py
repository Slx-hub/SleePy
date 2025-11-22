"""Keyboard input handling."""

import logging
import select
import sys
import termios
import tty
from typing import Optional

LOGGER = logging.getLogger(__name__)


class KeyboardPoller:
    """Context manager for raw keyboard input on Unix/Linux systems."""
    
    def __init__(self):
        self.fd: Optional[int] = None
        self.old_settings: Optional[list] = None
    
    def __enter__(self):
        try:
            self.fd = sys.stdin.fileno()
            self.old_settings = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
            return self
        except Exception as e:
            LOGGER.error("Failed to initialize keyboard poller: %s", e)
            raise
    
    def __exit__(self, *args):
        if self.fd is not None and self.old_settings is not None:
            try:
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
            except Exception as e:
                LOGGER.error("Failed to restore terminal settings: %s", e)
    
    def kbhit(self) -> bool:
        """Check if a key has been pressed."""
        if self.fd is None:
            return False
        return select.select([sys.stdin], [], [], 0.1)[0] != []
    
    def getch(self) -> str:
        """Get a single character from keyboard."""
        if self.fd is None:
            return ""
        return sys.stdin.read(1)
