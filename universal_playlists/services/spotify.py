import json
from pathlib import Path
from typing import List
import spotipy
from spotipy import SpotifyOAuth

from universal_playlists.services.services import (
    URI,
    PlaylistMetadata,
    ServiceType,
    ServiceWrapper,
    StreamingService,
    Track,
    cache,
)


class SpotifyURI(URI):
    def __init__(self, uri: str):
        super().__init__(service=ServiceType.SPOTIFY.value, uri=uri)

    def url(self) -> str:
        return f"https://open.spotify.com/track/{self.uri}"

    @staticmethod
    def url_to_uri(url: str) -> str:
        return url.split("/")[-1]

    @staticmethod
    def from_url(url: str) -> "SpotifyURI":
        return SpotifyURI(SpotifyURI.url_to_uri(url))


class SpotifyWrapper(ServiceWrapper):
    def __init__(self, config) -> None:
        super().__init__("spotify")
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
    def __init__(self, name: str, config_path: Path) -> None:
        super().__init__(name, config_path)
        credentials = json.load(open(config_path, "r"))
        self.sp = SpotifyWrapper(credentials)

    def get_playlist_metadatas(self) -> list[PlaylistMetadata]:
        results = self.sp.sp.current_user_playlists()

        return [
            {
                "name": playlist["name"],
                "description": playlist["description"],
                "uri": SpotifyURI.from_url(playlist["external_urls"]["spotify"]),
            }
            for playlist in results["items"]
        ]

    def pull_tracks(self, uri: URI) -> List[Track]:
        # query spotify until we get all tracks
        playlist_id = uri.uri.split("/")[-1]

        def get_tracks(offset: int) -> list[Track]:
            results = self.sp.sp.user_playlist_tracks(
                user=self.sp.sp.current_user()["id"],
                playlist_id=playlist_id,
                fields="items(track(name,artists(name),id,external_urls))",
                offset=offset,
            )
            return list(
                map(
                    self.raw_to_track,
                    results["items"],
                )
            )

        tracks = []
        offset = 0
        while True:
            new_tracks = get_tracks(offset)
            if not new_tracks:
                break
            tracks.extend(new_tracks)
            offset += len(new_tracks)
        return tracks

    def get_tracks_in_album(self, album_uri: URI) -> List[Track]:
        album_id = album_uri.uri.split("/")[-1]
        results = self.sp.album_tracks(album_id)
        return [self.raw_to_track(track) for track in results["items"]]

    def pull_track(self, uri: URI) -> Track:
        track_id = uri.uri.split("/")[-1]
        results = self.sp.track(track_id)
        if not results:
            raise ValueError(f"Track {uri} not found")
        return self.raw_to_track(results)

    def raw_to_track(self, raw: dict) -> Track:
        return Track(
            name=raw["name"],
            artists=[artist["name"] for artist in raw["artists"]],
            album=raw["album"]["name"],
            length=raw["duration_ms"] // 1000,
            uris=[SpotifyURI.from_url(raw["external_urls"]["spotify"])],
        )

    def search_track(self, track: Track) -> List[Track]:
        query = f"track:{track.name}"
        if track.artists:
            query += f" artist:{' '.join(track.artists)}"
        if track.album:
            query += f" album:{track.album}"

        results = self.sp.search(query, limit=5, type="track")
        return list(
            map(
                self.raw_to_track,
                results["tracks"]["items"],
            )
        )
