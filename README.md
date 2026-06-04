# sporganize

Utility to sort tracks from Spotify playlists into target playlists by release year.

## Overview

sporganize connects to the Spotify Web API, reads configured source playlists and creates/updates per-year playlists (e.g. `# Elektronisch - 1998`) by copying or moving tracks. It supports exporting CSVs, webhook notifications, and container-friendly operation.

## Features

- Sort tracks from one or more source playlists into year-based playlists
- Copy or move tracks (`--move`)
- Export track lists to CSV (`--export`, `--export-dir`)
- Webhook notifications for moved/copied tracks (`WEBHOOK_URL`)
- Container-friendly auth flow and token cache handling

## Requirements

Python 3.8+ and the dependencies in `requirements.txt`.

## Installation

```bash
pip install -r requirements.txt
```

Optional: create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Configuration values are read from environment variables first, then from `config.yaml` if present. You can explicitly point to a config file or directory with `--config-path` or `CONFIG_PATH`.

Configuration search order (first existing wins):

1. `--config-path <path>` / `CONFIG_PATH` (file or directory containing `config.yaml`)
2. `$HOME/.config/sporganize/config.yaml`
3. `$HOME/.config/config.yaml`
4. `config.yaml` next to the script

Important configuration keys (env vars or `config.yaml`):

- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `SPOTIFY_USERNAME`
- `PLAYLISTS` or `SPOTIFY_PLAYLISTS` (comma-separated)
- `WEBHOOK_URL`
- `SPOTIFY_CACHE_PATH` or `spotify_cache_path` (optional path or directory to persist the OAuth token cache)

If no `SPOTIFY_CACHE_PATH` is set, the default token cache file will be placed in `~/.cache/.cache-<username>` (or `~/.cache/.cache` if no username).

## Authentication (why and how)

Why authentication is necessary:

- The Spotify Web API requires OAuth tokens for access to user playlists and to create/modify playlists. The script needs permission scopes to read and modify playlists on behalf of the user.
- Required OAuth scopes used by this tool: `playlist-read-private`, `playlist-modify-private`, `playlist-modify-public`.

How authentication works in `sporganize`:

1. On first run (or when no valid cached token exists) `sporganize` uses the Spotify OAuth authorization code flow to obtain an access token.
2. The script constructs an authorization URL and prints it to the terminal. The user visits that URL in a browser, approves the app, and Spotify redirects to the configured redirect URI with a code.
3. The user then pastes the full redirect URL (or the code) back into the terminal prompt. The script exchanges the code for an access token and stores it in the token cache file.

### Creating Spotify client credentials

1. Open the Spotify Developer Dashboard: https://developer.spotify.com/dashboard/applications
2. Log in with your Spotify account and click **Create an App**.
3. Give the app a name and description, then create it.
4. Add the redirect URI used by this script, e.g. `http://127.0.0.1:8080/callback`.
5. Make sure the app is configured for the Spotify Web API. This tool uses the Spotify Web API authorization code flow with the scopes `playlist-read-private`, `playlist-modify-private`, and `playlist-modify-public`.
6. Click on save.
7. Copy the **Client ID** and **Client Secret** from the app overview.
8. Provide these values to `sporganize` via environment variables or `config.yaml`:

```yaml
spotify_client_id: <your-client-id>
spotify_client_secret: <your-client-secret>
```

Or set environment variables:

```bash
export SPOTIFY_CLIENT_ID=<your-client-id>
export SPOTIFY_CLIENT_SECRET=<your-client-secret>
```

Keep the client secret private and do not commit it to source control.

Notes about token cache and containers:

- The token cache is stored in a file whose path is controlled by `SPOTIFY_CACHE_PATH` / `--cache-path` / `spotify_cache_path` in `config.yaml`. If a directory is provided the cache file is created inside it; if omitted it defaults to `~/.cache/.cache-<username>`.
- For containers, mount a host directory into the container at a chosen path and pass `--cache-path` or `SPOTIFY_CACHE_PATH` so the token persists across runs. Example with `docker run -v`:

```bash
docker run --rm -it \
  -v "$HOME/.sporganize-cache":/cache \
  -e SPOTIFY_CACHE_PATH=/cache \
  sporganize --auth-only
```

- `--auth-only` runs the authentication flow and exits after storing the token (useful to pre-authenticate an interactive container).
- If running non-interactively (no TTY) the script cannot prompt for the redirect URL; run an interactive container to complete the flow.

Security note:

- Keep your `SPOTIFY_CLIENT_SECRET` and token cache file private; do not commit them to version control.

## Usage

Basic usage:

```bash
python3 sporganize.py [playlist] [options]
```

Common options:

- `--dry-run` : simulate changes without modifying playlists
- `--move` : move tracks instead of copying
- `--export` : export track list to CSV
- `--export-dir DIR` : directory for CSV exports
- `--auth-only` : perform OAuth authentication and exit
- `--cache-path PATH` / `SPOTIFY_CACHE_PATH` : token cache path

For full options:

```bash
python3 sporganize.py --help
```

## Container / Docker

Build locally:

```bash
docker build -f .build/Dockerfile -t sporganize .
```

Run one-off interactive auth (recommended for first-time container use):

```bash
docker compose run --rm -it sporganize --auth-only
```

The container's entrypoint will by default run `sporganize.py` periodically. To run a single pass set `INTERVAL_SECONDS=0` or `RUN_ONCE=1` in the environment. Passing `--auth-only` causes the entrypoint to run once and exit after authentication.

## Export & History

- Exported CSVs will be written to the directory given with `--export-dir` or `EXPORT_DIR` and will be created if missing.
- Created target playlist names are recorded in `paylists.csv` (to keep a list of generated playlists); duplicates are avoided.

## Webhook (Home Assistant example)

If `WEBHOOK_URL` is configured, the script posts a JSON payload for each actual track move/copy. The payload includes fields such as `event`, `track`, `artist`, `year`, `from_playlist`, `to_playlist`, `track_uri`, `dry_run`, and `message`.

Example automation in Home Assistant (use the `webhook_id` you configure):

```yaml
alias: Spotify track moved notification
trigger:
  - platform: webhook
    webhook_id: spotify_track_moved
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "Sporganize: {{ trigger.json.artist }} - {{ trigger.json.track }}"
      message: |-
        Track: {{ trigger.json.artist }} - {{ trigger.json.track }}
        From: {{ trigger.json.from_playlist }}
        To: {{ trigger.json.to_playlist }}
        Dry run: {{ trigger.json.dry_run }}
      data:
        url: "{{ trigger.json.track_uri }}"
```

## Contributing

Pull requests are welcome. For major changes, open an issue first to discuss.

## License

[MIT](https://choosealicense.com/licenses/mit/)
