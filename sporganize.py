# -*- coding: utf-8 -*-
import spotipy
import spotipy.util as util
import argparse
import yaml
import webbrowser
import sys
import os
import csv
import re
import unidecode
import json
import urllib.request
import urllib.error

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

# Cache for playlist contents to avoid repeated API calls
PLAYLIST_CONTENT_CACHE = {}

# File to store unique target playlists
PLAYLIST_HISTORY_FILE = 'playlists.csv'
PLAYLIST_HISTORY_CACHE = None

# Constants for Spotify authentication
SPOTIFY_SCOPE = 'playlist-read-private playlist-modify-private playlist-modify-public'
SPOTIFY_REDIRECT_URI = 'http://127.0.0.1:8080/callback'


def print_info(message: str) -> None:
    """Gibt eine Informationsmeldung aus."""
    print(f"[ {bcolors.OKBLUE}Info{bcolors.ENDC} ] {message}")


def print_error(message: str) -> None:
    """Gibt eine Fehlermeldung mit Farbe aus."""
    print(f"[ {bcolors.FAIL}Error{bcolors.ENDC} ] {message}")


def print_success(message: str) -> None:
    """Gibt eine Erfolgsmeldung aus."""
    print(f"[ {bcolors.OKGREEN}Success{bcolors.ENDC} ] {message}")


def print_warning(message: str) -> None:
    """Gibt eine Warnmeldung aus."""
    print(f"[ {bcolors.WARNING}Warning{bcolors.ENDC} ] {message}")

# Handling command line arguments
parser = argparse.ArgumentParser(
    description="Utility for sorting spotify playlists by release year",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)
parser.add_argument("playlist", nargs='?', default="", help="spotify playlist name for parse")
parser.add_argument("-e", "--export", action="store_true", help="export track list into csv file")
parser.add_argument("-i", "--import-csv", dest="import_csv", metavar="FILE", help="import tracks from csv file to playlists")
parser.add_argument("-n", "--dry-run", action="store_true", help="dry run without modify anything")
parser.add_argument("-m", "--move", action="store_true", help="would move track from source to target playlist instead of copying")
parser.add_argument("-u", "--urls", action="store_true", dest="urls", help="print full spotify URLs for playlists defined in config and exit")
parser.add_argument("-c", "--config-path", dest="config_path", metavar="PATH", help="path to config file or directory containing config.yaml")
parser.add_argument("--export-dir", dest="export_dir", metavar="DIR", help="directory to write exported CSV files into")
args = parser.parse_args()
args_config = vars(args)


