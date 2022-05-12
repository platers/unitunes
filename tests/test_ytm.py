import json
from pathlib import Path
import shutil

import pytest
from universal_playlists.services.ytm import YTM, YtmWrapper
from universal_playlists.uri import YtmTrackURI


@pytest.fixture(scope="module")
def ytm_wrapper():
    # delete cache folder
    cache = Path("tests/.cache")
    if cache.exists():
        shutil.rmtree(cache)
    return YtmWrapper(Path("tests") / "service_configs" / "ytm_config.json", cache)


@pytest.fixture(scope="module")
def ytm_service(ytm_wrapper):
    return YTM("ytmtest", ytm_wrapper)


def test_ytm_can_pull_track(ytm_service):
    track = ytm_service.pull_track(
        YtmTrackURI.from_url("https://music.youtube.com/watch?v=KWLGyeg74es")
    )
    assert track.name.value == "Fireflies"
    assert track.artists[0].value == "Owl City"
