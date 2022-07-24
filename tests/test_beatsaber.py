from pathlib import Path
from typing import Any, List

import pytest
from unitunes.services.services import cache
from unitunes.services.beatsaber import BeatsaverAPIWrapper

from tests.conftest import cache_path


@pytest.fixture
def beatsaver_api_wrapper() -> BeatsaverAPIWrapper:
    return BeatsaverAPIWrapper(None, cache_path)


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


def test_search(beatsaver_api_wrapper: BeatsaverAPIWrapper):
    results = beatsaver_api_wrapper.search("my hero MAN WITH A MISSION", 0)
    first = results[0]
    assert len(results) > 1
    assert first["name"] == "My Hero - MAN WITH A MISSION ( Inuyashiki OP )"
