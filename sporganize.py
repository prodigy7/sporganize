# -*- coding: utf-8 -*-
import spotipy
import spotipy.util as util
import argparse
import yaml
import webbrowser
import sys
import csv
import re
import unidecode

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# Handling command line arguments
parser = argparse.ArgumentParser(
    description="Utility for sorting spotify playlists by release year",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)
parser.add_argument("playlist", nargs='?', default="", help="spotify playlist name for parse")
parser.add_argument("-e", "--export", action="store_true", help="export track list into csv file")
parser.add_argument("-n", "--dry-run", action="store_true", help="dry run without modify anything")
parser.add_argument("-m", "--move", action="store_true", help="would move track from source to target playlist instead of copying")

args = parser.parse_args()
args_config = vars(args)

# Read the configuration file
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

client_id = config['client_id']
client_secret = config['client_secret']
username = config['username']
playlists = config['playlists']

def sort_playlist_by_year(playlist_name, dry_run, move, export):

    if export:
        csvFilename = slugify(playlist_name).removeprefix('-').removesuffix('-') + '.csv';
        print("")
        print(f"=> Spotify Playlist '{playlist_name}' ({csvFilename})")
    else:
        print("")
        print(f"=> Spotify Playlist '{playlist_name}'")

    # Authorization
    scope = 'playlist-read-private playlist-modify-private playlist-modify-public'
    redirect_uri = 'http://127.0.0.1:8080/callback'

    # Get the authorization URL
    try:
        token = util.prompt_for_user_token(
            username=username,
            scope=scope,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri
        )
    except Exception as e:
        # Allgemeiner Fehlerhandler für alle anderen Fehler
        print("")
        print(f"Ein unerwarteter Fehler ist aufgetreten: {e}")
        print("")
        sys.exit(1)


    if token:
        sp = spotipy.Spotify(auth=token, requests_timeout=10, retries=5)

        # Get all playlists
        playlists = []
        offset = 0
        while True:
            try:
                results = sp.current_user_playlists(limit=50, offset=offset)
            except Exception as e:
                # Allgemeiner Fehlerhandler für alle anderen Fehler
                print("")
                print(f"Ein unerwarteter Fehler ist aufgetreten: {e}")
                print("")
                sys.exit(1)
            playlists.extend(results['items'])
            offset += 50
            if not results['next']:
                break

        # Search for the playlist
        playlist_id = None
        for playlist in playlists:
            if playlist['name'] == playlist_name:
                playlist_id = playlist['id']
                break

        if not playlist_id:
            print("Playlist does not exist.")
            return

        # Get the playlist tracks
        results = sp.playlist_tracks(playlist_id)
        tracks = results['items']
        while results['next']:
            results = sp.next(results)
            tracks.extend(results['items'])

        # Sort the tracks by year
        #tracks.sort(key=lambda t: t['track']['album']['release_date'])

        if export:
            csvFile = open(csvFilename, 'w')
            csvExport = csv.writer(csvFile, dialect="excel")
            csvExport.writerow(["Artist", "Track", "Year", "Spotify Uri"])

        # Create playlists by year and genre
        playlists_by_year = {}
        for i, track in enumerate(tracks):
            track_type = track["track"]["type"]
            if track_type == "track":
                # Fetch extra info made currently no sense
                # track_info = sp.track(track['track']['id'])
                track_info = track['track']
                year = track_info['album']['release_date'][:4]

                # Print progress information
                artist_name = track_info['artists'][0]['name'] if track_info['artists'][0] else 'Unknown Artist'
                track_name = track_info['name']

                process_possible = True
                if not track_name:
                    process_possible = False

                #genres = get_artist_genre(sp, track_info['artists'][0]['id']) if track_info['artists'] else 'Other'

                playlist_key = f"# Elektronisch - {year}"

                if process_possible:
                    if playlist_key not in playlists_by_year:
                        # Check if the playlist already exists
                        playlist_create_would = False
                        if check_playlist_exists(sp, playlist_key):
                            playlists_by_year[playlist_key] = get_playlist_id_by_name(sp, playlist_key)
                        else:
                            if not export:
                                if dry_run:
                                    print(f"[ {bcolors.OKBLUE}Playlist{bcolors.ENDC} ] Would create: {playlist_key}")
                                    playlist_create_would = True
                                else:
                                    print(f"[ {bcolors.OKGREEN}Playlist{bcolors.ENDC} ] Create: {playlist_key}")
                                    playlist = sp.user_playlist_create(user=username, name=playlist_key, public=False)
                                    playlists_by_year[playlist_key] = playlist['id']

                    track_uri = track['track']['uri']

                    if export:
                        if dry_run:
                            print(f"[ {bcolors.OKGREEN}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks))} Would export to CSV: {artist_name} - {track_name} [{year}] -> {playlist_key}")
                        else:
                            print(f"[ {bcolors.OKGREEN}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks))} Export to CSV: {artist_name} - {track_name} [{year}] -> {playlist_key}")
                            csvExport.writerow([artist_name, track_name, year, track_uri])
                    else:
                        if playlist_create_would == False and not is_track_in_playlist(sp, playlists_by_year[playlist_key], track_uri):
                            if dry_run:
                                if move:
                                    print(f"[ {bcolors.OKBLUE}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks))} Would move: {artist_name} - {track_name} [{year}] -> {playlist_key}")
                                else:
                                    print(f"[ {bcolors.OKBLUE}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks))} Would copy: {artist_name} - {track_name} [{year}] -> {playlist_key}")
                            else:
                                if move:
                                    print(f"[ {bcolors.OKGREEN}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks))} Move: {artist_name} - {track_name} [{year}]")
                                    sp.playlist_add_items(playlists_by_year[playlist_key], [track_uri])
                                    sp.playlist_remove_all_occurrences_of_items(playlist_id, [track_uri])
                                else:
                                    print(f"[ {bcolors.OKGREEN}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks))} Copy: {artist_name} - {track_name} [{year}]")
                                    sp.playlist_add_items(playlists_by_year[playlist_key], [track_uri])
                        else:
                            if move:
                                if dry_run:
                                    print(f"[ {bcolors.WARNING}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks))} Would skip existing and remove from source: {artist_name} - {track_name} [{year}] -> {playlist_key}")
                                else:
                                    print(f"[ {bcolors.WARNING}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks))} Skip existing and remove from source: {artist_name} - {track_name} [{year}] -> {playlist_key}")
                                    sp.playlist_remove_all_occurrences_of_items(playlist_id, [track_uri])
                            else:
                                if dry_run:
                                    print(f"[ {bcolors.WARNING}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks))} Would skip existing: {artist_name} - {track_name} [{year}] -> {playlist_key}")
                                else:
                                    print(f"[ {bcolors.WARNING}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks))} Skip existing: {artist_name} - {track_name} [{year}] -> {playlist_key}")
                else:
                    if dry_run:
                        print(f"[ {bcolors.FAIL}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks))} Would skip missing: Track no longer available")
                    else:
                        print(f"[ {bcolors.FAIL}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks))} Skip missing: Track no longer available")


            else:
                artist_name = track["track"]['album']['artists'][0]['name'] if track["track"]['album']['artists'] else 'Unknown Artist'
                track_name = track["track"]["name"]
                print(f"[ {bcolors.FAIL}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks))} Type {track_type} not supported yet: {artist_name} - {track_name}")

        print("")
        if dry_run:
            print("Playlists would have been created and sorted successfully.")
        else:
            print("Playlists have been created and sorted successfully.")
    else:
        print("Unable to obtain token for authentication.")