def resolve_config_path(config_path_option):
    """Resolve the config file path from an explicit path, home config locations, or script directory."""
    if config_path_option:
        candidate = os.path.expanduser(config_path_option)
        if os.path.isfile(candidate):
            return candidate, True
        if os.path.isdir(candidate):
            return os.path.join(candidate, 'config.yaml'), False
        if os.path.splitext(os.path.basename(candidate))[1].lower() in ('.yaml', '.yml'):
            return candidate, False
        return os.path.join(candidate, 'config.yaml'), False

    home = os.path.expanduser('~')
    candidates = [
        os.path.join(home, '.config', 'sporganize', 'config.yaml'),
        os.path.join(home, '.config', 'config.yaml'),
        os.path.join(os.path.dirname(os.path.realpath(__file__)), 'config.yaml'),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path, True

    return candidates[-1], False


config_path_option = args.config_path or os.environ.get('CONFIG_PATH')
config_path, config_found = resolve_config_path(config_path_option)
config = {}
if config_path:
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
        if config_found:
            print_info(f"Loaded configuration from {config_path}")
    except FileNotFoundError:
        if config_path_option:
            print_error(f"Config file not found at {config_path}")
            sys.exit(1)
        config = {}
    except yaml.YAMLError as e:
        print_error(f"Failed to parse {config_path}: {e}")
        sys.exit(1)

client_id = os.environ.get('SPOTIFY_CLIENT_ID') or config.get('spotify_client_id')
client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET') or config.get('spotify_client_secret')
username = os.environ.get('SPOTIFY_USERNAME') or config.get('spotify_username')
webhook_url = os.environ.get('WEBHOOK_URL') or config.get('webhook_url')

playlist_env = os.environ.get('PLAYLISTS') or os.environ.get('SPOTIFY_PLAYLISTS')
if playlist_env:
    playlists = [item.strip() for item in playlist_env.split(',') if item.strip()]
else:
    config_playlists = config.get('spotify_playlists')
    if isinstance(config_playlists, str):
        playlists = [item.strip() for item in config_playlists.split(',') if item.strip()]
    else:
        playlists = config_playlists or []

export_dir = args_config.get('export_dir') or os.environ.get('EXPORT_DIR')
if export_dir:
    export_dir = os.path.abspath(os.path.expanduser(export_dir))
else:
    export_dir = None


def prepare_export_directory(export_dir, dry_run):
    """Ensure the export directory exists and is writable."""
    if not export_dir:
        return None

    if os.path.exists(export_dir):
        if not os.path.isdir(export_dir):
            print_error(f"Export path exists and is not a directory: {export_dir}")
            sys.exit(1)
        if not os.access(export_dir, os.W_OK):
            print_error(f"Export directory is not writable: {export_dir}")
            sys.exit(1)
        return export_dir

    if dry_run:
        print_info(f"Dry run: would create export directory: {export_dir}")
        return export_dir

    try:
        os.makedirs(export_dir, exist_ok=True)
    except OSError as e:
        print_error(f"Could not create export directory '{export_dir}': {e}")
        sys.exit(1)

    if not os.access(export_dir, os.W_OK):
        print_error(f"Export directory is not writable after creation: {export_dir}")
        sys.exit(1)

    return export_dir

def validate_configuration():
    missing = []
    if not client_id:
        missing.append('SPOTIFY_CLIENT_ID / spotify_client_id')
    if not client_secret:
        missing.append('SPOTIFY_CLIENT_SECRET / spotify_client_secret')
    if not username:
        missing.append('SPOTIFY_USERNAME / spotify_username')
    if not playlists and not args_config.get('playlist') and not args_config.get('import_csv') and not args_config.get('urls'):
        missing.append('PLAYLISTS / SPOTIFY_PLAYLISTS / spotify_playlists (required when no playlist positional argument is provided)')

    if missing:
        print_error('Missing required configuration values:')
        for key in missing:
            print_error(f'  - {key}')
        sys.exit(1)

validate_configuration()


def send_webhook_notification(payload):
    """Sendet ein JSON-Payload an den optional konfigurierten Webhook."""
    if not webhook_url:
        return

    try:
        data = json.dumps(payload).encode('utf-8')
        request = urllib.request.Request(
            webhook_url,
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status >= 300:
                print_warning(f"Webhook send failed: {response.status} {response.reason}")
    except urllib.error.URLError as e:
        print_warning(f"Webhook send error: {e}")
    except Exception as e:
        print_warning(f"Webhook unexpected error: {e}")


def load_playlist_history():
    """Load existing playlists from the history file into a set."""
    global PLAYLIST_HISTORY_CACHE
    if PLAYLIST_HISTORY_CACHE is not None:
        return PLAYLIST_HISTORY_CACHE

    PLAYLIST_HISTORY_CACHE = set()
    if not os.path.exists(PLAYLIST_HISTORY_FILE):
        return PLAYLIST_HISTORY_CACHE

    try:
        with open(PLAYLIST_HISTORY_FILE, 'r', encoding='utf-8', newline='') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if row and row[0]:
                    PLAYLIST_HISTORY_CACHE.add(row[0])
    except Exception as e:
        print_warning(f"Could not load playlist history: {e}")

    return PLAYLIST_HISTORY_CACHE


def add_playlist_to_history(playlist_name):
    """Append a playlist name to paylists.csv if it is not already present."""
    history = load_playlist_history()
    if playlist_name in history:
        return

    try:
        # Add to in-memory set
        history.add(playlist_name)

        # Write full sorted list back to the file to keep it alphabetical and deduplicated
        sorted_playlists = sorted(history, key=lambda s: s.lower())
        with open(PLAYLIST_HISTORY_FILE, 'w', encoding='utf-8', newline='') as csvfile:
            writer = csv.writer(csvfile)
            for name in sorted_playlists:
                writer.writerow([name])
    except Exception as e:
        print_warning(f"Could not write playlist history: {e}")


def get_spotify_client():
    """
    Authenticate with Spotify and return a Spotify client instance.
    Returns None if authentication fails.
    """
    try:
        token = util.prompt_for_user_token(
            username=username,
            scope=SPOTIFY_SCOPE,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=SPOTIFY_REDIRECT_URI
        )
    except Exception as e:
        print_error(f"Ein unerwarteter Fehler ist aufgetreten: {e}")
        sys.exit(1)

    if token:
        return spotipy.Spotify(auth=token, requests_timeout=10, retries=5)
    else:
        print_error("Unable to obtain token for authentication.")
        sys.exit(1)

def sort_playlist_by_year(playlist_name: str, dry_run: bool, move: bool, export: bool, export_dir=None) -> None:
    """Sortiert Tracks einer Spotify-Playlist nach Veröffentlichungsjahr."""
    csvFilename = None
    if export:
        if export_dir:
            export_dir = prepare_export_directory(export_dir, dry_run)
        csvFilename = slugify(playlist_name).removeprefix('-').removesuffix('-') + '.csv'
        if export_dir:
            csvFilename = os.path.join(export_dir, csvFilename)
        print(f"=> Spotify Playlist '{playlist_name}' ({csvFilename})")
    else:
        print(f"=> Spotify Playlist '{playlist_name}'")

    # Get Spotify client
    sp = get_spotify_client()
    if sp:

        # Get all playlists
        playlists = []
        offset = 0
        while True:
            try:
                results = sp.current_user_playlists(limit=50, offset=offset)
            except Exception as e:
                print_error(f"Ein unerwarteter Fehler ist aufgetreten: {e}")
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
            print_error("Playlist does not exist.")
            return

        # Get the playlist tracks
        results = sp.playlist_tracks(playlist_id)
        tracks = results['items']
        while results['next']:
            results = sp.next(results)
            tracks.extend(results['items'])

        # Sort the tracks by year
        #tracks.sort(key=lambda t: t['track']['album']['release_date'])

        csvFile = None
        csvExport = None
        if export and not dry_run:
            try:
                csvFile = open(csvFilename, 'w', encoding='utf-8', newline='')
                csvExport = csv.writer(csvFile, dialect="excel")
                csvExport.writerow(["Artist", "Track", "Year", "Spotify Uri"])
            except OSError as e:
                print_error(f"Could not open export file '{csvFilename}': {e}")
                return

        # Create playlists by year and genre
        playlists_by_year = {}
        try:
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

                    playlist_create_would = False
                    if process_possible:
                        if playlist_key not in playlists_by_year:
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
                        action = "Would export to CSV" if dry_run else "Export to CSV"
                        print(f"[ {bcolors.OKGREEN}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks))} {action}: {artist_name} - {track_name} [{year}] -> {playlist_key}")
                        if not dry_run and csvExport is not None:
                            csvExport.writerow([artist_name, track_name, year, track_uri])
                    else:
                        if not playlist_create_would and not is_track_in_playlist(sp, playlists_by_year[playlist_key], track_uri):
                            event_name = "spotify_track_moved" if move else "spotify_track_copied"
                            action_label = "Would move" if dry_run and move else "Would copy" if dry_run else "Move" if move else "Copy"

                            if dry_run:
                                print(f"[ {bcolors.OKBLUE}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks))} {action_label}: {artist_name} - {track_name} [{year}] -> {playlist_key}")
                                if webhook_url:
                                    send_webhook_notification({
                                        'event': event_name,
                                        'track': track_name,
                                        'artist': artist_name,
                                        'year': year,
                                        'from_playlist': playlist_name,
                                        'to_playlist': playlist_key,
                                        'track_uri': track_uri,
                                        'dry_run': True,
                                        'message': f"{artist_name} - {track_name} would {'move' if move else 'copy'} from {playlist_name} to {playlist_key}"
                                    })
                            else:
                                sp.playlist_add_items(playlists_by_year[playlist_key], [track_uri])
                                if move:
                                    sp.playlist_remove_all_occurrences_of_items(playlist_id, [track_uri])
                                clear_playlist_cache(playlists_by_year[playlist_key])
                                clear_playlist_cache(playlist_id)
                                if webhook_url:
                                    send_webhook_notification({
                                        'event': event_name,
                                        'track': track_name,
                                        'artist': artist_name,
                                        'year': year,
                                        'from_playlist': playlist_name,
                                        'to_playlist': playlist_key,
                                        'track_uri': track_uri,
                                        'dry_run': False,
                                        'message': f"{artist_name} - {track_name} {'moved' if move else 'copied'} from {playlist_name} to {playlist_key}"
                                    })
                                add_playlist_to_history(playlist_key)
                                action = "Move" if move else "Copy"
                                print(f"[ {bcolors.OKGREEN}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks))} {action}: {artist_name} - {track_name} [{year}]")
                        else:
                            if move:
                                if playlist_id == playlists_by_year[playlist_key]:
                                    action = "Would skip (already in correct playlist)" if dry_run else "Skip (already in correct playlist)"
                                    print(f"[ {bcolors.OKCYAN}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks))} {action}: {artist_name} - {track_name} [{year}] -> {playlist_key}")
                                else:
                                    action = "Would skip existing and remove from source" if dry_run else "Skip existing and remove from source"
                                    print(f"[ {bcolors.WARNING}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks))} {action}: {artist_name} - {track_name} [{year}] -> {playlist_key}")
                                    sp.playlist_remove_all_occurrences_of_items(playlist_id, [track_uri])
                                    clear_playlist_cache(playlist_id)
                            else:
                                action = "Would skip existing" if dry_run else "Skip existing"
                                print(f"[ {bcolors.WARNING}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks))} {action}: {artist_name} - {track_name} [{year}] -> {playlist_key}")
                elif track_type is None or track_type == 'episode':
                    if dry_run:
                        print(f"[ {bcolors.FAIL}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks))} Would skip missing or unsupported item: {track_uri if 'track_uri' in locals() else 'unknown'}")
                    else:
                        print(f"[ {bcolors.FAIL}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks))} Skip missing or unsupported item")
                else:
                    artist_name = track["track"]['album']['artists'][0]['name'] if track["track"]['album']['artists'] else 'Unknown Artist'
                    track_name = track["track"]["name"]
                    print(f"[ {bcolors.FAIL}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks))} Type {track_type} not supported yet: {artist_name} - {track_name}")
        finally:
            if csvFile is not None:
                csvFile.close()

        print("")
        if dry_run:
            print("Playlists would have been created and sorted successfully.")
        else:
            print("Playlists have been created and sorted successfully.")


def import_from_csv(csv_file, dry_run):
    """
    Import tracks from a CSV file and add them to the corresponding playlists.
    CSV format: Artist,Track,Year,Spotify Uri
    """
    print("")
    print(f"=> Import from CSV file: {csv_file}")

    # Get Spotify client
    sp = get_spotify_client()
    if not sp:
        return

    # Read CSV file
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            csv_reader = csv.DictReader(f)
            tracks_data = list(csv_reader)
    except FileNotFoundError:
        print(f"Error: CSV file '{csv_file}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        sys.exit(1)

    if not tracks_data:
        print("No tracks found in CSV file.")
        sys.exit(0)

    # Group tracks by year to create playlists
    playlists_by_year = {}

    for i, row in enumerate(tracks_data):
        artist_name = row.get('Artist', 'Unknown Artist')
        track_name = row.get('Track', 'Unknown Track')
        year = row.get('Year', 'unsortiert')
        track_uri = row.get('Spotify Uri', '')

        if not track_uri:
            print(f"[ {bcolors.FAIL}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks_data))} Skip: Missing Spotify URI for {artist_name} - {track_name}")
            continue

        playlist_key = f"# Elektronisch - {year}"

        # Check if playlist exists or create it
        if playlist_key not in playlists_by_year:
            if check_playlist_exists(sp, playlist_key):
                playlists_by_year[playlist_key] = get_playlist_id_by_name(sp, playlist_key)
            else:
                if dry_run:
                    print(f"[ {bcolors.OKBLUE}Playlist{bcolors.ENDC} ] Would create: {playlist_key}")
                    playlists_by_year[playlist_key] = None  # Placeholder for dry-run
                else:
                    print(f"[ {bcolors.OKGREEN}Playlist{bcolors.ENDC} ] Create: {playlist_key}")
                    playlist = sp.user_playlist_create(user=username, name=playlist_key, public=False)
                    playlists_by_year[playlist_key] = playlist['id']

        # Add track to playlist
        if playlists_by_year[playlist_key] is None:
            # Dry-run mode with non-existent playlist
            print(f"[ {bcolors.OKBLUE}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks_data))} Would add: {artist_name} - {track_name} [{year}] -> {playlist_key}")
        elif not is_track_in_playlist(sp, playlists_by_year[playlist_key], track_uri):
            if dry_run:
                print(f"[ {bcolors.OKBLUE}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks_data))} Would add: {artist_name} - {track_name} [{year}] -> {playlist_key}")
            else:
                print(f"[ {bcolors.OKGREEN}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks_data))} Add: {artist_name} - {track_name} [{year}] -> {playlist_key}")
                try:
                    sp.playlist_add_items(playlists_by_year[playlist_key], [track_uri])
                    clear_playlist_cache(playlists_by_year[playlist_key])
                except Exception as e:
                    print(f"[ {bcolors.FAIL}Error{bcolors.ENDC}    ] Failed to add track: {e}")
        else:
            if dry_run:
                print(f"[ {bcolors.WARNING}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks_data))} Would skip existing: {artist_name} - {track_name} [{year}] -> {playlist_key}")
            else:
                print(f"[ {bcolors.WARNING}Track{bcolors.ENDC}    ] {progress_label(i+1, len(tracks_data))} Skip existing: {artist_name} - {track_name} [{year}] -> {playlist_key}")

    print("")
    if dry_run:
        print("Import would have been completed successfully.")
    else:
        print("Import completed successfully.")

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


def print_playlist_urls():
    """Authenticate and print full Spotify playlist URLs for entries in `playlists` from config."""
    sp = get_spotify_client()
    if not sp:
        return

    for playlist in playlists:
        playlist_id = get_playlist_id_by_name(sp, playlist)
        if playlist_id:
            print(f"https://open.spotify.com/playlist/{playlist_id}")
        else:
            print_error(f"Playlist not found: {playlist}")

def get_all_playlist_tracks(sp, playlist_id):
    """
    Retrieve all tracks from a playlist, handling pagination.
    Uses caching to avoid repeated API calls.
    Returns a list of track items.
    """
    # Check if data is in cache
    if playlist_id in PLAYLIST_CONTENT_CACHE:
        print(f"[ {bcolors.OKBLUE}Cache{bcolors.ENDC}    ] {playlist_id} -> Found")
        return PLAYLIST_CONTENT_CACHE[playlist_id]
    else:
        print(f"[ {bcolors.OKBLUE}Cache{bcolors.ENDC}    ] {playlist_id} -> Created")

    all_tracks = []
    offset = 0
    limit = 100

    while True:
        # Call with current offset
        response = sp.playlist_tracks(playlist_id, limit=limit, offset=offset)

        # Extract tracks from current response
        items = response['items']
        all_tracks.extend(items)

        # Check if we've reached the end
        if len(items) < limit:
            break

        # Increase offset for next iteration
        offset += limit

    # Store in cache
    PLAYLIST_CONTENT_CACHE[playlist_id] = all_tracks
    return all_tracks

def clear_playlist_cache(playlist_id):
    """Remove playlist contents from cache if present."""
    if playlist_id in PLAYLIST_CONTENT_CACHE:
        print(f"[ {bcolors.OKBLUE}Cache{bcolors.ENDC}    ] {playlist_id} -> Clear")
        del PLAYLIST_CONTENT_CACHE[playlist_id]


def is_track_in_playlist(sp, playlist_id, track_uri):
    """
    Check if a track exists in a playlist.
    Uses get_all_playlist_tracks which handles pagination and caching.
    """
    # Get all tracks from playlist (cached)
    playlist_tracks = get_all_playlist_tracks(sp, playlist_id)

    # Check if track exists in playlist
    for playlist_track in playlist_tracks:
        if playlist_track['track'] and playlist_track['track']['uri'] == track_uri:
            return True

    return False

dry_run = args_config['dry_run']
move = args_config['move']
export = args_config['export']
import_csv = args_config.get('import_csv')
urls_only = args_config.get('urls')

if urls_only:
    print_playlist_urls()
    sys.exit(0)

if move and export:
    print("Combine of move and export option not option not possible!")
    sys.exit(1)

if import_csv and (move or export):
    print("Import option cannot be combined with move or export options!")
    sys.exit(1)

if import_csv:
    # Import mode
    import_from_csv(import_csv, dry_run)
elif args_config['playlist']:
    sort_playlist_by_year(args_config['playlist'], dry_run, move, export, export_dir)
else:
    for playlist in playlists:
        sort_playlist_by_year(playlist, dry_run, move, export, export_dir)

print("")
