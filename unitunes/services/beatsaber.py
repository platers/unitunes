from abc import ABC, abstractmethod
from typing import Any, List
import spotipy
from unitunes.playlist import Playlist, PlaylistMetadata
import requests

from unitunes.services.services import (
    Pushable,
    Searchable,
    ServiceWrapper,
    StreamingService,
    TrackPullable,
    UserPlaylistPullable,
    cache,
)
from unitunes.track import AliasedString, Track
from unitunes.types import ServiceType
from unitunes.uri import (
    URI,
    PlaylistURI,
    PlaylistURIs,
)


class BeatsaberWrapper(ServiceWrapper, ABC):
    @cache
    @abstractmethod
    def map(self, id: str, use_cache=True) -> Any:
        pass

    @cache
    @abstractmethod
    def search(self, query: str, page: int, use_cache=True, **kwargs) -> Any:
        pass


class BeatsaverAPIWrapper(BeatsaberWrapper):
    def __init__(self, config, cache_root) -> None:
        super().__init__("beatsaver", cache_root=cache_root)

    @cache
    def map(self, id: str, use_cache=True) -> Any:
        return requests.get(f"https://api.beatsaver.com/maps/id/{id}").json()

    @cache
    def search(self, query: str, page: int, use_cache=True, **kwargs) -> Any:
        return requests.get(
            f"https://api.beatsaver.com/search/text/{page}",
            params={"q": query, "sortOrder": "Relevance"},
        ).json()["docs"]
