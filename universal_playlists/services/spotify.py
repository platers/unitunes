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
    def track(self, uri: str, use_cache=True):
        return self.sp.track(uri)

    @cache
    def album_tracks(self, album_id: str, use_cache=True):
        return self.sp.album_tracks(album_id)


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
                "uri": SpotifyURI(playlist["external_urls"]["spotify"]),
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
            tracks = []
            for track in results["items"]:
                uris = track["track"]["external_urls"]
                uri: List[URI] = []
                if "spotify" in uris:
                    uri = [SpotifyURI(uris["spotify"])]

                tracks.append(
                    Track(
                        name=track["track"]["name"],
                        artists=[
                            artist["name"] for artist in track["track"]["artists"]
                        ],
                        uris=uri,
                    )
                )
            return tracks

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
        return [
            Track(
                name=track["name"],
                artists=[artist["name"] for artist in track["artists"]],
                uris=[SpotifyURI(track["external_urls"]["spotify"])],
            )
            for track in results["items"]
        ]

    def pull_track(self, uri: URI) -> Track:
        track_id = uri.uri.split("/")[-1]
        results = self.sp.track(track_id)
        if not results:
            raise ValueError(f"Track {uri} not found")
        return Track(
            name=results["name"],
            artists=[artist["name"] for artist in results["artists"]],
            uris=[SpotifyURI(results["external_urls"]["spotify"])],
        )
