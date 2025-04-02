import random
import subprocess
import time
import os
import pickle
import yaml
import sys
import select
import tty
import termios
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Define the scope and path to your OAuth credentials
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

# Global Vars
config_playlists = {}
youtube_auth = None
selected_playlist = None

# ---------- State Machine ----------

current_state = 'init'

states = dict({
    'init':state_init,
    'select':state_select,
    'play':state_play,
    'wait':state_wait,
    'shutdown':state_shutdown,
    'quit':state_quit
})

# ---------- Main Loop ----------
def main():
    global states
    global current_state
    try:
        while current_state is not 'quit':
            states[current_state]()
    finally:
        print("Exiting gracefully...")
        state_quit()

# ---------- State Functions ----------

def state_init():
    global youtube_auth
    global current_state
    play_sound("up.wav")
    load_config()
    youtube_auth = authenticate_youtube()
    current_state = 'select'

def state_select():
    global selected_playlist
    global current_state
    play_sound("ping.wav")
    selected_playlist = None
    while not selected_playlist:
        # Wait for initial keypress to choose a playlist.
        choice = wait_for_key()
        if choice == '0':
            selected_playlist = config_playlists['asmr']
        elif choice == '1':
            selected_playlist = config_playlists['chill-music']
        elif choice == '4':
            selected_playlist = config_playlists['hard-music']
        elif choice == '*':
            current_state = 'shutdown'
            return
        else:
            play_sound("error.wav")
    current_state = 'play'
    play_sound("ok.wav")

def state_play():
    global selected_playlist
    global current_state
    items = get_playlist_items(selected_playlist['id'])
    if not items:
        print("Playlist is empty.")
        play_sound("error.wav")
        break
    
    index = 0 if not selected_playlist['randomize'] else random.randrange(len(items))
    selected = items[index]

    video_id = selected['contentDetails']['videoId']
    playlist_item_id = selected['id']
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    print("Now playing:", video_url)

    # Play the audio. This call will exit if playback finishes normally or is cancelled.
    stream_video_sound_cancellable(video_url)

    if selected_playlist.get('delete_after_play', False):
        print("Playback finished. Removing video from playlist...")
        remove_playlist_item(playlist_item_id)

    if selected_playlist.get('shutdown_after_play', False):
        current_state = 'wait'
        return
    
def state_wait():
    global current_state
    cancel_type = play_sound_cancellable("wait.wav")
    if cancel_type == 'continue':
        current_state = 'play'
    else:
        current_state = 'shutdown'
    
def state_shutdown():
    play_sound("shutdown.wav")
    os.system("sudo shutdown -h now")

def state_quit():
    play_sound("down.wav")

# ---------- Authentication And General Functions ----------

def authenticate_youtube():
    global SCOPES
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'cred.json', SCOPES)
            creds = flow.run_console()
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return build('youtube', 'v3', credentials=creds)

def get_playlist_items(playlist_id):
    global youtube_auth
    request = youtube_auth.playlistItems().list(
        part="snippet,contentDetails",
        playlistId=playlist_id
    )
    response = request.execute()
    if response.get('items'):
        return response['items']
    else:
        return None

def remove_playlist_item(playlist_item_id):
    global youtube_auth
    request = youtube_auth.playlistItems().delete(id=playlist_item_id)
    request.execute()

def load_config():
    global config_playlists
    print("Reloading config file.")
    with open("config.yaml", 'r') as stream:
        yaml_config = yaml.safe_load(stream.read())
        config_playlists = yaml_config['Playlists']

# ---------- Keyboard Polling Helper ----------
class KeyboardPoller:
    def __enter__(self):
        self.fd = sys.stdin.fileno()
        self.old_settings = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        return self
    def __exit__(self, type, value, traceback):
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
    def kbhit(self):
        dr, _, _ = select.select([sys.stdin], [], [], 0.1)
        return dr != []
    def getch(self):
        return sys.stdin.read(1)

# ---------- User Input ----------
def wait_for_key():
    with KeyboardPoller() as kp:
        while True:
            if kp.kbhit():
                return kp.getch()
            time.sleep(0.1)

# ---------- Audio Playback ----------
def stream_video_sound_cancellable(video_url):
    proc = subprocess.Popen(["mpv", "--no-video", video_url],
        stdin=subprocess.DEVNULL,  # Prevent from reading input
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setpgrp)  # Run in a separate process group

    print("Press * to skip playback.")
    with KeyboardPoller() as kp:
        while proc.poll() is None:
            if kp.kbhit():
                key = kp.getch()
                if key == '*':
                    print("Cancelling playback...")
                    proc.terminate()
                    proc.wait()
                    break
            time.sleep(0.1)

def play_sound_cancellable(sound):
    proc = subprocess.Popen(["aplay", f"./sounds/{sound}"],
        stdin=subprocess.DEVNULL,  # Prevent from reading input
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setpgrp)  # Run in a separate process group

    print("Press * to skip playback.")
    with KeyboardPoller() as kp:
        while proc.poll() is None:
            if kp.kbhit():
                key = kp.getch()
                if key == '*':
                    print("Cancelling playback...")
                    proc.terminate()
                    proc.wait()
                    return 'shutdown'
                if key == '\r':
                    proc.terminate()
                    proc.wait()
                    return 'continue'
            time.sleep(0.1)

def play_sound(sound):
    subprocess.run(["aplay", f"./sounds/{sound}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ---------- Entry Point ----------

if __name__ == '__main__':
    main()