import random
import subprocess
import time
import os
import pickle
import yaml
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Define the scope and path to your OAuth credentials
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
config_playlists = {}

def authenticate():
    global SCOPES
    creds = None
    # Load existing credentials from token.pickle if available
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no valid credentials available, prompt the user to log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'cred.json', SCOPES)
            creds = flow.run_console()
        # Save the credentials for future use
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

def play_audio(video_url):
    # Use yt-dlp to extract and play audio directly
    subprocess.run(["yt-dlp", "--extract-audio", "--audio-format", "mp3", "--audio-quality", "0", video_url])

def load_config():
    print("Reloading config file.")
    global config_playlists
    config_playlists = {}
    with open("config.yaml", 'r') as stream:
        yaml_config = yaml.safe_load(stream.read())
        config_playlists = yaml_config['Playlists']

def main():
    global config_playlists
    load_config()

    creds = authenticate()

    playlist = config_playlists['music']
    youtube = get_youtube_service(creds)

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

        # Play the audio. This call blocks until playback is finished.
        play_audio(video_url)

        if playlist['delete_after_play']:
            print("Playback finished. Removing video from playlist...")
            remove_playlist_item(youtube, playlist_item_id)

        if playlist['shutdown_after_play']:
            return
        time.sleep(1)  # small delay before checking the next video

if __name__ == '__main__':
    main()
