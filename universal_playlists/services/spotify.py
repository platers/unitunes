import json
from pathlib import Path
from typing import List
import spotipy
from spotipy import SpotifyOAuth
from tqdm import tqdm
from universal_playlists.playlist import PlaylistMetadata

from universal_playlists.services.services import (
    ServiceWrapper,
    StreamingService,
    cache,
)
from universal_playlists.track import AliasedString, Track
from universal_playlists.types import ServiceType
from universal_playlists.uri import URI, SpotifyPlaylistURI, SpotifyTrackURI


class SpotifyWrapper(ServiceWrapper):
    def __init__(self, config, cache_root) -> None:
        super().__init__("spotify", cache_root=cache_root)
        self.sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=config["client_id"],
                client_secret=config["client_secret"],
                redirect_uri=config["redirect_uri"],
                scope="user-library-read",
            )
        )

    @cache
    def track(self, *args, use_cache=True, **kwargs):
        return self.sp.track(*args, **kwargs)

    @cache
    def album_tracks(self, *args, use_cache=True, **kwargs):
        return self.sp.album_tracks(*args, **kwargs)

    @cache
    def search(self, *args, use_cache=True, **kwargs):
        return self.sp.search(*args, **kwargs)


class SpotifyService(StreamingService):
    wrapper: SpotifyWrapper

    def __init__(self, name: str, wrapper: SpotifyWrapper) -> None:
        super().__init__(name, ServiceType.SPOTIFY)
        self.wrapper = wrapper

    def get_playlist_metadatas(self) -> list[PlaylistMetadata]:
        results = self.wrapper.sp.current_user_playlists()

        return [
            PlaylistMetadata(
                name=playlist["name"],
                description=playlist["description"],
                uri=SpotifyPlaylistURI.from_url(playlist["external_urls"]["spotify"]),
            )
            for playlist in results["items"]
        ]

    def pull_tracks(self, uri: URI) -> List[Track]:
        # query spotify until we get all tracks
        playlist_id = uri.uri

        def get_tracks(offset: int) -> list[Track]:
            results = self.wrapper.sp.user_playlist_tracks(
                user=self.wrapper.sp.current_user()["id"],
                playlist_id=playlist_id,
                fields="items(track(name,artists(name),album,duration_ms,id,external_urls))",
                offset=offset,
            )
            return [self.raw_to_track(track["track"]) for track in results["items"]]

        tracks = []
        offset = 0
        while True:
            new_tracks = get_tracks(offset)
            if not new_tracks:
                break
            tracks.extend(new_tracks)
            offset += len(new_tracks)

        # filter out tracks withouth uris
        tracks = [track for track in tracks if track.uris]
        return tracks

    def get_tracks_in_album(self, album_uri: URI) -> List[Track]:
        album_id = album_uri.uri.split("/")[-1]
        results = self.wrapper.album_tracks(album_id)
        return [self.raw_to_track(track) for track in results["items"]]

    def pull_track(self, uri: URI) -> Track:
        track_id = uri.uri.split("/")[-1]
        results = self.wrapper.track(track_id)
        if not results:
            raise ValueError(f"Track {uri} not found")
        return self.raw_to_track(results)

    def raw_to_track(self, raw: dict) -> Track:
        return Track(
            name=AliasedString(value=raw["name"]),
            artists=[AliasedString(value=artist["name"]) for artist in raw["artists"]],
            albums=[AliasedString(value=raw["album"]["name"])],
            length=raw["duration_ms"] // 1000,
            uris=[SpotifyTrackURI.from_url(raw["external_urls"]["spotify"])]
            if "spotify" in raw["external_urls"]
            else [],
        )

    def search_track(self, track: Track) -> List[Track]:
        query = f"track:{track.name}"
        if track.artists:
            query += f" artist:{' '.join([artist.value for artist in track.artists])}"
        if track.albums:
            query += f" album:{track.albums[0]}"

        results = self.wrapper.search(query, limit=5, type="track")
        return list(
            map(
                self.raw_to_track,
                results["tracks"]["items"],
            )
        )