def slugify(text):
    text = unidecode.unidecode(text).lower()
    return re.sub(r'[\W_]+', '-', text)

def progress_label(current, total):
    return f"{str(current).zfill(3)} / {str(total).zfill(3)} |"

def check_playlist_exists(sp, playlist_name):
    playlists = sp.current_user_playlists()
    for playlist in playlists['items']:
        if playlist['name'] == playlist_name:
            return True
    return False

def get_playlist_id_by_name(sp, playlist_name):
    playlists = sp.current_user_playlists()
    for playlist in playlists['items']:
        if playlist['name'] == playlist_name:
            return playlist['id']
    return None

def is_track_in_playlist(sp, playlist_id, track_uri):
    # Hole die Tracks der Playlist
    playlist_tracks = sp.playlist_tracks(playlist_id)['items']

    # Überprüfe, ob der Track in der Playlist existiert
    for playlist_track in playlist_tracks:
        if playlist_track['track']['uri'] == track_uri:
            return True

    return False

dry_run = args_config['dry_run']
move = args_config['move']
export = args_config['export']

if move and export:
    print("Combine of move and export option not option not possible!")
    sys.exit(1)
    

if args_config['playlist']:
    sort_playlist_by_year(args_config['playlist'], dry_run, export)
else:
    for playlist in playlists:
        sort_playlist_by_year(playlist, dry_run, move, export)

print("")
