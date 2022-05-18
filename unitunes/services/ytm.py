from abc import ABC, abstractmethod
from pathlib import Path
import time
from typing import Any, List, Optional
from tqdm import tqdm
from ytmusicapi import YTMusic
from unitunes.playlist import PlaylistMetadata
from youtube_title_parse import get_artist_title


from unitunes.services.services import (
    Pushable,
    Searchable,
    ServiceWrapper,
    StreamingService,
    TrackPullable,
    UserPlaylistPullable,
    cache,
)
from unitunes.track import (
    AliasedString,
    Track,
)
from unitunes.types import ServiceType
from unitunes.uri import (
    PlaylistURI,
    PlaylistURIs,
    YtmPlaylistURI,
    YtmTrackURI,
)


class YtmWrapper(ServiceWrapper, ABC):
    @abstractmethod
    def get_playlist(self, *args, **kwargs) -> Any:
        pass

    @abstractmethod
    def get_song(self, *args, use_cache=True, **kwargs) -> Any:
        pass

    @abstractmethod
    def search(self, *args, use_cache=True, **kwargs) -> Any:
        pass

    @abstractmethod
    def create_playlist(self, title: str, description: str = "") -> str:
        pass

    @abstractmethod
    def edit_title(self, playlist_id: str, title: str) -> None:
        pass

    @abstractmethod
    def edit_description(self, playlist_id: str, description: str) -> None:
        pass

    @abstractmethod
    def add_tracks(self, playlist_id: str, track_ids: List[str]) -> None:
        """Add tracks to a playlist."""

    @abstractmethod
    def remove_tracks(self, playlist_id: str, track_ids: List[str]) -> None:
        """Remove tracks from a playlist."""

    @abstractmethod
    def get_library_playlists(self, *args, **kwargs) -> Any:
        pass


class YtmAPIWrapper(YtmWrapper):
    def __init__(self, config_path: Path, cache_root: Path) -> None:
        super().__init__("ytm", cache_root=cache_root)
        self.ytm = YTMusic(config_path.__str__())

    def get_playlist(self, *args, **kwargs):
        kwargs["limit"] = 100000  # probably no playlist this big
        return self.ytm.get_playlist(*args, **kwargs)

    @cache
    def get_song(self, *args, use_cache=True, **kwargs):
        return self.ytm.get_song(*args, **kwargs)

    @cache
    def search(self, *args, use_cache=True, **kwargs):
        return self.ytm.search(*args, **kwargs)

    def create_playlist(self, title: str, description: str = "") -> str:
        id = self.ytm.create_playlist(title, description)
        assert isinstance(id, str)
        return id

    def edit_title(self, playlist_id: str, title: str) -> None:
        self.ytm.edit_playlist(playlist_id, title=title)

    def edit_description(self, playlist_id: str, description: str) -> None:
        self.ytm.edit_playlist(playlist_id, description=description)

    def add_tracks(self, playlist_id: str, track_ids: List[str]) -> None:
        """Add tracks to a playlist."""
        if playlist_id == "LM":
            for track_id in tqdm(track_ids, desc="Rating songs"):
                self.ytm.rate_song(track_id, "LIKE")
                time.sleep(0.8)

        else:
            self.ytm.add_playlist_items(playlist_id, track_ids)

    def remove_tracks(self, playlist_id: str, track_ids: List[str]) -> None:
        """Remove tracks from a playlist."""

        if playlist_id == "LM":
            for track_id in tqdm(track_ids, desc="Unrating songs"):
                self.ytm.rate_song(track_id, "INDIFFERENT")
                time.sleep(0.8)
            return

        playlist = self.get_playlist(playlist_id)
        playlist_items = playlist["tracks"]
        videos_to_remove = [
            video
            for video in playlist_items
            if "videoId" in video and video["videoId"] in track_ids
        ]
        self.ytm.remove_playlist_items(playlist_id, videos_to_remove)

    def get_library_playlists(self, *args, **kwargs):
        return self.ytm.get_library_playlists(*args, **kwargs)


class YTM(
    StreamingService,
    Searchable,
    TrackPullable,
    Pushable,
    UserPlaylistPullable,
):
    wrapper: YtmWrapper

    def __init__(self, name: str, wrapper: YtmWrapper) -> None:
        super().__init__(name, ServiceType.YTM)
        self.wrapper = wrapper

    def get_playlist_metadatas(self) -> list[PlaylistMetadata]:
        results = self.wrapper.get_library_playlists()

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
            filter(
                None,
                map(
                    self.raw_to_track,
                    songs,
                ),
            )
        )

    def pull_tracks(self, uri: YtmPlaylistURI) -> List[Track]:
        tracks = self.wrapper.get_playlist(uri.uri)["tracks"]
        return self.results_to_tracks(tracks)

    def parse_video_details(self, details: dict) -> Optional[Track]:
        title = details["title"]
        if details["musicVideoType"] == "MUSIC_VIDEO_TYPE_UGC":  # messy title
            artist_title_tuple = get_artist_title(title)
            if artist_title_tuple:
                artist, title = artist_title_tuple
            else:
                artist = None
        else:
            artist = details["author"]

        if "videoId" not in details:
            return None

        return Track(
            name=AliasedString(title),
            artists=[AliasedString(artist)] if artist else [],
            length=details["lengthSeconds"],
            uris=[YtmTrackURI.from_uri(details["videoId"])],
        )

    def raw_to_track(self, raw: dict) -> Optional[Track]:
        if "videoDetails" in raw:
            return self.parse_video_details(raw["videoDetails"])

        if "videoId" not in raw or raw["videoId"] is None:
            return None

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
        raw = self.wrapper.get_song(uri.uri)
        track = self.raw_to_track(raw)
        assert track is not None
        return track

    def search_query(self, query: str) -> List[Track]:
        results = self.wrapper.search(query)
        return self.results_to_tracks(results)

    def query_generator(self, track: Track) -> List[str]:
        query = f"{track.name.value} - {' '.join([artist.value for artist in track.artists])}"
        return [query]

    def create_playlist(self, title: str, description: str = "") -> PlaylistURIs:
        id = self.wrapper.create_playlist(title, description)
        return YtmPlaylistURI.from_uri(id)

    def add_tracks(self, playlist_uri: PlaylistURI, tracks: List[Track]) -> None:
        assert isinstance(playlist_uri, YtmPlaylistURI)

        track_ids = []
        for track in tracks:
            uri = track.find_uri(self.type)
            assert uri
            track_ids.append(uri.uri)

        self.wrapper.add_tracks(playlist_uri.uri, track_ids)

    def remove_tracks(self, playlist_uri: PlaylistURI, tracks: List[Track]) -> None:
        assert isinstance(playlist_uri, YtmPlaylistURI)

        track_ids = []
        for track in tracks:
            uri = track.find_uri(self.type)
            assert uri
            track_ids.append(uri.uri)

        self.wrapper.remove_tracks(playlist_uri.uri, track_ids)
