from abc import ABC, abstractmethod
from typing import Literal, Union
from pydantic import BaseModel
from pydantic.validators import dict_validator
from universal_playlists.types import EntityType, ServiceType


class URIBase(BaseModel, ABC):
    service: Literal[ServiceType.SPOTIFY, ServiceType.YTM, ServiceType.MB]
    type: Literal[EntityType.TRACK, EntityType.PLAYLIST, EntityType.ALBUM]
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
    type: Literal[EntityType.TRACK] = EntityType.TRACK


class PlaylistURI(URIBase):
    type: Literal[EntityType.PLAYLIST] = EntityType.PLAYLIST


class AlbumURI(URIBase):
    type: Literal[EntityType.ALBUM] = EntityType.ALBUM


class SpotifyTrackURI(TrackURI):
    service: Literal[ServiceType.SPOTIFY] = ServiceType.SPOTIFY

    def url(self) -> str:
        return f"https://open.spotify.com/track/{self.uri}"

    @staticmethod
    def url_to_uri(url: str) -> str:
        return url.split("/")[-1]

    @staticmethod
    def from_url(url: str) -> "SpotifyTrackURI":
        return SpotifyTrackURI(uri=SpotifyTrackURI.url_to_uri(url))


class SpotifyPlaylistURI(PlaylistURI):
    service: Literal[ServiceType.SPOTIFY] = ServiceType.SPOTIFY

    def url(self) -> str:
        return f"https://open.spotify.com/playlist/{self.uri}"

    @staticmethod
    def url_to_uri(url: str) -> str:
        return url.split("/")[-1]

    @staticmethod
    def from_url(url: str) -> "SpotifyPlaylistURI":
        return SpotifyPlaylistURI(uri=SpotifyPlaylistURI.url_to_uri(url))


class YtmTrackURI(TrackURI):
    service: Literal[ServiceType.YTM] = ServiceType.YTM

    @staticmethod
    def url_to_uri(url: str) -> str:
        return url.split("=")[-1]

    def url(self) -> str:
        return f"https://music.youtube.com/watch?v={self.uri}"


class YtmPlaylistURI(PlaylistURI):
    service: Literal[ServiceType.YTM] = ServiceType.YTM

    def url(self) -> str:
        return f"https://music.youtube.com/playlist?list={self.uri}"

    @staticmethod
    def url_to_uri(url: str) -> str:
        return url.split("=")[-1]

    @staticmethod
    def from_url(url: str) -> "YtmPlaylistURI":
        return YtmPlaylistURI(uri=YtmPlaylistURI.url_to_uri(url))


class MB_RECORDING_URI(TrackURI):
    service: Literal[ServiceType.MB] = ServiceType.MB

    def url(self) -> str:
        return f"https://musicbrainz.org/recording/{self.uri}"


class MB_RELEASE_URI(AlbumURI):
    service: Literal[ServiceType.MB] = ServiceType.MB

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


def URI_Builder(service: ServiceType, type: EntityType, uri: str) -> URI:
    if service == ServiceType.SPOTIFY:
        if type == EntityType.TRACK:
            return SpotifyTrackURI(uri=uri)
        elif type == EntityType.PLAYLIST:
            return SpotifyPlaylistURI(uri=uri)
    elif service == ServiceType.YTM:
        if type == EntityType.TRACK:
            return YtmTrackURI(uri=uri)
        elif type == EntityType.PLAYLIST:
            return YtmPlaylistURI(uri=uri)
    elif service == ServiceType.MB:
        if type == EntityType.TRACK:
            return MB_RECORDING_URI(uri=uri)
        elif type == EntityType.ALBUM:
            return MB_RELEASE_URI(uri=uri)
    else:
        raise ValueError(f"Unknown service type {service}")

    raise ValueError(f"Unknown entity type {type} for service {service}")
