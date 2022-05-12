import json
from pathlib import Path

import pytest
from universal_playlists.services.spotify import SpotifyService, SpotifyWrapper
from universal_playlists.uri import SpotifyTrackURI


@pytest.fixture(scope="module")
def spotify_wrapper(pytestconfig):
    config_path = pytestconfig.getoption("config")
    if not config_path:
        raise ValueError("config-path option is required for now")
    else:
        config_path = Path(config_path) / "spotify_config.json"
        with config_path.open() as f:
            config = json.load(f)
    cache = Path("tests/cache")
    return SpotifyWrapper(config, cache)


@pytest.fixture(scope="module")
def spotify_service(spotify_wrapper):
    return SpotifyService("spotifytest", spotify_wrapper)


def test_spotify_can_pull_track(spotify_service):
    track = spotify_service.pull_track(
        SpotifyTrackURI.from_url(
            "https://open.spotify.com/track/3DamFFqW32WihKkTVlwTYQ?si=ff5d6b0562ca4fb7"
        )
    )

    assert track.name.value == "Fireflies"
    assert track.artists[0].value == "Owl City"
