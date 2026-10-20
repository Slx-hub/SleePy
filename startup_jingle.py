import logging
import sys
import time

from sleepy.audio import AudioPlayer

# Configure logging to use systemd journal
logging.basicConfig(
    level=logging.INFO,
    format='%(name)s[%(process)d]: %(levelname)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('sleepy-startup')

if __name__ == '__main__':
    logger.info("SleePy startup jingle!")
    time.sleep(2)
    
    player = AudioPlayer()
    if not player.play_sound("startup.wav"):
        logger.error("SleePy startup jingle failed")
        sys.exit(1)

    logger.info("SleePy startup jingle completed")