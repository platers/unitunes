import json
from pathlib import Path
from typing import Any, List

import pytest
from unitunes.matcher import DefaultMatcherStrategy
from unitunes.playlist import PlaylistDetails
from unitunes.searcher import DefaultSearcherStrategy
from unitunes.services.services import Pushable, cache
from unitunes.services.beatsaver import (
    BeatSaverConfig,
    BeatSaverService,
    BeatSaverAPIWrapper,
)

from tests.conftest import cache_path
from unitunes.track import AliasedString, Track
from unitunes.uri import BeatSaverPlaylistURI, BeatSaverTrackURI


@pytest.fixture
def empty_dir():
    dir = Path("tests") / "test_beatsaver"
    dir.mkdir(exist_ok=True)
    assert dir.exists()

    yield dir

    dir.rmdir()


@pytest.fixture
def BeatSaver(pytestconfig):
    config_path = pytestconfig.getoption("beatsaver", skip=True)
    config = BeatSaverConfig.parse_file(config_path)
    return BeatSaverService("BeatSaver", config, cache_path)


def test_pull_track(BeatSaver: BeatSaverService):
    track = BeatSaver.pull_track(BeatSaverTrackURI.from_uri("27b65"))
    assert track.name.value == "My Hero (TV Size)"
    assert track.artists[0].value == "MAN WITH A MISSION"


def test_search(BeatSaver: BeatSaverService):
    searcher = DefaultSearcherStrategy(DefaultMatcherStrategy())
    query_track = Track(
        name=AliasedString("My Hero"), artists=[AliasedString("MAN WITH A MISSION")]
    )
    results = searcher.search(BeatSaver, query_track, 3)
    assert len(results) > 0
    assert results[0].artists[0].value == "MAN WITH A MISSION"
    assert "My Hero" in results[0].name.value


def test_get_playlist_metadatas(BeatSaver: BeatSaverService):
    metas = BeatSaver.get_playlist_metadatas()
    assert len(metas) > 1


def test_pull_tracks(BeatSaver: BeatSaverService):
    tracks = BeatSaver.pull_tracks(BeatSaverPlaylistURI.from_uri("7803"))
    assert len(tracks) == 1


def test_add_remove_tracks(BeatSaver: BeatSaverService):
    playlist = BeatSaverPlaylistURI.from_uri("7803")
    track = Track(
        name=AliasedString("My Hero"),
        artists=[AliasedString("MAN WITH A MISSION")],
        uris=[BeatSaverTrackURI.from_uri("27b65")],
    )
    BeatSaver.add_tracks(playlist, [track])
    assert len(BeatSaver.pull_tracks(playlist)) == 2

    BeatSaver.remove_tracks(playlist, [track])
    assert len(BeatSaver.pull_tracks(playlist)) == 1


def test_update_metadata(BeatSaver: BeatSaverService):
    playlist = BeatSaverPlaylistURI.from_uri("7803")
    metadata = PlaylistDetails(
        name="Test Playlist",
        description="Test description",
    )
    BeatSaver.update_metadata(playlist, metadata)
    assert BeatSaver.pull_metadata(playlist).description == "Test description"


def test_protocols(BeatSaver: BeatSaverService):
    assert isinstance(BeatSaver, Pushable)
