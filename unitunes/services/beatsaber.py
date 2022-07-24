from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List

from pydantic import BaseModel
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
    BeatsaberPlaylistURI,
    BeatsaberTrackURI,
    PlaylistURI,
    PlaylistURIs,
    TrackURI,
)


class BeatsaverAPIWrapper(ServiceWrapper):
    def __init__(self, config, cache_root) -> None:
        super().__init__("beatsaver", cache_root=cache_root)

    @cache
    def map(self, id: str, use_cache=True) -> Any:
        return requests.get(f"https://api.beatsaver.com/maps/id/{id}").json()

    @cache
    def search(
        self, query: str, page: int, search_config={}, use_cache=True, **kwargs
    ) -> Any:
        params = search_config.copy()
        params["q"] = query
        return requests.get(
            f"https://api.beatsaver.com/search/text/{page}",
            params=params,
        ).json()["docs"]


class BPListSong(BaseModel):
    key: str
    hash: str
    songName: str


class BPList(BaseModel):
    playlistTitle: str
    playlistAuthor: str
    playlistDescription: str
    image: str
    songs: List[BPListSong]


class BeatsaberService(StreamingService):
    # Tracks are online at beatsaver.com, playlists are local .bplist files
    wrapper: BeatsaverAPIWrapper
    search_config = {}
    dir: Path

    def __init__(self, name: str, wrapper: BeatsaverAPIWrapper, config) -> None:
        super().__init__(name, ServiceType.BEATSABER)
        self.wrapper = wrapper

        if "dir" not in config:
            raise ValueError("No beatsaber directory specified")
        self.dir = Path(config["dir"])

        if "search_config" in config:
            self.search_config = config["search_config"]

    def pull_track(self, uri: BeatsaberTrackURI) -> Track:
        res = self.wrapper.map(uri.uri)
        track = Track(
            name=AliasedString(res["metadata"]["songName"]),
            artists=[AliasedString(res["metadata"]["songAuthorName"])],
            length=res["metadata"]["duration"],
        )
        return track

    def search_query(self, query: str) -> List[Track]:
        results = self.wrapper.search(
            query,
            0,
            search_config=self.search_config,
        )
        return [
            self.pull_track(BeatsaberTrackURI.from_uri(res["id"])) for res in results
        ]

    def query_generator(self, track: Track) -> List[str]:
        return [
            f"{track.name.value} {track.artists[0].value}",
            # track.name.value,
        ]

    def get_playlist_metadatas(self) -> list[PlaylistMetadata]:
        # find .bplist files in the beatsaber directory
        playlists = []
        for file in self.dir.iterdir():
            if file.suffix == ".bplist":
                bp = BPList.parse_file(file)
                playlists.append(
                    PlaylistMetadata(
                        name=bp.playlistTitle,
                        description=bp.playlistDescription,
                        uri=BeatsaberPlaylistURI.from_uri(file.stem),
                    )
                )

        return playlists

    def pull_tracks(self, uri: PlaylistURI) -> List[Track]:
        bp = BPList.parse_file(self.dir / (uri.uri + ".bplist"))
        return [
            self.pull_track(BeatsaberTrackURI.from_uri(song.key)) for song in bp.songs
        ]

    def write_bplist(self, playlist_uri: PlaylistURI, bp: BPList) -> None:
        with (self.dir / (playlist_uri.uri + ".bplist")).open("w") as f:
            f.write(bp.json(indent=4))

    def read_playlist(self, playlist_uri: PlaylistURI) -> BPList:
        return BPList.parse_file(self.dir / (playlist_uri.uri + ".bplist"))

    def create_playlist(
        self, title: str, description: str = ""
    ) -> BeatsaberPlaylistURI:
        bp = BPList(
            playlistTitle=title,
            playlistAuthor="",
            playlistDescription=description,
            image="",
            songs=[],
        )
        self.write_bplist(BeatsaberPlaylistURI.from_uri(title), bp)

        return BeatsaberPlaylistURI.from_uri(title)

    def get_song(self, track: Track) -> BPListSong:
        uri = track.find_uri(ServiceType.BEATSABER)
        assert uri is not None
        results = self.wrapper.map(uri.uri)
        return BPListSong(
            key=results["id"],
            hash=results["versions"][0]["hash"],
            songName=results["name"],
        )

    def add_tracks(
        self, playlist_uri: BeatsaberPlaylistURI, tracks: List[Track]
    ) -> None:
        bp = self.read_playlist(playlist_uri)
        new_songs = [self.get_song(track) for track in tracks]
        bp.songs.extend(new_songs)
        self.write_bplist(playlist_uri, bp)

    def remove_tracks(self, playlist_uri: PlaylistURI, tracks: List[Track]) -> None:
        bp = self.read_playlist(playlist_uri)
        removed_songs = [self.get_song(track) for track in tracks]
        bp.songs = [
            song for song in bp.songs if song.key not in [s.key for s in removed_songs]
        ]
        self.write_bplist(playlist_uri, bp)
