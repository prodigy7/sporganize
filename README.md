# sporganizer

A script to sort songs from different Spotify playlists into new lists by release year.

## Installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install all requirements.

```bash
pip install -r requirements.txt
```

The script supports an optional Home Assistant webhook. If you add `webhook_url` to `config.yaml`, the script will send a JSON payload to that URL for every actual track move.

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

## Setup

Execute the following commands to set up:

```bash
python3 -m venv .venv
```

## Usage

All necessary options are made in `config.yaml` (copy from `config.yaml.dist` previously!). Call up the command as follows:

```bash
source .venv/bin/activate
python3 sporganize.py
```

For available options call the command with `--help`.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

[MIT](https://choosealicense.com/licenses/mit/)
