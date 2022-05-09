from typing import List
import spotipy
from spotipy import SpotifyOAuth
from universal_playlists.playlist import Playlist, PlaylistMetadata

from universal_playlists.services.services import (
    PlaylistPullable,
    Pushable,
    Query,
    Searchable,
    ServiceWrapper,
    StreamingService,
    TrackPullable,
    UserPlaylistPullable,
    cache,
)
from universal_playlists.track import AliasedString, Track
from universal_playlists.types import ServiceType
from universal_playlists.uri import (
    URI,
    PlaylistURI,
    PlaylistURIs,
    SpotifyPlaylistURI,
    SpotifyTrackURI,
)


class SpotifyWrapper(ServiceWrapper):
    def __init__(self, config, cache_root) -> None:
        super().__init__("spotify", cache_root=cache_root)
        self.sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=config["client_id"],
                client_secret=config["client_secret"],
                redirect_uri=config["redirect_uri"],
                scope="user-library-read playlist-modify-private, playlist-modify-public",
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

    def create_playlist(self, title: str, description: str = "") -> str:
        id = self.sp.user_playlist_create(self.sp.me()["id"], title, public=False)["id"]
        assert isinstance(id, str)
        return id

    def add_tracks(self, playlist_id: str, tracks: List[str]) -> None:
        self.sp.user_playlist_add_tracks(self.sp.me()["id"], playlist_id, tracks)

    def remove_tracks(self, playlist_id: str, tracks: List[str]) -> None:
        self.sp.user_playlist_remove_all_occurrences_of_tracks(
            self.sp.me()["id"], playlist_id, tracks
        )


class SpotifyService(
    StreamingService,
    Searchable,
    TrackPullable,
    Pushable,
    UserPlaylistPullable,
):
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

    def search_query(self, query: str) -> List[Track]:
        results = self.wrapper.search(query, limit=5, type="track")
        return list(
            map(
                self.raw_to_track,
                results["tracks"]["items"],
            )
        )

    def query_generator(self, track: Track) -> List[str]:
        query = f'track:"{track.name}"'
        if track.artists:
            query += (
                f" artist:\"{' '.join([artist.value for artist in track.artists])}\""
            )
        if track.albums:
            query += f' album:"{track.albums[0].value}"'

        return [query]

    def create_playlist(self, name: str, description: str = "") -> PlaylistURIs:
        playlist = self.wrapper.sp.user_playlist_create(
            self.wrapper.sp.current_user()["id"],
            name,
            public=False,
            description=description,
        )
        uri = SpotifyPlaylistURI.from_url(playlist["external_urls"]["spotify"])
        return uri

    def push_playlist(self, playlist: Playlist) -> PlaylistURI:
        uri = playlist.find_uri(self.type)
        if not uri:
            raise ValueError(f"Playlist {playlist} does not have a spotify uri")

        track_uris = [track.find_uri(self.type) for track in playlist.tracks]
        track_ids = [uri.uri for uri in track_uris if uri]

        self.wrapper.sp.user_playlist_replace_tracks(
            self.wrapper.sp.current_user()["id"], uri.uri, track_ids
        )

        return uri

    def add_tracks(self, playlist_uri: PlaylistURI, tracks: List[Track]) -> None:
        assert isinstance(playlist_uri, SpotifyPlaylistURI)
        track_ids = []
        for track in tracks:
            uri = track.find_uri(self.type)
            assert uri
            track_ids.append(uri.uri)

        self.wrapper.add_tracks(playlist_uri.uri, track_ids)

    def remove_tracks(self, playlist_uri: PlaylistURI, tracks: List[Track]) -> None:
        assert isinstance(playlist_uri, SpotifyPlaylistURI)
        track_ids = []
        for track in tracks:
            uri = track.find_uri(self.type)
            assert uri
            track_ids.append(uri.uri)

        self.wrapper.remove_tracks(playlist_uri.uri, track_ids)
