from enum import Enum
from pathlib import Path
import shelve
from typing import List, Literal, NewType, Optional, TypedDict, Union
from pydantic import BaseModel
from strsimpy.jaro_winkler import JaroWinkler
from pydantic.validators import dict_validator
from abc import ABC, abstractmethod


class ServiceType(str, Enum):
    SPOTIFY = "spotify"
    YTM = "ytm"
    MB = "mb"


class URIBase(BaseModel, ABC):
    service: str
    uri: str

    class Config:
        frozen = True

    @abstractmethod
    def url(self) -> str:
        pass

    def __rich__(self) -> str:
        return f"[link={self.url()}]{self.url()}[/link]"

    @classmethod
    def get_validators(cls):
        # yield dict_validator
        yield cls.validate

    @classmethod
    def validate(cls, value):
        if isinstance(value, cls):
            return value
        else:
            return cls(**dict_validator(value))


class SpotifyURI(URIBase):
    type: Literal["spotify"] = "spotify"

    def __init__(self, **kwargs):
        kwargs["service"] = ServiceType.SPOTIFY.value
        super().__init__(**kwargs)

    def url(self) -> str:
        return f"https://open.spotify.com/track/{self.uri}"

    @staticmethod
    def url_to_uri(url: str) -> str:
        return url.split("/")[-1]

    @staticmethod
    def from_url(url: str) -> "SpotifyURI":
        return SpotifyURI(uri=SpotifyURI.url_to_uri(url))


class YtmURI(URIBase):
    type: Literal["ytm"] = "ytm"

    def __init__(self, **kwargs):
        kwargs["service"] = ServiceType.YTM.value
        super().__init__(**kwargs)

    def url(self) -> str:
        return f"https://music.youtube.com/watch?v={self.uri}"


class MB_RECORDING_URI(URIBase):
    type: Literal["mb_recording"] = "mb_recording"

    def __init__(self, **kwargs):
        kwargs["service"] = ServiceType.MB.value
        super().__init__(**kwargs)

    def url(self) -> str:
        return f"https://musicbrainz.org/recording/{self.uri}"


class MB_RELEASE_URI(URIBase):
    type: Literal["mb_release"] = "mb_release"

    def __init__(self, **kwargs):
        kwargs["service"] = ServiceType.MB.value
        super().__init__(**kwargs)

    def url(self) -> str:
        return f"https://musicbrainz.org/release/{self.uri}"


URI = Union[SpotifyURI, YtmURI, MB_RECORDING_URI, MB_RELEASE_URI]


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
    str_sim = normalized_string_similarity(album1, album2)
    if str_sim < 0:
        str_sim /= 5

    return str_sim


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

    def __rich__(self):
        s = f"[b]{self.name}[/b]"
        if self.artists:
            s += f"\nArtists: {', '.join(self.artists)}"
        if self.album:
            s += f"\nAlbum: {self.album}"
        if self.length:
            s += f"\nLength: {self.length}"
        if self.uris:
            s += f"\nURIs: {', '.join(uri.__rich__() for uri in self.uris)}"

        return s

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
    def __init__(self, name: str, type: ServiceType, config_path: Path) -> None:
        self.name = name
        self.type = type
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
