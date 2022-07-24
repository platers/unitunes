from abc import ABC, abstractmethod
from typing import Any, List
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
    BeatsaberTrackURI,
    PlaylistURI,
    PlaylistURIs,
    TrackURI,
)


class BeatsaverAPIWrapper(ServiceWrapper):
    search_config = {}

    def __init__(self, config, cache_root) -> None:
        super().__init__("beatsaver", cache_root=cache_root)
        if config is not None and "search_config" in config:
            self.search_config = config["search_config"]

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


class BeatsaberService(StreamingService):
    # Tracks are online at beatsaver.com, playlists are local .bplist files
    wrapper: BeatsaverAPIWrapper

    def __init__(self, name: str, wrapper: BeatsaverAPIWrapper) -> None:
        super().__init__(name, ServiceType.BEATSABER)
        self.wrapper = wrapper

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
            search_config=self.wrapper.search_config,
        )
        return [
            self.pull_track(BeatsaberTrackURI.from_uri(res["id"])) for res in results
        ]

    def query_generator(self, track: Track) -> List[str]:
        return [
            f"{track.name.value} {track.artists[0].value}",
            # track.name.value,
        ]
