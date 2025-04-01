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
config_playlists = {}

# ---------- Authentication and API Functions ----------
def authenticate():
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
    return creds

def get_youtube_service(creds):
    return build('youtube', 'v3', credentials=creds)

def get_playlist_items(youtube, playlist_id):
    request = youtube.playlistItems().list(
        part="snippet,contentDetails",
        playlistId=playlist_id
    )
    response = request.execute()
    if response.get('items'):
        return response['items']
    else:
        return None

def remove_playlist_item(youtube, playlist_item_id):
    request = youtube.playlistItems().delete(id=playlist_item_id)
    request.execute()

def load_config():
    print("Reloading config file.")
    global config_playlists
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
def play_audio(video_url):
    proc = subprocess.Popen(["mpv", "--no-video", video_url],
        stdin=subprocess.DEVNULL,  # Prevent mpv from reading input
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

def play_sound(sound):
    subprocess.run(["aplay", f"./sounds/{sound}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ---------- System Stuff ----------

def shutdown():
    play_sound("shutdown.wav")
    os.system("sudo shutdown -h now")

# ---------- Main Loop ----------
def main():
    try:
        play_sound("ok.wav")
        load_config()
        creds = authenticate()
        youtube = get_youtube_service(creds)

        playlist = None
        while not playlist:
            # Wait for initial keypress to choose a playlist.
            choice = wait_for_key()
            if choice == '0':
                playlist = config_playlists['asmr']
            elif choice == '1':
                playlist = config_playlists['chill-music']
            elif choice == '4':
                playlist = config_playlists['hard-music']
            elif choice == '*':
                shutdown()
                return
            else:
                play_sound("error.wav")
        play_sound("ok.wav")
    
        while True:
            items = get_playlist_items(youtube, playlist['id'])
            if not items:
                print("Playlist is empty.")
                break
            
            index = 0 if not playlist['randomize'] else random.randrange(len(items))
            selected = items[index]

            video_id = selected['contentDetails']['videoId']
            playlist_item_id = selected['id']
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            print("Now playing:", video_url)

            # Play the audio. This call will exit if playback finishes normally or is cancelled.
            play_audio(video_url)

            if playlist.get('delete_after_play', False):
                print("Playback finished. Removing video from playlist...")
                remove_playlist_item(youtube, playlist_item_id)

            if playlist.get('shutdown_after_play', False):
                shutdown()
                return
    finally:
        print("Exiting gracefully...")
        play_sound("error.wav")

if __name__ == '__main__':
    main()