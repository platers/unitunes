import json
from pathlib import Path
from typing import Any, List

import pytest
from universal_playlists.services.services import cache
from universal_playlists.services.spotify import (
    SpotifyAPIWrapper,
    SpotifyService,
    SpotifyWrapper,
)
from universal_playlists.uri import SpotifyTrackURI

from tests.conftest import cache_path


class LocalSpotifyWrapper(SpotifyWrapper):
    def __init__(self, cache_root) -> None:
        super().__init__("spotify", cache_root=cache_root)

    @cache
    def track(self, *args, use_cache=True, **kwargs):
        raise NotImplementedError

    @cache
    def album_tracks(self, *args, use_cache=True, **kwargs) -> Any:
        pass

    @cache
    def search(self, *args, use_cache=True, **kwargs) -> Any:
        pass

    def create_playlist(self, title: str, description: str = "") -> str:
        raise NotImplementedError

    def add_tracks(self, playlist_id: str, tracks: List[str]) -> None:
        raise NotImplementedError

    def remove_tracks(self, playlist_id: str, tracks: List[str]) -> None:
        raise NotImplementedError

    def current_user_playlists(self, *args, **kwargs) -> Any:
        raise NotImplementedError

    def user_playlist_replace_tracks(self, *args, **kwargs):
        raise NotImplementedError

    def user_playlist_tracks(self, *args, **kwargs) -> Any:
        raise NotImplementedError

    def current_user(self, *args, **kwargs) -> Any:
        raise NotImplementedError

    def user_playlist_create(self, *args, **kwargs) -> Any:
        raise NotImplementedError


@pytest.fixture(scope="module")
def spotify_wrapper(pytestconfig):
    spotify_config_path = pytestconfig.getoption("spotify")
    if not spotify_config_path:
        return LocalSpotifyWrapper(cache_path)
    else:
        with open(spotify_config_path) as f:
            return SpotifyAPIWrapper(json.load(f), cache_path)


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
