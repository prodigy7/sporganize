# sporganizer

A script to sort songs from different Spotify playlists into new lists by release year.

## Installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install all requirements.

```bash
pip install -r requirements.txt
```

The script supports environment-based configuration. `config.yaml` is optional as long as the required values are provided through environment variables.

You can also explicitly specify a config file or config directory using `--config-path` or the `CONFIG_PATH` environment variable.

The script searches for configuration in this order:

1. `--config-path <path>` or `CONFIG_PATH=<path>` if provided
   - if the path includes a file name, it is used as the config file path
   - if the path is a directory, the script looks for `config.yaml` inside that directory
2. `$HOME/.config/sporganize/config.yaml`
3. `$HOME/.config/config.yaml`
4. `config.yaml` in the script directory

The following values are read from environment variables first, then from `config.yaml` if not set:

- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `SPOTIFY_USERNAME`
- `PLAYLISTS` or `SPOTIFY_PLAYLISTS` (comma-separated list)
- `WEBHOOK_URL`

If you set `WEBHOOK_URL` in the container environment, the script will send a JSON payload to that URL for every actual track move.

When a track is actually added to a target playlist (copy or move), the target playlist name is also stored in `paylists.csv`. Duplicate playlist names are not written again.

### Home Assistant webhook setup

1. Open Home Assistant and go to `Settings -> Automations & Scenes -> Automations`.
2. Create a new automation and choose `Webhook` as the trigger type.
3. Set a webhook ID, for example `spotify_track_moved`.
4. Use the full webhook URL in `config.yaml` like `https://<your-home-assistant>/api/webhook/spotify_track_moved`.
5. Add an action for the automation, for example a notification or a logbook entry.

The payload that is posted is a JSON object with fields such as `event`, `track`, `artist`, `year`, `from_playlist`, `to_playlist`, `track_uri`, `dry_run`, and `message`.

#### Example Home Assistant automation

```yaml
alias: Spotify track moved notification
trigger:
  - platform: webhook
    webhook_id: spotify_track_moved
condition: []
action:
  - service: notify.mobile_app_your_phone
    data:
      message: |-
        Track: {{ trigger.json.artist }} - {{ trigger.json.track }}
        Source: {{ trigger.json.from_playlist }}
        Target: {{ trigger.json.to_playlist }}
        Action: {% if trigger.json.event == "spotify_track_moved" %}Move{% else %}Copy{% endif %}
        Execution: {% if trigger.json.dry_run %}No{% else %}Yes{% endif %}
      title: "Sporganize: {{ trigger.json.artist }} - {{ trigger.json.track }}"
      data:
        url: "{{ trigger.json.track_uri }}"
```

In the action, Home Assistant makes the webhook body available via `trigger.json`, so you can use the fields directly in notifications or other automations.

### Container build and local deployment

Build the Docker image locally with:

```bash
docker build -f .build/Dockerfile -t sporganize .
```

Or use the provided `docker-compose.yml` to build and start the service:

```bash
docker compose build
docker compose up -d
```

`docker compose up -d` starts the `sporganize` service in the background. The container runs `/app/entrypoint.sh`, which by default executes `sporganize.py` repeatedly every `INTERVAL_SECONDS` (default `300`).

To run once instead of on an interval, set one of these environment values:

```yaml
services:
  sporganize:
    environment:
      - RUN_ONCE=1
```

or

```yaml
services:
  sporganize:
    environment:
      - INTERVAL_SECONDS=0
```

If you want the Compose service to start in dry-run mode, add a `command` override:

```yaml
services:
  sporganize:
    command: ["--dry-run", "--move"]
```

You can also pass CLI arguments directly when running the container interactively:

```bash
docker compose run --rm sporganize --dry-run --move
```

And with `docker run`:

```bash
docker run --rm \
  -v "$PWD/paylists.csv":/app/paylists.csv \
  sporganize --dry-run --move
```

Execute the following commands to set up a Python virtual environment:

```bash
python3 -m venv .venv
```

## Usage

The script prefers environment variables and only needs `config.yaml` when values are not supplied through the environment. You can copy `config.yaml.dist` to `config.yaml`, or configure the same values in `docker-compose.env` or your container runtime.

If you use `--export`, you can also set the output directory with `--export-dir DIR` or `EXPORT_DIR=DIR`. The directory will be created automatically if it does not yet exist, and the script checks that it is writable before exporting.

```bash
source .venv/bin/activate
python3 sporganize.py
```

For available options, run:

```bash
python3 sporganize.py --help
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

[MIT](https://choosealicense.com/licenses/mit/)
