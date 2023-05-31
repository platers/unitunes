from pathlib import Path
from typing import Any, List
from urllib import response
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
    BeatSaverPlaylistURI,
    BeatSaverTrackURI,
    PlaylistURI,
)


class BeatSaverSearchConfig(BaseModel):
    minNps: int = 0
    maxNps: int = 1000
    minRating: float = 0.51
    sortOrder: str = "Relevance"


class BeatSaverConfig(ServiceConfig):
    search_config: BeatSaverSearchConfig = BeatSaverSearchConfig()
    username: str = ""
    password: str = ""


class BeatSaverAPIWrapper(ServiceWrapper):
    s: requests.Session
    config: BeatSaverConfig

    def __init__(self, config, cache_root) -> None:
        super().__init__("beatsaver", cache_root=cache_root)
        self.s = requests.Session()
        self.config = config

    def login(self) -> None:
        # Check if we're already logged in
        if self.s.cookies.get("BMSESSIONID") is not None:
            return

        s = self.s
        s.post(
            "https://beatsaver.com/login",
            data={
                "username": self.config.username,
                "password": self.config.password,
            },
        )
        assert s.cookies.get("BMSESSIONID") is not None

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

    def get_playlists(self, use_cache=True) -> Any:
        self.login()
        return self.s.get("https://beatsaver.com/api/maps/id/0/playlists").json()

    def add_to_playlist(self, playlist_id: str, track_id: str) -> None:
        self.login()
        res = self.s.post(
            f"https://beatsaver.com/api/playlists/id/{playlist_id}/add",
            json={"mapId": track_id, "inPlaylist": True},
        )
        assert res.status_code == 200

    def remove_from_playlist(self, playlist_id: str, track_id: str) -> None:
        self.login()
        res = self.s.post(
            f"https://beatsaver.com/api/playlists/id/{playlist_id}/add",
            json={"mapId": track_id, "inPlaylist": False},
        )
        assert res.status_code == 200

    def get_playlist(self, playlist_id: str) -> Any:
        self.login()
        return self.s.get(
            f"https://beatsaver.com/api/playlists/id/{playlist_id}/0"
        ).json()

    def edit_playlist(
        self, playlist_id: str, name: str, description: str, public: bool = True
    ) -> None:
        self.login()
        res = self.s.post(
            f"https://beatsaver.com/api/playlists/id/{playlist_id}/edit",
            files={
                "name": (None, name),
                "description": (None, description),
            },
        )
        assert res.status_code == 200


class BeatSaverService(StreamingService):
    # Tracks are online at beatsaver.com, playlists are local .bplist files
    wrapper: BeatSaverAPIWrapper
    config: BeatSaverConfig

    def __init__(self, name: str, config: BeatSaverConfig, cache_root: Path) -> None:
        super().__init__(name, ServiceType.BEATSAVER, cache_root)
        self.wrapper = BeatSaverAPIWrapper(config, cache_root)
        self.load_config(config)

    def load_config(self, config: BeatSaverConfig) -> None:
        self.config = config

    def pull_track(self, uri: BeatSaverTrackURI) -> Track:
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
            self.pull_track(BeatSaverTrackURI.from_uri(res["id"])) for res in results
        ]

    def query_generator(self, track: Track) -> List[str]:
        return [
            f"{track.name.value} {track.artists[0].value}",
            # track.name.value,
        ]

    def get_playlist_metadatas(self) -> list[PlaylistMetadata]:
        response = self.wrapper.get_playlists()

        def parse_playlist(playlist):
            pl = playlist["playlist"]
            id = pl["playlistId"]
            uri = BeatSaverPlaylistURI.from_uri(id)
            data = self.pull_metadata(uri)
            return PlaylistMetadata(
                name=data.name,
                description=data.description,
                uri=uri,
            )

        playlists = [parse_playlist(playlist) for playlist in response]
        return playlists

    def pull_tracks(self, uri: BeatSaverPlaylistURI) -> List[Track]:
        maps = self.wrapper.get_playlist(uri.uri)["maps"]

        def parse_map(map) -> Track:
            return Track(
                name=AliasedString(map["metadata"]["songName"]),
                artists=[AliasedString(map["metadata"]["songAuthorName"])],
                length=map["metadata"]["duration"],
                uris=[BeatSaverTrackURI.from_uri(map["id"])],
            )

        return [parse_map(map["map"]) for map in maps]

    def create_playlist(
        self, title: str, description: str = ""
    ) -> BeatSaverPlaylistURI:
        raise NotImplementedError()

    def add_tracks(
        self, playlist_uri: BeatSaverPlaylistURI, tracks: List[Track]
    ) -> None:
        for track in tracks:
            uri = track.find_uri(self.type)
            assert uri is not None
            self.wrapper.add_to_playlist(playlist_uri.uri, uri.uri)

    def remove_tracks(
        self, playlist_uri: BeatSaverPlaylistURI, tracks: List[Track]
    ) -> None:
        for track in tracks:
            uri = track.find_uri(self.type)
            assert uri is not None
            self.wrapper.remove_from_playlist(playlist_uri.uri, uri.uri)

    def pull_metadata(self, uri: BeatSaverPlaylistURI) -> PlaylistDetails:
        data = self.wrapper.get_playlist(uri.uri)
        return PlaylistDetails(
            name=data["playlist"]["name"],
            description=data["playlist"]["description"],
        )

    def update_metadata(
        self, uri: BeatSaverPlaylistURI, metadata: PlaylistDetails
    ) -> None:
        self.wrapper.edit_playlist(uri.uri, metadata.name, metadata.description)
