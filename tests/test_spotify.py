import json
from pathlib import Path
from typing import Any, List

import pytest
from unitunes.services.services import cache
from unitunes.services.spotify import (
    SpotifyAPIWrapper,
    SpotifyService,
    SpotifyWrapper,
)
from unitunes.uri import SpotifyPlaylistURI, SpotifyTrackURI

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

    def playlist_tracks(self, *args, **kwargs) -> Any:
        raise NotImplementedError

    def current_user(self, *args, **kwargs) -> Any:
        raise NotImplementedError

    def user_playlist_create(self, *args, **kwargs) -> Any:
        raise NotImplementedError

    def current_user_saved_tracks(self, limit: int = 20, offset: int = 0) -> Any:
        raise NotImplementedError

    def current_user_saved_tracks_add(self, tracks: List[str]) -> None:
        raise NotImplementedError

    def current_user_saved_tracks_delete(self, tracks: List[str]) -> None:
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
    """Returns a SpotifyService object. Abstract if no config is provided."""
    return SpotifyService("spotifytest", spotify_wrapper)


@pytest.fixture(scope="module")
def spotify_api_service(pytestconfig):
    """Returns a real SpotifyService object. Config is required."""
    spotify_config_path = pytestconfig.getoption("spotify", skip=True)
    with open(spotify_config_path) as f:
        wrapper = SpotifyAPIWrapper(json.load(f), cache_path)
    return SpotifyService("spotifytest", wrapper)


def test_spotify_can_pull_track(spotify_service):
    track = spotify_service.pull_track(
        SpotifyTrackURI.from_url(
            "https://open.spotify.com/track/3DamFFqW32WihKkTVlwTYQ?si=ff5d6b0562ca4fb7"
        )
    )

    assert track.name.value == "Fireflies"
    assert track.artists[0].value == "Owl City"


def test_spotify_can_pull_playlist(spotify_api_service):
    tracks = spotify_api_service.pull_tracks(
        SpotifyPlaylistURI.from_url(
            "https://open.spotify.com/playlist/19TGUNYKnJ8N1bFe0oA5lv"
        )
    )
    assert len(tracks) > 5


def test_liked_songs_uri():
    uri = SpotifyPlaylistURI.from_url("spotify:liked_songs")
    assert uri.uri == "Liked Songs"
    assert uri.type == "playlist"
    assert uri.is_liked_songs()


def test_pull_liked_tracks(spotify_api_service):
    tracks = spotify_api_service.pull_tracks(
        SpotifyPlaylistURI.from_url("spotify:liked_songs")
    )
    assert len(tracks) > 5


def test_spotify_can_search(spotify_service: SpotifyService):
    results = spotify_service.search_query(
        'track:"value=\'OBENTO MAGNUM\' aliases=[]" artist:"DOKONJOFINGER(CV:?????????????????????????????????????????????????????????)" album:"TV????????????SHOW BY ROCK!!STARS!!?????????????????????????????? Vol.1"'
    )  # this is a tricky URL due to the album. Spotipy returns 404, make sure we handle gracefully.
    assert results is not None
