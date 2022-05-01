from enum import Enum
from pathlib import Path
import shelve
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    NewType,
    Optional,
    TypedDict,
    Union,
)
from pydantic import BaseModel
from strsimpy.jaro_winkler import JaroWinkler
from pydantic.validators import dict_validator
from abc import ABC, abstractmethod
from rich import print


def pairwise_max(a: List[Any], b: List[Any], f: Callable[[Any, Any], float]) -> float:
    mx = 0
    for i in a:
        for j in b:
            mx = max(mx, f(i, j))
    return mx


def normalized_string_similarity(s1: str, s2: str) -> float:
    jw = JaroWinkler().similarity(s1.lower(), s2.lower())
    # convert to [-1, 1]
    return (jw - 0.5) * 2


class AliasedString(BaseModel):
    value: str
    aliases: List[str] = []

    def __init__(self, value: str, aliases: List[str] = []):
        super().__init__(value=value, aliases=aliases)
        # remove duplicates
        self.aliases = list(set(self.aliases))
        if self.value in self.aliases:
            self.aliases.remove(self.value)

    def __rich__(self):
        s = self.value
        if self.aliases:
            s += f" ({', '.join(self.aliases)})"
        return s

    def all_values(self) -> List[str]:
        return [self.value] + self.aliases

    def pairwise_max_similarity(self, other: "AliasedString") -> float:
        return pairwise_max(
            self.all_values(), other.all_values(), normalized_string_similarity
        )


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
        """
        Returns a clickable URL for the URI.
        """

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


class TrackURI(URIBase):
    pass


class PlaylistURI(URIBase):
    pass


class AlbumURI(URIBase):
    pass


class SpotifyTrackURI(TrackURI):
    type: Literal["spotify_track"] = "spotify_track"

    def __init__(self, *uri, **kwargs):
        if len(uri) == 1:
            kwargs["uri"] = uri[0]
        kwargs["service"] = ServiceType.SPOTIFY.value
        super().__init__(**kwargs)

    def url(self) -> str:
        return f"https://open.spotify.com/track/{self.uri}"

    @staticmethod
    def url_to_uri(url: str) -> str:
        return url.split("/")[-1]

    @staticmethod
    def from_url(url: str) -> "SpotifyTrackURI":
        return SpotifyTrackURI(SpotifyTrackURI.url_to_uri(url))


class SpotifyPlaylistURI(PlaylistURI):
    type: Literal["spotify_playlist"] = "spotify_playlist"

    def __init__(self, *uri, **kwargs):
        if len(uri) == 1:
            kwargs["uri"] = uri[0]
        kwargs["service"] = ServiceType.SPOTIFY.value
        super().__init__(**kwargs)

    def url(self) -> str:
        return f"https://open.spotify.com/playlist/{self.uri}"

    @staticmethod
    def url_to_uri(url: str) -> str:
        return url.split("/")[-1]

    @staticmethod
    def from_url(url: str) -> "SpotifyPlaylistURI":
        return SpotifyPlaylistURI(uri=SpotifyPlaylistURI.url_to_uri(url))


class YtmTrackURI(TrackURI):
    type: Literal["ytm_track"] = "ytm_track"

    def __init__(self, *uri, **kwargs):
        if len(uri) == 1:
            kwargs["uri"] = uri[0]
        kwargs["service"] = ServiceType.YTM.value
        super().__init__(**kwargs)

    @staticmethod
    def url_to_uri(url: str) -> str:
        return url.split("=")[-1]

    def url(self) -> str:
        return f"https://music.youtube.com/watch?v={self.uri}"


class YtmPlaylistURI(PlaylistURI):
    type: Literal["ytm_playlist"] = "ytm_playlist"

    def __init__(self, *uri, **kwargs):
        if len(uri) == 1:
            kwargs["uri"] = uri[0]
        kwargs["service"] = ServiceType.YTM.value
        super().__init__(**kwargs)

    def url(self) -> str:
        return f"https://music.youtube.com/playlist?list={self.uri}"

    @staticmethod
    def url_to_uri(url: str) -> str:
        return url.split("=")[-1]

    @staticmethod
    def from_url(url: str) -> "YtmPlaylistURI":
        return YtmPlaylistURI(uri=YtmPlaylistURI.url_to_uri(url))


class MB_RECORDING_URI(TrackURI):
    type: Literal["mb_recording"] = "mb_recording"

    def __init__(self, *uri, **kwargs):
        if len(uri) == 1:
            kwargs["uri"] = uri[0]
        kwargs["service"] = ServiceType.MB.value
        super().__init__(**kwargs)

    def url(self) -> str:
        return f"https://musicbrainz.org/recording/{self.uri}"


