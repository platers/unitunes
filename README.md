# unitunes [![PyPI version](https://badge.fury.io/py/unitunes.svg)](https://badge.fury.io/py/unitunes) ![example workflow](https://github.com/platers/unitunes/actions/workflows/github-actions.yml/badge.svg)

![unituneslogo](https://github.com/platers/unitunes/blob/master/unitunes.png?raw=true)

A command-line interface tool to manage playlists across music streaming services.

## Introduction

unitunes manages playlists across streaming services. unitunes can transfer songs between services and keep playlists in sync.

unitunes stores your playlists in plain text, allowing you to version control your music. Playlists can be pushed and pulled from streaming services. Tracks from one service can be searched on another.

### Current Supported Streaming Services

| Name          | Pullable | Pushable | Searchable |
| ------------- | :------: | :------: | :--------: |
| MusicBrainz   |          |          |     ✅     |
| Spotify       |    ✅    |    ✅    |     ✅     |
| Youtube Music |    ✅    |    ✅    |     ✅     |

Want to add support for another service? See [contributing](#contributing).

## Documentation

[Documentation](https://github.com/platers/unitunes/blob/master/docs.md)

## Quickstart

### Installation

```bash
pip install unitunes
```

### Initialize

```bash
unitunes init
```

This creates a `config.json` file in the current directory.

### Add Services

#### Spotify

Follow the instructions at https://spotipy.readthedocs.io/en/2.19.0/#getting-started to obtain client credentials.

Put the credentials in a file like so:

```json
{
  "client_id": "...",
  "client_secret": "...",
  "redirect_uri": "http://example.com"
}
```

Register the service in unitunes:

```bash
unitunes service add spotify spotify_config.json
```

#### Youtube Music

Follow the instructions at https://ytmusicapi.readthedocs.io/en/latest/setup.html#manual-file-creation to create a `ytm_config.json` file.

Register the service in unitunes:

```bash
unitunes service add ytm ytm_config.json
```

### Add Playlists

Initialize UP's from your existing playlists:

```bash
unitunes fetch spotify # use -f to skip confirmation
unitunes fetch ytm
```

### Pull Playlists

Pull all tracks from all playlists.

```bash
unitunes pull
```

### Search Playlists

Search for tracks on another service:

```bash
unitunes search SERVICE_TYPE PLAYLIST_NAME
```

### Push Playlists

Push all changes to streaming services:

```bash
unitunes push
```

## Contributing

unitunes is in alpha. Contributions are very welcome. I am looking for collaborators to grow unitunes into a foundation for user controlled music software.

Take a look at the open issues!

### Development Setup

1. Fork and clone the repository.
2. Install [poetry](https://python-poetry.org/).
3. In the root directory, run `poetry shell`.
4. Run `poetry install`.
5. `unitunes` should now be runnable.

#### Testing

Run `pytest` to run tests. With no arguments, it will skip tests that require service configs.

Add a service config to run more tests.

```bash
pytest --spotify spotify_config.json --ytm ytm_config.json # may need to run with -s to paste spotify redirect URL the first time
```
