# unitunes [![PyPI version](https://badge.fury.io/py/unitunes.svg)](https://badge.fury.io/py/unitunes) ![example workflow](https://github.com/platers/unitunes/actions/workflows/github-actions.yml/badge.svg)

![unituneslogo](assets/unitunes.png)

A python GUI and library to sync playlists across music streaming services.

## Introduction

unitunes manages playlists across streaming services. unitunes can transfer songs between services and keep playlists in sync.

unitunes stores your playlists in plain text, allowing you to version control your music. Playlists can be pushed and pulled from streaming services. Tracks from one service can be searched on another.

### Current Supported Streaming Services

| Name          | Pullable | Pushable | Searchable |
| ------------- | :------: | :------: | :--------: |
| MusicBrainz   |          |          |     ✅     |
| Spotify       |    ✅    |    ✅    |     ✅     |
| Youtube Music |    ✅    |    ✅    |     ✅     |
| Beatsaber     |    ✅    |    ✅    |     ✅     |

Want to add support for another service? See [contributing](#contributing).

### How it works

All data is stored with json files stored in a music directory. You can version control this directory with git.

Unitunes supports three operations: pulling, searching, and pushing. Pulling a playlist updates the unitunes playlist with the latest tracks from the streaming service. Searching tries to find matching tracks on other streaming services and adds them to the unitunes playlist. Pushing a playlist adds the tracks in the unitunes playlist to the streaming service. For convenience, there is a `Sync` button that performs all three operations.

## Usage

```bash
# Clone the repo
git clone https://github.com/platers/unitunes.git
# Change directory
cd unitunes
# Start a poetry shell
poetry shell
# Install dependencies
poetry install
# Run the GUI
streamlit run unitunes/streamlit/Unitunes.py -- --music-dir {path to music directory}
```

First connect streaming services on the service page. Enter the service name and type. After adding a service, follow the instructions in the app to configure it. Each service type requires some configuration, Spotify requires a client id and secret, and Youtube Music requires request headers.

Playlists can then be added to the playlist tab.

After adding playlists, you can sync them. You likely just want to press the `Sync All` button, which will pull, search, and push all playlists.

## Contributing

unitunes is still in an alpha state. Take a look at the [contributing guide](CONTRIBUTING.md).
