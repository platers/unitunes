import json
from pathlib import Path
from typing import List
from ytmusicapi import YTMusic

from universal_playlists.services.services import (
    URI,
    PlaylistMetadata,
    ServiceType,
    ServiceWrapper,
    StreamingService,
    Track,
    cache,
)


class YtmURI(URI):
    def __init__(self, uri: str):
        super().__init__(service=ServiceType.YTM.value, uri=uri)

    def url(self) -> str:
        return f"https://music.youtube.com/watch?v={self.uri}"


class YtmWrapper(ServiceWrapper):
    def __init__(self, config_path: Path) -> None:
        super().__init__("ytm")
        self.ytm = YTMusic(config_path.__str__())

    @cache
    def get_playlist(self, *args, use_cache=True, **kwargs):
        return self.ytm.get_playlist(*args, **kwargs)

    @cache
    def get_song(self, *args, use_cache=True, **kwargs):
        return self.ytm.get_song(*args, **kwargs)

    @cache
    def search(self, *args, use_cache=True, **kwargs):
        return self.ytm.search(*args, **kwargs)


class YTM(StreamingService):
    def __init__(self, name: str, config_path: Path) -> None:
        super().__init__(name, config_path)
        self.ytm = YtmWrapper(config_path)

    def get_playlist_metadatas(self) -> list[PlaylistMetadata]:
        results = self.ytm.ytm.get_library_playlists()

        def playlistFromResponse(response):
            return PlaylistMetadata(
                name=response["title"],
                description=response["description"],
                uri=YtmURI(response["playlistId"]),
            )

        playlists = list(map(playlistFromResponse, results))
        return playlists

    def results_to_tracks(self, results: list[dict]) -> List[Track]:
        songs = filter(lambda x: "videoId" in x or "videoDetails" in x, results)
        return list(
            map(
                self.raw_to_track,
                songs,
            )
        )

    def pull_tracks(self, uri: YtmURI) -> List[Track]:
        tracks = self.ytm.get_playlist(uri.uri)["tracks"]
        return self.results_to_tracks(tracks)

    def raw_to_track(self, raw: dict) -> Track:
        if "videoDetails" in raw:
            details = raw["videoDetails"]
            return Track(
                name=details["title"],
                artists=[details["author"]],
                uris=[YtmURI(details["videoId"])],
            )

        return Track(
            name=raw["title"],
            artists=[artist["name"] for artist in raw["artists"]],
            uris=[YtmURI(raw["videoId"])],
        )

    def pull_track(self, uri: YtmURI) -> Track:
        track = self.ytm.get_song(uri.uri)
        return self.raw_to_track(track)

    def search_track(self, track: Track) -> List[Track]:
        query = f"{track.name} - {' '.join(track.artists)}"
        results = self.ytm.search(query)
        return self.results_to_tracks(results)
