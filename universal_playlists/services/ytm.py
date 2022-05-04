from pathlib import Path
from typing import List
from ytmusicapi import YTMusic
from universal_playlists.playlist import PlaylistMetadata


from universal_playlists.services.services import (
    ServiceWrapper,
    StreamingService,
    cache,
)
from universal_playlists.track import AliasedString, Track
from universal_playlists.types import ServiceType
from universal_playlists.uri import YtmPlaylistURI, YtmTrackURI


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
        super().__init__(name, ServiceType.YTM, config_path=config_path)
        self.ytm = YtmWrapper(config_path)

    def get_playlist_metadatas(self) -> list[PlaylistMetadata]:
        results = self.ytm.ytm.get_library_playlists()

        def playlistFromResponse(response):
            return PlaylistMetadata(
                name=response["title"],
                description=response["description"],
                uri=YtmPlaylistURI.from_uri(response["playlistId"]),
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

    def pull_tracks(self, uri: YtmTrackURI) -> List[Track]:
        tracks = self.ytm.get_playlist(uri.uri)["tracks"]
        return self.results_to_tracks(tracks)

    def raw_to_track(self, raw: dict) -> Track:
        if "videoDetails" in raw:
            details = raw["videoDetails"]
            return Track(
                name=details["title"],
                artists=[details["author"]],
                length=details["lengthSeconds"],
                uris=[YtmTrackURI.from_uri(details["videoId"])],
            )

        return Track(
            name=AliasedString(raw["title"]),
            artists=[AliasedString(value=artist["name"]) for artist in raw["artists"]],
            albums=[AliasedString(value=raw["album"]["name"])]
            if "album" in raw and raw["album"]
            else [],
            length=raw["duration_seconds"] if "duration_seconds" in raw else None,
            uris=[YtmTrackURI.from_uri(raw["videoId"])],
        )

    def pull_track(self, uri: YtmTrackURI) -> Track:
        track = self.ytm.get_song(uri.uri)
        return self.raw_to_track(track)

    def search_track(self, track: Track) -> List[Track]:
        query = f"{track.name} - {' '.join([artist.value for artist in track.artists])}"
        results = self.ytm.search(query)
        return self.results_to_tracks(results)
