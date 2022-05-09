from os import remove
from pathlib import Path
from typing import List, Optional
from ytmusicapi import YTMusic
from universal_playlists.playlist import Playlist, PlaylistMetadata
from youtube_title_parse import get_artist_title


from universal_playlists.services.services import (
    PlaylistPullable,
    Pushable,
    Searchable,
    ServiceWrapper,
    StreamingService,
    TrackPullable,
    UserPlaylistPullable,
    cache,
)
from universal_playlists.track import (
    AliasedString,
    Track,
    tracks_to_add,
    tracks_to_remove,
)
from universal_playlists.types import ServiceType
from universal_playlists.uri import (
    PlaylistURI,
    PlaylistURIs,
    YtmPlaylistURI,
    YtmTrackURI,
)


class YtmWrapper(ServiceWrapper):
    def __init__(self, config_path: Path, cache_root: Path) -> None:
        super().__init__("ytm", cache_root=cache_root)
        self.ytm = YTMusic(config_path.__str__())

    def get_playlist(self, *args, **kwargs):
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
        self.ytm.add_playlist_items(playlist_id, track_ids)

    def remove_tracks(self, playlist_id: str, track_ids: List[str]) -> None:
        """Remove tracks from a playlist."""
        playlist = self.get_playlist(playlist_id)
        playlist_items = playlist["tracks"]
        videos_to_remove = [
            video
            for video in playlist_items
            if "videoId" in video and video["videoId"] in track_ids
        ]
        self.ytm.remove_playlist_items(playlist_id, videos_to_remove)


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
        results = self.wrapper.ytm.get_library_playlists()

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

    def pull_tracks(self, uri: YtmPlaylistURI) -> List[Track]:
        tracks = self.wrapper.get_playlist(uri.uri)["tracks"]
        return self.results_to_tracks(tracks)

    def parse_video_details(self, details: dict) -> Track:
        title = details["title"]
        if details["musicVideoType"] == "MUSIC_VIDEO_TYPE_UGC":
            artist_title_tuple = get_artist_title(title)
            if artist_title_tuple:
                artist, title = artist_title_tuple
            else:
                artist = None
        else:
            artist = details["author"]

        return Track(
            name=AliasedString(title),
            artists=[AliasedString(artist)] if artist else [],
            length=details["lengthSeconds"],
            uris=[YtmTrackURI.from_uri(details["videoId"])],
        )

    def raw_to_track(self, raw: dict) -> Track:
        if "videoDetails" in raw:
            return self.parse_video_details(raw["videoDetails"])

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
        track = self.wrapper.get_song(uri.uri)
        return self.raw_to_track(track)

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
