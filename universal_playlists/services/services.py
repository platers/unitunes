from enum import Enum
from pathlib import Path
import shelve
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    TypedDict,
)
from pydantic import BaseModel
from strsimpy.jaro_winkler import JaroWinkler
from rich import print
from universal_playlists.playlist import PlaylistMetadata
from universal_playlists.track import Track

from universal_playlists.types import ServiceType
from universal_playlists.uri import PlaylistURI, PlaylistURIs, TrackURI, TrackURIs


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
    def __init__(self, cache_name: str) -> None:
        cache_root = Path("cache")
        if not cache_root.exists():
            cache_root.mkdir()
        self.cache_path = Path("cache") / cache_name
        if not self.cache_path.exists():
            self.cache_path.mkdir()


class StreamingService:
    def __init__(self, name: str, type: ServiceType, config_path: Path) -> None:
        self.name = name
        self.type = type
        self.config_path = config_path

    def get_playlist_metadatas(self) -> list[PlaylistMetadata]:
        raise NotImplementedError

    def get_playlist_metadata(self, playlist_name: str) -> PlaylistMetadata:
        metas = self.get_playlist_metadatas()
        for meta in metas:
            if meta.name == playlist_name:
                return meta
        raise ValueError(
            f"Playlist {playlist_name} not found in {self.name}. Available playlists: {', '.join([meta.name for meta in metas])}"
        )

    def pull_tracks(self, uri: PlaylistURI) -> List[Track]:
        raise NotImplementedError

    def pull_track(self, uri: TrackURI) -> Track:
        raise NotImplementedError

    def search_track(self, track: Track) -> List[Track]:
        """Search for a track in the streaming service. Returns a list of potential matches."""
        raise NotImplementedError
