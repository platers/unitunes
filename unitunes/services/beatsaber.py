from pathlib import Path
from typing import Any, List
from platformdirs import user_documents_dir

from pydantic import BaseModel
from unitunes.file_manager import format_filename
from unitunes.playlist import PlaylistDetails, PlaylistMetadata
import requests

from unitunes.services.services import (
    ServiceConfig,
    ServiceWrapper,
    StreamingService,
    cache,
)
from unitunes.track import AliasedString, Track
from unitunes.common_types import ServiceType
from unitunes.uri import (
    BeatsaberPlaylistURI,
    BeatsaberTrackURI,
    PlaylistURI,
)


class BeatsaberSearchConfig(BaseModel):
    minNps: int = 0
    maxNps: int = 1000
    minRating: float = 0.51
    sortOrder: str = "Relevance"


class BeatsaberConfig(ServiceConfig):
    dir: Path = Path(user_documents_dir()) / "Beatsaber"
    search_config: BeatsaberSearchConfig = BeatsaberSearchConfig()


class BeatsaverAPIWrapper(ServiceWrapper):
    def __init__(self, cache_root) -> None:
        super().__init__("beatsaber", cache_root=cache_root)

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
    playlistTitle: str = ""
    playlistAuthor: str = ""
    playlistDescription: str = ""
    image: str = ""
    songs: List[BPListSong] = []


class BeatsaberService(StreamingService):
    # Tracks are online at beatsaver.com, playlists are local .bplist files
    wrapper: BeatsaverAPIWrapper
    config: BeatsaberConfig

    def __init__(self, name: str, config: BeatsaberConfig, cache_root: Path) -> None:
        super().__init__(name, ServiceType.BEATSABER, cache_root)
        self.wrapper = BeatsaverAPIWrapper(cache_root)
        self.load_config(config)

    def load_config(self, config: BeatsaberConfig) -> None:
        self.config = config

    def pull_track(self, uri: BeatsaberTrackURI) -> Track:
        res = self.wrapper.map(uri.uri)
        track = Track(
            name=AliasedString(res["metadata"]["songName"]),
            artists=[AliasedString(res["metadata"]["songAuthorName"])],
            length=res["metadata"]["duration"],
            uris=[uri],
        )
        return track

    def search_query(self, query: str) -> List[Track]:
        results = self.wrapper.search(
            query,
            0,
            search_config=self.config.search_config.dict(),
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
        for file in self.config.dir.iterdir():
            if file.suffix == ".bplist":
                bp = BPList.parse_file(file)
                playlists.append(
                    PlaylistMetadata(
                        name=bp.playlistTitle,
                        description=bp.playlistDescription,
                        uri=BeatsaberPlaylistURI.from_uri(file.name),
                    )
                )

        return playlists

    def pull_tracks(self, uri: PlaylistURI) -> List[Track]:
        # create a new playlist if it doesn't exist
        path = self.config.dir / uri.uri
        if not path.exists():
            return []

        bp = BPList.parse_file(path)
        return [
            self.pull_track(BeatsaberTrackURI.from_uri(song.key)) for song in bp.songs
        ]

    def write_bplist(self, playlist_uri: BeatsaberPlaylistURI, bp: BPList) -> None:
        with (self.config.dir / playlist_uri.uri).open("w") as f:
            f.write(bp.json(indent=4))

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
        uri = BeatsaberPlaylistURI.from_uri(format_filename(title) + ".bplist")
        self.write_bplist(uri, bp)

        return uri

    def get_song(self, track: Track) -> BPListSong:
        uri = track.find_uri(ServiceType.BEATSABER)
        assert uri is not None
        results = self.wrapper.map(uri.uri)
        return BPListSong(
            key=results["id"],
            hash=results["versions"][0]["hash"],
            songName=results["name"],
        )

    def read_playlist(self, playlist_uri: BeatsaberPlaylistURI) -> BPList:
        path = self.config.dir / playlist_uri.uri
        if not path.exists():
            return BPList()
        return BPList.parse_file(self.config.dir / (playlist_uri.uri))

    def add_tracks(
        self, playlist_uri: BeatsaberPlaylistURI, tracks: List[Track]
    ) -> None:
        bp = self.read_playlist(playlist_uri)
        new_songs = [self.get_song(track) for track in tracks]
        bp.songs.extend(new_songs)
        self.write_bplist(playlist_uri, bp)

    def remove_tracks(
        self, playlist_uri: BeatsaberPlaylistURI, tracks: List[Track]
    ) -> None:
        bp = self.read_playlist(playlist_uri)
        removed_songs = [self.get_song(track) for track in tracks]
        bp.songs = [
            song for song in bp.songs if song.key not in [s.key for s in removed_songs]
        ]
        self.write_bplist(playlist_uri, bp)

    def pull_metadata(self, uri: BeatsaberPlaylistURI) -> PlaylistDetails:
        bp = self.read_playlist(uri)
        return PlaylistDetails(
            name=bp.playlistTitle,
            description=bp.playlistDescription,
        )

    def update_metadata(
        self, uri: BeatsaberPlaylistURI, metadata: PlaylistDetails
    ) -> None:
        bp = self.read_playlist(uri)
        bp.playlistTitle = metadata.name
        bp.playlistDescription = metadata.description
        self.write_bplist(uri, bp)