class MB_RELEASE_URI(AlbumURI):
    type: Literal["mb_release"] = "mb_release"

    def __init__(self, *uri, **kwargs):
        if len(uri) == 1:
            kwargs["uri"] = uri[0]
        kwargs["service"] = ServiceType.MB.value
        super().__init__(**kwargs)

    def url(self) -> str:
        return f"https://musicbrainz.org/release/{self.uri}"


URI = Union[
    SpotifyTrackURI,
    SpotifyPlaylistURI,
    YtmTrackURI,
    YtmPlaylistURI,
    MB_RECORDING_URI,
    MB_RELEASE_URI,
]
TrackURIs = Union[SpotifyTrackURI, YtmTrackURI, MB_RECORDING_URI]
PlaylistURIs = Union[SpotifyPlaylistURI, YtmPlaylistURI]


def artists_similarity(
    artists1: List[AliasedString], artists2: List[AliasedString]
) -> float:
    if len(artists1) == 0 or len(artists2) == 0:
        return 0

    sim = pairwise_max(artists1, artists2, lambda a, b: a.pairwise_max_similarity(b))
    return sim


def album_similarity(album1: List[AliasedString], album2: List[AliasedString]) -> float:
    sim = pairwise_max(album1, album2, lambda a, b: a.pairwise_max_similarity(b))
    if sim < 0:
        sim /= 5

    return sim


def length_similarity(length_sec_1: int, length_sec_2: int) -> float:
    d = abs(length_sec_1 - length_sec_2)
    max_dist = 4
    if d > max_dist:
        return -1
    return 1 - d / max_dist


class Track(BaseModel):
    name: AliasedString
    albums: List[AliasedString] = []
    artists: List[AliasedString] = []
    length: Optional[int] = None
    uris: List[TrackURIs] = []

    def __rich__(self):
        s = f"[b]{self.name.__rich__()}[/b]"
        if self.artists:
            s += f"\nArtists: {', '.join(a.__rich__() for a in self.artists)}"
        if self.albums:
            s += f"\nAlbums: {', '.join([a.__rich__() for a in self.albums])}"
        if self.length:
            s += f"\nLength: {self.length}"
        if self.uris:
            s += f"\nURIs: {', '.join(uri.__rich__() for uri in self.uris)}"

        return s

    def similarity(self, other: "Track", verbose=False) -> float:
        # check if any URI in track matches any URI in self
        for uri in self.uris:
            if uri in other.uris:
                return 1

        weights = {
            "name": 50,
            "album": 20,
            "artists": 30,
            "length": 20,
        }

        feature_scores: Dict[str, float] = {}

        if self.name and other.name:
            feature_scores["name"] = self.name.pairwise_max_similarity(other.name)

        if self.artists and other.artists:
            feature_scores["artists"] = artists_similarity(self.artists, other.artists)

        if self.albums and other.albums:
            feature_scores["album"] = album_similarity(self.albums, other.albums)

        if self.length and other.length:
            feature_scores["length"] = length_similarity(self.length, other.length)

        if verbose:
            print(f"{self.name} vs {other.name}")
            print(other)
            print(feature_scores)

        used_features = feature_scores.keys()
        if not used_features:
            return 0

        weighted_sum = sum(
            feature_scores[feature] * weights[feature] for feature in used_features
        )
        total_weight = sum(weights[feature] for feature in used_features)

        similarity = weighted_sum / total_weight
        assert -1 <= similarity <= 1
        return similarity

    def matches(self, track: "Track", threshold: float = 0.8) -> bool:
        return self.similarity(track) > threshold

    def merge(self, other: "Track") -> None:
        for uri in other.uris:
            if uri not in self.uris:
                self.uris.append(uri)

        # TODO: merge other fields


class PlaylistMetadata(TypedDict):
    name: str
    description: str
    uri: PlaylistURIs


class Playlist(BaseModel):
    name: str
    description: str = ""
    uris: List[PlaylistURIs] = []
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
        raise ValueError(
            f"Playlist {playlist_name} not found in {self.name}. Available playlists: {', '.join([meta['name'] for meta in metas])}"
        )

    def pull_tracks(self, uri: PlaylistURI) -> List[Track]:
        raise NotImplementedError

    def pull_track(self, uri: TrackURI) -> Track:
        raise NotImplementedError

    def search_track(self, track: Track) -> List[Track]:
        """Search for a track in the streaming service. Returns a list of potential matches."""
        raise NotImplementedError
