from pathlib import Path
from typing import Any, List

import pytest
from unitunes.services.services import cache
from unitunes.services.ytm import YTM, YtmAPIWrapper, YtmWrapper
from unitunes.uri import YtmTrackURI

from tests.conftest import cache_path


class YtmLocalWrapper(YtmWrapper):
    def __init__(self, cache_root):
        super().__init__("ytm", cache_root=cache_root)

    @cache
    def get_playlist(self, *args, **kwargs) -> Any:
        raise NotImplementedError

    @cache
    def get_song(self, *args, use_cache=True, **kwargs) -> Any:
        raise NotImplementedError

    @cache
    def search(self, *args, use_cache=True, **kwargs) -> Any:
        raise NotImplementedError

    def create_playlist(self, title: str, description: str = "") -> str:
        raise NotImplementedError

    def edit_title(self, playlist_id: str, title: str) -> None:
        raise NotImplementedError

    def edit_description(self, playlist_id: str, description: str) -> None:
        raise NotImplementedError

    def add_tracks(self, playlist_id: str, track_ids: List[str]) -> None:
        raise NotImplementedError

    def remove_tracks(self, playlist_id: str, track_ids: List[str]) -> None:
        raise NotImplementedError

    def get_library_playlists(self, *args, **kwargs) -> Any:
        raise NotImplementedError


@pytest.fixture(scope="module")
def ytm_wrapper(pytestconfig):
    ytm_config_path = pytestconfig.getoption("ytm")
    if not ytm_config_path:
        return YtmLocalWrapper(cache_path)
    else:
        return YtmAPIWrapper(ytm_config_path, cache_path)


@pytest.fixture(scope="module")
def ytm_service(ytm_wrapper):
    return YTM("ytmtest", ytm_wrapper)


def test_ytm_can_pull_track(ytm_service):
    track = ytm_service.pull_track(
        YtmTrackURI.from_url("https://music.youtube.com/watch?v=KWLGyeg74es")
    )
    assert track.name.value == "Fireflies"
    assert track.artists[0].value == "Owl City"


def test_invalid_uri(ytm_service: YTM):
    assert ytm_service.is_uri_alive(
        YtmTrackURI.from_url(
            "https://music.youtube.com/watch?v=KWLGyeg74es"
        )  # may be flaky, check if url is valid
    )

    assert not ytm_service.is_uri_alive(
        YtmTrackURI.from_url("https://music.youtube.com/watch?v=WvvIjTtBYWM")
    )

    assert ytm_service.is_uri_alive(
        YtmTrackURI.from_url("https://music.youtube.com/watch?v=AKXNtLwP294")
    )
