from abc import ABC, abstractmethod
import json
from pathlib import Path
from typing import (
    Any,
    List,
    NewType,
)
from unitunes.playlist import PlaylistMetadata
from unitunes.track import Track

from unitunes.types import ServiceType
from unitunes.uri import PlaylistURI, PlaylistURIs, TrackURI


def cache(method):
    def wrapper(self, *args, use_cache=True, **kwargs):
        file_path = self.cache_path / f"{method.__name__}.json"
        if use_cache and file_path.exists():
            with file_path.open("r") as f:
                try:
                    d = json.load(f)
                except json.JSONDecodeError:
                    d = {}
        else:
            d = {}

        cache_key = f"{args}_{kwargs}"
        if use_cache and cache_key in d:
            return d[cache_key]
        result = method(self, *args, **kwargs)
        d[cache_key] = method(self, *args, **kwargs)

        with file_path.open("w") as f:
            json.dump(d, f, indent=4)

        return result

    return wrapper


class ServiceWrapper:
    cache_path: Path
    cache_name: str

    def __init__(self, cache_name: str, cache_root: Path) -> None:
        self.cache_name = cache_name
        self.cache_path = cache_root / cache_name
        if not cache_root.exists():
            cache_root.mkdir()
        if not self.cache_path.exists():
            self.cache_path.mkdir()


class UserPlaylistPullable(ABC):
    @abstractmethod
    def get_playlist_metadatas(self) -> list[PlaylistMetadata]:
        """Returns the users playlists"""

    def get_playlist_metadata(self, playlist_name: str) -> PlaylistMetadata:
        metas = self.get_playlist_metadatas()
        for meta in metas:
            if meta.name == playlist_name:
                return meta
        raise ValueError(
            f"Playlist {playlist_name} not found. Available playlists: {', '.join([meta.name for meta in metas])}"
        )


class PlaylistPullable(ABC):
    @abstractmethod
    def pull_tracks(self, uri: PlaylistURI) -> List[Track]:
        """Gets tracks from a playlist"""


class TrackPullable(ABC):
    @abstractmethod
    def pull_track(self, uri: TrackURI) -> Track:
        raise NotImplementedError


Query = NewType("Query", Any)


class Searchable(ABC):
    @abstractmethod
    def search_query(self, query: Query) -> List[Track]:
        """Search for a query in the streaming service. Returns a list of potential matches."""

    @abstractmethod
    def query_generator(self, track: Track) -> List[Query]:
        """Returns a list of queries that could be used to search for a track.
        Sorted from most precise to least precise."""


class Pushable(PlaylistPullable):
    @abstractmethod
    def create_playlist(self, title: str, description: str = "") -> PlaylistURIs:
        """Creates a new playlist"""

    @abstractmethod
    def add_tracks(self, playlist_uri: PlaylistURI, tracks: List[Track]) -> None:
        """Adds tracks to a playlist"""

    @abstractmethod
    def remove_tracks(self, playlist_uri: PlaylistURI, tracks: List[Track]) -> None:
        """Removes tracks from a playlist"""


class StreamingService(ABC):
    name: str
    type: ServiceType
    wrapper: ServiceWrapper

    def __init__(self, name: str, type: ServiceType) -> None:
        self.name = name
        self.type = type
