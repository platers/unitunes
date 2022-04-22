from enum import Enum
import json
from pathlib import Path
import shelve
from typing import List, Optional, TypedDict
from pydantic import BaseModel
from strsimpy.jaro_winkler import JaroWinkler


class ServiceType(Enum):
    SPOTIFY = "spotify"
    YTM = "youtube-music"
    MB = "musicbrainz"


class URI(BaseModel):
    service: str
    uri: str

    class Config:
        frozen = True

    def url(self) -> str:
        return f"{self.service}:{self.uri}"


def normalized_string_similarity(s1: str, s2: str) -> float:
    jw = JaroWinkler().similarity(s1, s2)
    # convert to [-1, 1]
    return (jw - 0.5) * 2


def name_similarity(name1: str, name2: str) -> float:
    return normalized_string_similarity(name1, name2)


def artists_similarity(artists1: List[str], artists2: List[str]) -> float:
    if len(artists1) == 0 or len(artists2) == 0:
        return 0

    mx_similarity = 0
    for artist1 in artists1:
        for artist2 in artists2:
            mx_similarity = max(
                mx_similarity, normalized_string_similarity(artist1, artist2)
            )

    return mx_similarity


def album_similarity(album1: str, album2: str) -> float:
    return normalized_string_similarity(album1, album2)


def length_similarity(length_sec_1: int, length_sec_2: int) -> float:
    d = abs(length_sec_1 - length_sec_2)
    max_dist = 4
    if d > max_dist:
        return -1
    return 1 - d / max_dist


class Track(BaseModel):
    name: str
    album: Optional[str] = None
    album_position: Optional[int] = None
    artists: List[str] = []
    length: Optional[int] = None
    uris: List[URI] = []

    def similarity(self, other: "Track") -> float:
        # check if any URI in track matches any URI in self
        for uri in self.uris:
            if uri in other.uris:
                return 1

        total_weight = 0
        similarity = 0

        if self.name and other.name:
            name_weight = 50
            similarity += name_weight * name_similarity(self.name, other.name)
            total_weight += name_weight

        if self.artists and other.artists:
            artists_weight = 30
            similarity += artists_weight * artists_similarity(
                self.artists, other.artists
            )
            total_weight += artists_weight

        if self.album and other.album:
            album_weight = 20
            similarity += album_weight * album_similarity(self.album, other.album)
            total_weight += album_weight

        if self.length and other.length:
            length_weight = 20
            similarity += length_weight * length_similarity(self.length, other.length)
            total_weight += length_weight

        similarity /= total_weight
        assert -1 <= similarity <= 1
        return similarity

    def matches(self, track: "Track", threshold: float = 0.8) -> bool:
        return self.similarity(track) > threshold


class PlaylistMetadata(TypedDict):
    name: str
    description: str
    uri: URI


class Playlist(BaseModel):
    name: str
    description: str = ""
    uris: List[URI] = []
    tracks: List[Track] = []

    def merge_metadata(self, metadata: PlaylistMetadata) -> None:
        self.name = self.name or metadata["name"]
        self.description = self.description or metadata["description"]
        if metadata["uri"] not in self.uris:
            self.uris.append(metadata["uri"])


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
    def __init__(self, name: str, config_path: Path) -> None:
        self.name = name
        self.config_path = config_path

    def get_playlist_metadatas(self) -> list[PlaylistMetadata]:
        raise NotImplementedError

    def get_playlist_metadata(self, playlist_name: str) -> PlaylistMetadata:
        metas = self.get_playlist_metadatas()
        for meta in metas:
            if meta["name"] == playlist_name:
                return meta
        raise ValueError(f"Playlist {playlist_name} not found in {self.name}")

    def pull_tracks(self, uri: URI) -> List[Track]:
        raise NotImplementedError

    def pull_track(self, uri: URI) -> Track:
        raise NotImplementedError

    def search_track(self, track: Track) -> List[Track]:
        """Search for a track in the streaming service. Returns a list of potential matches."""
        raise NotImplementedError
