from enum import Enum
import json
from pathlib import Path
import shelve
from typing import List, Optional, TypedDict
from ytmusicapi import YTMusic
from pydantic import BaseModel


class ServiceType(Enum):
    SPOTIFY = "spotify"
    YTM = "youtube-music"
    MB = "musicbrainz"


class URI(BaseModel):
    service: str
    uri: str

    class Config:
        frozen = True


class YtmURI(URI):
    def __init__(self, uri: str):
        super().__init__(service=ServiceType.YTM.value, uri=uri)


class Track(BaseModel):
    name: str
    album: Optional[str] = None
    album_position: Optional[int] = None
    artists: List[str] = []
    uris: List[URI] = []

    def matches(self, track: "Track") -> bool:
        # check if any URI in track matches any URI in self
        for uri in track.uris:
            if uri in self.uris:
                return True

        if self.name == track.name:
            # check if any artist in track matches any artist in self
            for artist in track.artists:
                if artist in self.artists:
                    return True

        return False


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


class YTM(StreamingService):
    def __init__(self, name: str, config_path: Path) -> None:
        super().__init__(name, config_path)
        self.ytm = YTMusic(config_path.__str__())

    def get_playlist_metadatas(self) -> list[PlaylistMetadata]:
        results = self.ytm.get_library_playlists()

        def playlistFromResponse(response):
            return PlaylistMetadata(
                name=response["title"],
                description=response["description"],
                uri=YtmURI(response["playlistId"]),
            )

        playlists = list(map(playlistFromResponse, results))
        return playlists

    def pull_tracks(self, uri: YtmURI) -> List[Track]:
        tracks = self.ytm.get_playlist(uri.uri)["tracks"]
        tracks = filter(lambda x: x["videoId"] is not None, tracks)
        tracks = list(
            map(
                lambda x: Track(
                    name=x["title"],
                    artists=[artist["name"] for artist in x["artists"]],
                    uris=[YtmURI(x["videoId"])],
                ),
                tracks,
            )
        )
        return tracks

    def pull_track(self, uri: YtmURI) -> Track:
        track = self.ytm.get_song(uri.uri)
        return Track(
            name=track["title"],
            artists=[artist["name"] for artist in track["artists"]],
            uris=[YtmURI(track["videoId"])],
        )
