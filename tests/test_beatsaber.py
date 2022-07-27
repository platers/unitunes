from distutils.command.config import config
import json
from pathlib import Path
from typing import Any, List

import pytest
from unitunes.matcher import DefaultMatcherStrategy
from unitunes.searcher import DefaultSearcherStrategy
from unitunes.services.services import cache
from unitunes.services.beatsaber import BeatsaberService, BeatsaverAPIWrapper

from tests.conftest import cache_path
from unitunes.track import AliasedString, Track
from unitunes.uri import BeatsaberPlaylistURI, BeatsaberTrackURI


@pytest.fixture
def beatsaver_api_wrapper() -> BeatsaverAPIWrapper:
    return BeatsaverAPIWrapper(cache_path)


def test_get_map(beatsaver_api_wrapper: BeatsaverAPIWrapper):
    map = beatsaver_api_wrapper.map("27b65")
    assert map["id"] == "27b65"

    expected = {
        "id": "27b65",
        "name": "My Hero (TV Size) [Inuyashiki Opening] - MAN WITH A MISSION",
        "description": "Thanks to https://twitter.com/kitsunesoba1 for the special request!\n\nGameplay preview:\nhttps://youtu.be/uLcGgJEOGuQ\n\nMy Hero is the opening theme song of the Inuyashiki anime series, performed by the Japanese rock band Man with a Mission.\n\nKeep up to date on my maps: https://twitter.com/Joetastic_\nMy mapper's profile: https://bsaber.com/members/joetastic/\nContact me on discord: @Joetastic#2501\n\nEDIT:  Fixed a small inconsistency on E+",
        "uploader": {
            "id": 58338,
            "name": "Joetastic",
            "hash": "5cff0b7498cc5a672c85050e",
            "avatar": "https://cdn.beatsaver.com/avatar/227767566402191360.png",
            "type": "DISCORD",
            "curator": True,
            "verifiedMapper": True,
        },
        "metadata": {
            "bpm": 180,
            "duration": 92,
            "songName": "My Hero (TV Size)",
            "songSubName": "",
            "songAuthorName": "MAN WITH A MISSION",
            "levelAuthorName": "Joetastic",
        },
        "stats": {
            "plays": 0,
            "downloads": 0,
            "upvotes": 32,
            "downvotes": 1,
            "score": 0.8072,
        },
        "uploaded": "2022-07-12T18:40:15.270804Z",
        "automapper": False,
        "ranked": False,
        "qualified": False,
        "createdAt": "2022-07-12T18:40:04.134607Z",
        "updatedAt": "2022-07-12T19:14:09.477843Z",
        "lastPublishedAt": "2022-07-12T19:14:09.477843Z",
        "tags": ["j-rock", "anime", "balanced"],
    }
    assert expected.items() <= map.items()


def test_search_wrapper(beatsaver_api_wrapper: BeatsaverAPIWrapper):
    results = beatsaver_api_wrapper.search("my hero MAN WITH A MISSION", 0)
    first = results[0]
    assert len(results) > 1
    assert first["name"] == "My Hero - MAN WITH A MISSION ( Inuyashiki OP )"

    results = beatsaver_api_wrapper.search(
        "my hero MAN WITH A MISSION", 0, search_config={"minNps": 10}
    )
    # print(results)
    assert len(results) == 0


@pytest.fixture
def empty_dir():
    dir = Path("tests") / "test_bplists"
    dir.mkdir(exist_ok=True)
    assert dir.exists()

    yield dir

    dir.rmdir()


@pytest.fixture
def populated_dir(empty_dir: Path):
    raw = {
        "playlistTitle": "Bass House Music Pack",
        "playlistAuthor": "alphabeat",
        "playlistDescription": "A description",
        "image": "truncated47318904732189047201",
        "customData": {
            "syncURL": "https://api.beatsaver.com/playlists/id/7015/download"
        },
        "songs": [
            {
                "key": "27bfe",
                "hash": "24800f88b15041713940163bebaf344df0775471",
                "songName": "[Alphabeat - Bass House Pack] Cheyenne Giles - Jump Around",
            },
            {
                "key": "27ca1",
                "hash": "c07dfcec4114f36cd686273e8cd99f94651009d8",
                "songName": "[Alphabeat - Bass House Pack] Rootkit - Levitate",
            },
        ],
    }
    file = empty_dir / "bass_house_music_pack.bplist"
    file.write_text(json.dumps(raw, indent=4))

    yield empty_dir

    file.unlink()


@pytest.fixture
def Beatsaber(beatsaver_api_wrapper, populated_dir: Path):
    config = {
        "dir": populated_dir.absolute().__str__(),
        "search_config": {
            "minNps": 0.0,
            "maxNps": 1000,
            "minRating": 0,
            "sortOrder": "Relevance",
        },
    }
    return BeatsaberService("beatsaber", beatsaver_api_wrapper, config)


def test_pull_track(Beatsaber: BeatsaberService):
    track = Beatsaber.pull_track(BeatsaberTrackURI.from_uri("27b65"))
    assert track.name.value == "My Hero (TV Size)"
    assert track.artists[0].value == "MAN WITH A MISSION"


def test_search(Beatsaber: BeatsaberService):
    searcher = DefaultSearcherStrategy(DefaultMatcherStrategy())
    query_track = Track(
        name=AliasedString("My Hero"), artists=[AliasedString("MAN WITH A MISSION")]
    )
    results = searcher.search(Beatsaber, query_track, 3)
    assert len(results) > 0
    assert results[0].artists[0].value == "MAN WITH A MISSION"
    assert "My Hero" in results[0].name.value


def test_get_playlist_metadatas(Beatsaber: BeatsaberService):
    metas = Beatsaber.get_playlist_metadatas()
    assert len(metas) == 1
    assert metas[0].name == "Bass House Music Pack"
    assert metas[0].description == "A description"
    assert metas[0].uri.uri == "bass_house_music_pack.bplist"


def test_pull_tracks(Beatsaber: BeatsaberService):
    tracks = Beatsaber.pull_tracks(
        BeatsaberPlaylistURI.from_uri("bass_house_music_pack.bplist")
    )
    assert len(tracks) == 2
    assert tracks[0].name.value == "Jump Around"
    assert tracks[1].name.value == "Levitate"


def test_add_remove_tracks(Beatsaber: BeatsaberService):
    playlist = BeatsaberPlaylistURI.from_uri("bass_house_music_pack.bplist")
    track = Track(
        name=AliasedString("My Hero"),
        artists=[AliasedString("MAN WITH A MISSION")],
        uris=[BeatsaberTrackURI.from_uri("27b65")],
    )
    Beatsaber.add_tracks(playlist, [track])
    assert len(Beatsaber.pull_tracks(playlist)) == 3

    Beatsaber.remove_tracks(playlist, [track])
    assert len(Beatsaber.pull_tracks(playlist)) == 2
