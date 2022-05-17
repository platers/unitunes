from abc import ABC, abstractmethod
from typing import Literal, Union
from pydantic import BaseModel
from pydantic.validators import dict_validator
from unitunes.types import EntityType, ServiceType


class URIBase(BaseModel, ABC):
    service: Literal[ServiceType.SPOTIFY, ServiceType.YTM, ServiceType.MB]
    type: Literal[EntityType.TRACK, EntityType.PLAYLIST, EntityType.ALBUM]
    uri: str
    url: str

    class Config:
        frozen = True

    @staticmethod
    @abstractmethod
    def uri_to_url(uri: str) -> str:
        """
        Returns a clickable URL for the URI.
        """

    @staticmethod
    @abstractmethod
    def url_to_uri(url: str) -> str:
        """
        Returns the URI corresponding to a URL.
        """

    def __rich__(self) -> str:
        return f"[link={self.url}]{self.url}[/link]"

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
    type: Literal[EntityType.TRACK] = EntityType.TRACK


class PlaylistURI(URIBase):
    type: Literal[EntityType.PLAYLIST] = EntityType.PLAYLIST


class AlbumURI(URIBase):
    type: Literal[EntityType.ALBUM] = EntityType.ALBUM


class SpotifyTrackURI(TrackURI):
    service: Literal[ServiceType.SPOTIFY] = ServiceType.SPOTIFY

    @classmethod
    def from_uri(cls, uri: str) -> "SpotifyTrackURI":
        return cls(uri=uri, url=cls.uri_to_url(uri))

    @staticmethod
    def uri_to_url(uri: str) -> str:
        return f"https://open.spotify.com/track/{uri}"

    @staticmethod
    def url_to_uri(url: str) -> str:
        return url.split("/")[-1]

    @staticmethod
    def valid_url(url: str) -> bool:
        return url.startswith("https://open.spotify.com/track/")

    @staticmethod
    def from_url(url: str) -> "SpotifyTrackURI":
        return SpotifyTrackURI.from_uri(SpotifyTrackURI.url_to_uri(url))


class SpotifyPlaylistURI(PlaylistURI):
    service: Literal[ServiceType.SPOTIFY] = ServiceType.SPOTIFY

    @classmethod
    def from_uri(cls, uri: str) -> "SpotifyPlaylistURI":
        return cls(uri=uri, url=cls.uri_to_url(uri))

    def is_liked_songs(self) -> bool:
        return self.uri == "Liked Songs"

    @staticmethod
    def uri_to_url(uri: str) -> str:
        if uri == "Liked Songs":
            return f"spotify:liked_songs"
        return f"https://open.spotify.com/playlist/{uri}"

    @staticmethod
    def url_to_uri(url: str) -> str:
        if url == "spotify:liked_songs":
            return "Liked Songs"
        return url.split("/")[-1]

    @staticmethod
    def valid_url(url: str) -> bool:
        return (
            url.startswith("https://open.spotify.com/playlist/")
            or url == "spotify:liked_songs"
        )

    @staticmethod
    def from_url(url: str) -> "SpotifyPlaylistURI":
        return SpotifyPlaylistURI.from_uri(SpotifyPlaylistURI.url_to_uri(url))


class YtmTrackURI(TrackURI):
    service: Literal[ServiceType.YTM] = ServiceType.YTM

    @classmethod
    def from_uri(cls, uri: str) -> "YtmTrackURI":
        return cls(uri=uri, url=cls.uri_to_url(uri))

    @staticmethod
    def url_to_uri(url: str) -> str:
        return url.split("=")[-1]

    @staticmethod
    def uri_to_url(uri: str) -> str:
        return f"https://music.youtube.com/watch?v={uri}"

    @staticmethod
    def valid_url(url: str) -> bool:
        return url.startswith("https://music.youtube.com/watch?v=")

    @staticmethod
    def from_url(url: str) -> "YtmTrackURI":
        return YtmTrackURI.from_uri(YtmTrackURI.url_to_uri(url))


class YtmPlaylistURI(PlaylistURI):
    service: Literal[ServiceType.YTM] = ServiceType.YTM

    @classmethod
    def from_uri(cls, uri: str) -> "YtmPlaylistURI":
        return cls(uri=uri, url=cls.uri_to_url(uri))

    @staticmethod
    def url_to_uri(url: str) -> str:
        return url.split("=")[-1]

    @staticmethod
    def uri_to_url(uri: str) -> str:
        return f"https://music.youtube.com/playlist?list={uri}"

    @staticmethod
    def valid_url(url: str) -> bool:
        return url.startswith("https://music.youtube.com/playlist?list=")

    @staticmethod
    def from_url(url: str) -> "YtmPlaylistURI":
        return YtmPlaylistURI.from_uri(YtmPlaylistURI.url_to_uri(url))


