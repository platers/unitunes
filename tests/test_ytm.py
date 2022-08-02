from pathlib import Path
from typing import Any, List

import pytest
from unitunes.services.services import cache
from unitunes.services.ytm import YTM, YtmAPIWrapper, YtmConfig, YtmWrapper
from unitunes.uri import YtmTrackURI

from tests.conftest import cache_path


@pytest.fixture(scope="module")
def ytm_service(pytestconfig):
    config_path = pytestconfig.getoption("ytm", skip=True)
    return YTM("ytmtest", YtmConfig.parse_file(config_path), cache_path)


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
