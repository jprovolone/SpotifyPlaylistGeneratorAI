import os
import argparse
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from openai import OpenAI
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import threading
import logging

load_dotenv()

# Global variable to store the authorization code
auth_code = None
# Initialize OpenAI client
client = OpenAI()

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query_components = parse_qs(urlparse(self.path).query)
        if 'code' in query_components:
            auth_code = query_components['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Authentication successful! You can close this window.")
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Authentication failed. Please try again.")

def start_local_server():
    server = HTTPServer(('localhost', 8888), RequestHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    return server

def authenticate_spotify(client_id, client_secret, redirect_uri):
    logging.info("Authenticating with Spotify...")
    sp_oauth = SpotifyOAuth(client_id=client_id,
                            client_secret=client_secret,
                            redirect_uri=redirect_uri,
                            scope="playlist-modify-private user-top-read user-read-recently-played")

    token_info = sp_oauth.get_cached_token()

    if not token_info:
        auth_url = sp_oauth.get_authorize_url()
        print(f"Please navigate here: {auth_url}")
        response = input("Enter the URL you were redirected to: ")
        code = sp_oauth.parse_response_code(response)
        token_info = sp_oauth.get_access_token(code)

    if token_info:
        logging.info("Successfully authenticated with Spotify.")
        return spotipy.Spotify(auth=token_info['access_token'])
    else:
        raise Exception("Failed to get access token")


def get_user_music_context(sp, limit=50):
    logging.info("Fetching user's music context...")
    recent_tracks = sp.current_user_recently_played(limit=limit)
    top_tracks = sp.current_user_top_tracks(limit=limit, time_range='medium_term')

    context = "Recently played tracks:\n"
    for item in recent_tracks['items'][:limit]: 
        track = item['track']
        context += f"{track['artists'][0]['name']} - {track['name']}\n"

    context += "\nTop tracks:\n"
    for item in top_tracks['items'][:limit]:
        context += f"{item['artists'][0]['name']} - {item['name']}\n"

    return context

def generate_playlist(prompt, length, user_context=None):
    try:
        if user_context is not None:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a music expert. Generate a playlist based on the given prompt and user's music context."},
                    {"role": "user", "content": f"Here's the user's music context:\n\n{user_context}\n\nBased on this context and the following prompt: '{prompt}', generate a playlist of {length} songs. Return only the list of songs in the format 'Artist - Song Title', one per line. Do not include numbering or any additional information."}
                ]
            )
        else:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a music expert. Generate a playlist based on the given prompt and user's music context."},
                    {"role": "user", "content": f"Based on the following prompt: '{prompt}', generate a playlist of {length} songs. Return only the list of songs in the format 'Artist - Song Title', one per line. Do not include numbering or any additional information."}
                ]
            )
        songs = response.choices[0].message.content.strip().split('\n')
        logging.info(f"Generated {len(songs)} songs")
        return songs
    except Exception as e:
        logging.error(f"Error generating playlist: {str(e)}")
        raise


def create_spotify_playlist(sp, songs, playlist_name=None):
    print("Creating Spotify playlist...")
    if not playlist_name:
        playlist_name = f"AI Generated Playlist - {songs[0].split(' - ')[0]}"
    
    user_id = sp.me()['id']
    playlist = sp.user_playlist_create(user_id, playlist_name, public=False)
    print(f"Created playlist: {playlist_name}")
    
    track_uris = []
    for song in songs:
        try:
            artist, title = song.split(' - ', 1)
        except:
            print(f"Error parsing input. Stupid AI!")
            continue
        print(f"Searching for: {artist} - {title}")
        
        result = sp.search(q=f"artist:{artist} track:{title}", type='track', limit=1)
        if not result['tracks']['items']:
            result = sp.search(q=f"track:{title}", type='track', limit=1)
        
        if result['tracks']['items']:
            track_uri = result['tracks']['items'][0]['uri']
            track_uris.append(track_uri)
            print(f"  Found: {track_uri}")
        else:
            print(f"  Not found: {artist} - {title}")
    
    if track_uris:
        print(f"Adding {len(track_uris)} tracks to playlist...")
        for i in range(0, len(track_uris), 100):
            sp.playlist_add_items(playlist['id'], track_uris[i:i+100])
    else:
        print("No tracks found to add to playlist.")
    
    return playlist['external_urls']['spotify']

def run_playlist_generator(prompt, length, name=None, config=None):
    logging.info(f"Starting playlist generation: prompt='{prompt}', length={length}, name='{name}'")

    if config is None:
        config = {}

    # Use the config values or fall back to environment variables
    client_id = config.get('client_id') or None
    client_secret = config.get('client_secret') or None
    redirect_uri = config.get('redirect_uri') or None
    
    # Set OpenAI API key
    client.api_key = config.get('openai_key') or None

    # Check for none values
    none_values = []
    
    if client_id is None:
        none_values.append("client_id")
    if client_secret is None:
        none_values.append("client_secret")
    if redirect_uri is None:
        none_values.append("redirect_uri")
    if client.api_key is None:
        none_values.append("openai_key")
    
    if none_values:
        return f"The following values are None: {', '.join(none_values)}"

    logging.info("Authenticating with Spotify...")
    try:
        sp = authenticate_spotify(client_id, client_secret, redirect_uri)
        logging.info("Successfully authenticated with Spotify.")
    except Exception as e:
        logging.error(f"Failed to authenticate with Spotify: {str(e)}")
        raise

    logging.info("Getting user's music context...")
    user_context = get_user_music_context(sp)
    
    logging.info("Generating playlist with OpenAI...")
    songs = generate_playlist(prompt, length, user_context)
    
    logging.info("Creating Spotify playlist...")
    playlist_url = create_spotify_playlist(sp, songs, name)
    
    logging.info(f"Playlist created: {playlist_url}")
    return f"Playlist created: {playlist_url}"


def main():
    parser = argparse.ArgumentParser(description='Generate and create a Spotify playlist based on your listening history.')
    parser.add_argument('-p', '--prompt', required=True, help='Prompt for playlist generation')
    parser.add_argument('-l', '--length', type=int, default=10, help='Number of songs in the playlist')
    parser.add_argument('-n', '--name', help='Name for the playlist')
    parser.add_argument('--history', type=int, default=0, help="Number of songs to use as context from your listen history & top tracks.")
    args = parser.parse_args()

    print(f"Starting script with prompt: '{args.prompt}', length: {args.length}, name: '{args.name}', history: '{args.history}'")

    sp = authenticate_spotify(os.getenv("SPOTIFY_CLIENT_ID"), os.getenv("SPOTIFY_CLIENT_SECRET"), os.getenv("SPOTIFY_REDIRECT_URI"))
    user_context = None
    if args.history > 0:
        user_context = get_user_music_context(sp, args.history)
    client.api_key = os.getenv("OPENAI_API_KEY")
    songs = generate_playlist(args.prompt, args.length, user_context)
    playlist_url = create_spotify_playlist(sp, songs, args.name)
    
    print(f"Playlist created: {playlist_url}")

if __name__ == "__main__":
    main()
