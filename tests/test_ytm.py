import pytest
from unitunes.services.services import Pushable
from unitunes.services.ytm import YTM, YtmConfig
from unitunes.uri import YtmPlaylistURI, YtmTrackURI

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


def test_protocols(ytm_service: YTM):
    assert isinstance(ytm_service, Pushable)


def test_pull_metadata(ytm_service: YTM):
    imagine_dragons_playlist_uri = YtmPlaylistURI.from_url(
        "https://music.youtube.com/playlist?list=RDCLAK5uy_mzpBFnAPcGS-4FYm4BzAY-Q3VmvNCQwxY"
    )
    metadata = ytm_service.pull_metadata(imagine_dragons_playlist_uri)
    assert metadata.name == "Presenting Imagine Dragons"
    assert metadata.description == "The most played hits and essential tracks."
