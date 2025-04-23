# sporganizer

A script to sort songs from different Spotify playlists into new lists by release year.

## Installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install all requirements.

```bash
pip install -r requirements.txt
```

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