class MB_RECORDING_URI(TrackURI):
    service: Literal[ServiceType.MB] = ServiceType.MB

    @classmethod
    def from_uri(cls, uri: str) -> "MB_RECORDING_URI":
        return cls(uri=uri, url=cls.uri_to_url(uri))

    @staticmethod
    def uri_to_url(uri: str) -> str:
        return f"https://musicbrainz.org/recording/{uri}"

    @staticmethod
    def url_to_uri(url: str) -> str:
        return url.split("/")[-1]

    @staticmethod
    def valid_url(url: str) -> bool:
        return url.startswith("https://musicbrainz.org/recording/")

    @staticmethod
    def from_url(url: str) -> "MB_RECORDING_URI":
        return MB_RECORDING_URI.from_uri(MB_RECORDING_URI.url_to_uri(url))


class MB_RELEASE_URI(AlbumURI):
    service: Literal[ServiceType.MB] = ServiceType.MB

    @classmethod
    def from_uri(cls, uri: str) -> "MB_RELEASE_URI":
        return cls(uri=uri, url=cls.uri_to_url(uri))

    @staticmethod
    def uri_to_url(uri: str) -> str:
        return f"https://musicbrainz.org/release/{uri}"

    @staticmethod
    def url_to_uri(url: str) -> str:
        return url.split("/")[-1]

    @staticmethod
    def valid_url(url: str) -> bool:
        return url.startswith("https://musicbrainz.org/release/")

    @staticmethod
    def from_url(url: str) -> "MB_RELEASE_URI":
        return MB_RELEASE_URI.from_uri(MB_RELEASE_URI.url_to_uri(url))


TrackURIs = Union[SpotifyTrackURI, YtmTrackURI, MB_RECORDING_URI]
PlaylistURIs = Union[SpotifyPlaylistURI, YtmPlaylistURI]
AlbumURIs = MB_RELEASE_URI

playlist_uri_types = [SpotifyPlaylistURI, YtmPlaylistURI]
track_uri_types = [SpotifyTrackURI, YtmTrackURI, MB_RECORDING_URI]
album_uri_types = [MB_RELEASE_URI]
all_uri_types = [..., *playlist_uri_types, *track_uri_types, *album_uri_types]

URI = Union[
    TrackURIs,
    PlaylistURIs,
    AlbumURIs,
]


def URI_Builder(service: ServiceType, type: EntityType, uri: str) -> URI:
    if service == ServiceType.SPOTIFY:
        if type == EntityType.TRACK:
            return SpotifyTrackURI.from_uri(uri)
        elif type == EntityType.PLAYLIST:
            return SpotifyPlaylistURI.from_uri(uri)
    elif service == ServiceType.YTM:
        if type == EntityType.TRACK:
            return YtmTrackURI.from_uri(uri)
        elif type == EntityType.PLAYLIST:
            return YtmPlaylistURI.from_uri(uri)
    elif service == ServiceType.MB:
        if type == EntityType.TRACK:
            return MB_RECORDING_URI.from_uri(uri)
        elif type == EntityType.ALBUM:
            return MB_RELEASE_URI.from_uri(uri)
    else:
        raise ValueError(f"Unknown service type {service}")

    raise ValueError(f"Unknown entity type {type} for service {service}")


def playlistURI_from_url(url: str) -> PlaylistURIs:
    for cls in playlist_uri_types:
        if cls.valid_url(url):
            return cls.from_url(url)

    raise ValueError(f"Unknown URL format {url}")


def trackURI_from_url(url: str) -> TrackURIs:
    for cls in track_uri_types:
        if cls.valid_url(url):
            return cls.from_url(url)

    raise ValueError(f"Unknown URL format {url}")


def albumURI_from_url(url: str) -> AlbumURIs:
    for cls in album_uri_types:
        if cls.valid_url(url):
            return cls.from_url(url)

    raise ValueError(f"Unknown URL format {url}")


def URI_from_url(url: str) -> URI:
    for cls in all_uri_types:
        if cls.valid_url(url):
            return cls.from_url(url)

    raise ValueError(f"Unknown URL format {url}")
