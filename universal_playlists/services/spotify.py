import json
from pathlib import Path
from typing import List
import spotipy
from spotipy import SpotifyOAuth
from tqdm import tqdm

from universal_playlists.services.services import (
    URI,
    AliasedString,
    PlaylistMetadata,
    ServiceType,
    ServiceWrapper,
    StreamingService,
    Track,
    SpotifyURI,
    cache,
)


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
        super().__init__(name, ServiceType.SPOTIFY, config_path)
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
                fields="items(track(name,artists(name),album,duration_ms,id,external_urls))",
                offset=offset,
            )
            return [
                self.raw_to_track(track["track"]) for track in tqdm(results["items"])
            ]

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
            name=AliasedString(value=raw["name"]),
            artists=[AliasedString(value=artist["name"]) for artist in raw["artists"]],
            albums=[AliasedString(value=raw["album"]["name"])],
            length=raw["duration_ms"] // 1000,
            uris=[SpotifyURI.from_url(raw["external_urls"]["spotify"])]
            if "spotify" in raw["external_urls"]
            else [],
        )

    def search_track(self, track: Track) -> List[Track]:
        query = f"track:{track.name}"
        if track.artists:
            query += f" artist:{' '.join([artist.value for artist in track.artists])}"
        if track.albums:
            query += f" album:{track.albums[0]}"

        results = self.sp.search(query, limit=5, type="track")
        return list(
            map(
                self.raw_to_track,
                results["tracks"]["items"],
            )
        )
