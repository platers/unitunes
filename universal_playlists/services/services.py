from abc import ABC, abstractmethod
from pathlib import Path
import shelve
from typing import (
    Any,
    List,
    NewType,
    Optional,
)
from universal_playlists.matcher import DefaultMatcherStrategy
from universal_playlists.playlist import Playlist, PlaylistMetadata
from universal_playlists.track import Track

from universal_playlists.types import ServiceType
from universal_playlists.uri import PlaylistURI, PlaylistURIs, TrackURI


def cache(method):
    def wrapper(self, *args, use_cache=True, **kwargs):
        file_path = self.cache_path / f"{method.__name__}.shelve"
        d = shelve.open(file_path.__str__())
        cache_key = f"{args}_{kwargs}"
        if use_cache:
            if cache_key in d:
                return d[cache_key]
        result = method(self, *args, **kwargs)
        d[cache_key] = result
        d.close()
        return result

    return wrapper


class ServiceWrapper:
    cache_path: Path
    cache_name: str

    def create_cache_dir(self, cache_dir: Path):
        if not cache_dir.exists():
            cache_dir.mkdir()
        if not self.cache_path.exists():
            print(f"Creating cache dir: {self.cache_path}")
            self.cache_path.mkdir()

    def __init__(self, cache_name: str, cache_root: Path = Path("cache")) -> None:
        self.cache_name = cache_name
        self.cache_path = cache_root / cache_name
        self.create_cache_dir(cache_root)


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
    def push_playlist(self, playlist: Playlist) -> PlaylistURIs:
        """Pushes a playlist to the streaming service.
        Raises ValueError if the no PlaylistURI is found."""


class StreamingService(ABC):
    name: str
    type: ServiceType
    wrapper: ServiceWrapper

    def __init__(self, name: str, type: ServiceType) -> None:
        self.name = name
        self.type = type
