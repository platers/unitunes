import pytest
from unitunes.services.services import Pushable
from unitunes.services.spotify import (
    SpotifyConfig,
    SpotifyService,
)
from unitunes.uri import SpotifyPlaylistURI, SpotifyTrackURI

from tests.conftest import cache_path


@pytest.fixture(scope="module")
def spotify_service(pytestconfig):
    """Returns a SpotifyService object. Abstract if no config is provided."""
    spotify_config_path = pytestconfig.getoption("spotify", skip=True)
    return SpotifyService(
        "spotifytest", SpotifyConfig.parse_file(spotify_config_path), cache_path
    )


def test_spotify_can_pull_track(spotify_service):
    track = spotify_service.pull_track(
        SpotifyTrackURI.from_url(
            "https://open.spotify.com/track/3DamFFqW32WihKkTVlwTYQ?si=ff5d6b0562ca4fb7"
        )
    )

    assert track.name.value == "Fireflies"
    assert track.artists[0].value == "Owl City"


def test_spotify_can_pull_playlist(spotify_service):
    tracks = spotify_service.pull_tracks(
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


def test_pull_liked_tracks(spotify_service):
    tracks = spotify_service.pull_tracks(
        SpotifyPlaylistURI.from_url("spotify:liked_songs")
    )
    assert len(tracks) > 5


def test_spotify_can_search(spotify_service: SpotifyService):
    results = spotify_service.search_query(
        'track:"tfarotnfarotnferiatfartnfarotnferiatfarotnfarotnferiatfarotnfarotnfeatfarotnfarotnferiatfarotnfarotnferia"'
    )  # Long queries are unsupported.
    assert results is not None


def test_spotify_is_pushable(spotify_service: SpotifyService):
    assert isinstance(spotify_service, Pushable)
