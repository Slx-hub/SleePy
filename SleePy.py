import random, subprocess, time, os, pickle, yaml, sys, select, tty, termios, logging, glob
from datetime import datetime
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%d.%m.%Y %H:%M:%S")
logger = logging.getLogger(__name__)
config_playlists, youtube_auth, selected_playlist, current_state, video_index, no_sound_effects = {}, None, None, 'init', 0, False

SPECIAL_ACTIONS = {
    '*': 'shutdown',
    '/': 'quit',
    '-': 'select',
    '+': 'skip',
}

SPECIAL_KEYS = list(SPECIAL_ACTIONS.keys())

class KeyboardPoller:
    def __enter__(self):
        self.fd = sys.stdin.fileno(); self.old = termios.tcgetattr(self.fd); tty.setcbreak(self.fd); return self
    def __exit__(self, *args): termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)
    def kbhit(self): return select.select([sys.stdin], [], [], 0.1)[0] != []
    def getch(self): return sys.stdin.read(1)

load_config = lambda: (
    logger.info("Reloading config file."),
    exec("global config_playlists\nwith open('config.yaml') as f:\n    config_playlists = yaml.safe_load(f.read()).get('Playlists', {})"),
    logger.info("Config loaded.")
)

def play_sound(s): 
    if no_sound_effects:
        return
    try: subprocess.run(["aplay", f"./sounds/{s}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e: logger.error("Sound error (%s): %s", s, e)

def run_cancellable_process(cmd, action_keys):
    try:
        proc = subprocess.Popen(cmd,
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,preexec_fn=os.setpgrp)
    except Exception as e:
        logger.error("Process error for command %s: %s", cmd, e)
        return ""
    logger.info("Started process: %s. Waiting for keys: %s", ' '.join(cmd), action_keys)
    with KeyboardPoller() as kp:
        while proc.poll() is None:
            if kp.kbhit():
                key = kp.getch()
                if key in action_keys:
                    logger.info("Key '%s' pressed, terminating process.", key)
                    proc.terminate(); proc.wait()
                    return key
            time.sleep(0.1)
    return ""

def play_sound_cancellable(filepath, action_keys):
    return run_cancellable_process(["aplay", filepath], action_keys)

def stream_video_sound_cancellable(url, action_keys):
    return run_cancellable_process(["mpv", "--no-video", url], action_keys)

def authenticate_youtube():
    global current_state
    creds = None
    if os.path.exists('token.pickle'):
        try:
            with open('token.pickle','rb') as t: creds = pickle.load(t)
            logger.info("Loaded credentials.")
        except Exception as e: logger.error("Token load error: %s", e)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try: creds.refresh(Request()); logger.info("Token refreshed.")
            except Exception as e: logger.error("Refresh failed: %s", e); creds = None
        if not creds or not creds.valid:
            play_sound("error.wav")
            try:
                flow = InstalledAppFlow.from_client_secrets_file('cred.json', 'https://www.googleapis.com/auth/youtube.force-ssl')
                creds = flow.run_console(access_type='offline', prompt='consent')
                logger.info("Obtained new credentials.")
            except Exception as e: logger.error("Auth error: %s", e); return
        with open('token.pickle','wb') as t: pickle.dump(creds, t); logger.info("Saved credentials.")
    return build('youtube','v3', credentials=creds)

def get_playlist_items(pid):
    try:
        req = youtube_auth.playlistItems().list(part="snippet,contentDetails", playlistId=pid, maxResults=50)
        items = req.execute().get('items')
        logger.info("Found %d items.", len(items) if items else 0)
        return items
    except Exception as e: logger.error("Playlist error: %s", e); return None

def remove_playlist_item(pid): 
    try: youtube_auth.playlistItems().delete(id=pid).execute(); logger.info("Removed %s", pid)
    except Exception as e: logger.error("Removal error %s: %s", pid, e)

def play_youtube_item():
    global selected_playlist, current_state, SPECIAL_KEYS, video_index
    items = get_playlist_items(selected_playlist['id'])
    if not items:
        logger.warning("Playlist empty."); play_sound("error.wav"); return
    idx = video_index if not selected_playlist.get('randomize', False) else random.randrange(len(items))
    sel = items[idx]
    video_id, pid = sel['contentDetails']['videoId'], sel['id']
    url = f"https://www.youtube.com/watch?v={video_id}"
    logger.info("Now playing: %s", url)
    pressed_key = stream_video_sound_cancellable(url, SPECIAL_KEYS)
    handle_action_key(pressed_key, 'play')

    if pressed_key == '' and selected_playlist.get('delete_after_play', False):
        logger.info("Deleting video."); remove_playlist_item(pid)
    else:
        video_index = video_index + 1
    if pressed_key == '' and selected_playlist.get('shutdown_after_play', False): current_state = 'wait'

def play_local_item():
    global selected_playlist, current_state, SPECIAL_KEYS, video_index
    items = glob.glob(f"{selected_playlist['id']}*.mp4")
    if not items:
        logger.warning("Folder empty."); play_sound("error.wav"); return
    idx = video_index if not selected_playlist.get('randomize', False) else random.randrange(len(items))
    selected = items[idx]
    logger.info("Now playing: %s", selected)
    pressed_key = play_sound_cancellable(selected, SPECIAL_KEYS)
    handle_action_key(pressed_key, 'play')

    if pressed_key == '' and selected_playlist.get('delete_after_play', False):
        logger.info("Deleting video."); remove_playlist_item(pid)
    else:
        video_index = video_index + 1
    if pressed_key == '' and selected_playlist.get('shutdown_after_play', False): current_state = 'wait'

def wait_for_key():
    with KeyboardPoller() as kp:
        while True:
            if kp.kbhit():
                k = kp.getch(); logger.info("Key: %s", k); return k
            time.sleep(0.1)

def handle_action_key(action_key, next_state):
    global SPECIAL_ACTIONS, states, current_state
    action = SPECIAL_ACTIONS.get(action_key)
    if action == None:
        return
    if action in states:
        current_state = action
        return
    if action == 'skip' and next_state:
        current_state = next_state

def state_init():
    global youtube_auth, current_state
    play_sound("up.wav"); load_config(); youtube_auth = authenticate_youtube(); current_state = 'select'
    logger.info("State changed to 'select'.")

def state_select():
    global selected_playlist, current_state, video_index
    video_index = 0
    playlist_keys = list(config_playlists.keys())

    play_sound("ping.wav"); selected_playlist = None
    logger.info("Select playlist")
    while not selected_playlist:
        ch = wait_for_key()
        if ch in playlist_keys: selected_playlist = config_playlists.get(ch)
        elif ch=='*': current_state = 'shutdown'; return
        else: play_sound("error.wav"); logger.warning("Invalid key: %s", ch)
    current_state = 'play'; play_sound("ok.wav"); logger.info("Playlist selected; state changed to 'play'.")

def state_play():
    global selected_playlist
    if selected_playlist['id'].startswith('./'):
        play_local_item()
    else:
        play_youtube_item()

def state_wait():
    global current_state, SPECIAL_KEYS, no_sound_effects
    pressed_key = play_sound_cancellable("./sounds/wait.wav", SPECIAL_KEYS)
    handle_action_key(pressed_key, 'play')
    if pressed_key == "":
        no_sound_effects = True
        current_state = 'shutdown'

def state_shutdown():
    play_sound("shutdown.wav"); logger.info("Shutting down."); os.system("sudo shutdown -h now")

def state_quit():
    play_sound("down.wav"); logger.info("Exiting application.")

states = {'init': state_init, 'select': state_select, 'play': state_play, 'wait': state_wait, 'shutdown': state_shutdown, 'quit': state_quit}

def main():
    global current_state
    try:
        while current_state != 'quit':
            try:
                states[current_state]()
            except Exception as e:
                logger.error("Error in state %s: %s", current_state, e)
                current_state = 'quit'
    except KeyboardInterrupt:
        logger.info("Ctrl+C detected.")
    finally:
        state_quit()

if __name__=='__main__':
    main()
