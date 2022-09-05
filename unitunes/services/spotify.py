from pathlib import Path
from typing import List, Optional
import spotipy
from spotipy import SpotifyOAuth
from unitunes.playlist import PlaylistDetails, PlaylistMetadata

from unitunes.services.services import (
    ServiceConfig,
    ServiceWrapper,
    StreamingService,
    cache,
)
from unitunes.track import AliasedString, Track
from unitunes.types import ServiceType
from unitunes.uri import (
    AlbumURI,
    SpotifyPlaylistURI,
    SpotifyTrackURI,
)


class SpotifyConfig(ServiceConfig):
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = ""


class SpotifyAPIWrapper(ServiceWrapper):
    def __init__(self, config: SpotifyConfig, cache_root) -> None:
        super().__init__("spotify", cache_root=cache_root)
        self.init_config(config)

    def init_config(self, config: SpotifyConfig) -> None:
        self.sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=config.client_id,
                client_secret=config.client_secret,
                redirect_uri=config.redirect_uri,
                scope="user-library-read playlist-modify-private, playlist-modify-public, user-library-modify playlist-read-private",
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
        # Query length must be less than or equal to 100 characters, otherwise 404 is returned
        return self.sp.search(*args, **kwargs)

    def create_playlist(self, title: str, description: str = "") -> str:
        id = self.sp.user_playlist_create(self.sp.me()["id"], title, public=False)["id"]
        assert isinstance(id, str)
        return id

    def add_tracks(self, playlist_id: str, tracks: List[str]) -> None:
        chunk_size = 100
        chunks = [tracks[i : i + chunk_size] for i in range(0, len(tracks), chunk_size)]
        for chunk in chunks:
            self.sp.user_playlist_add_tracks(self.sp.me()["id"], playlist_id, chunk)

    def remove_tracks(self, playlist_id: str, tracks: List[str]) -> None:
        self.sp.user_playlist_remove_all_occurrences_of_tracks(
            self.sp.me()["id"], playlist_id, tracks
        )

    def current_user_playlists(self, *args, **kwargs):
        return self.sp.current_user_playlists(*args, **kwargs)

    def user_playlist_replace_tracks(self, *args, **kwargs):
        return self.sp.user_playlist_replace_tracks(*args, **kwargs)

    def playlist_tracks(self, *args, **kwargs):
        return self.sp.playlist_items(*args, **kwargs)

    def playlist_metadata(self, playlist_id: str) -> PlaylistDetails:
        if playlist_id == "Liked Songs":
            # Liked songs has no metadata
            return PlaylistDetails(name="Liked Songs", description="")

        res = self.sp.playlist(playlist_id, fields="name,description")
        return PlaylistDetails(name=res["name"], description=res["description"])

    def current_user(self, *args, **kwargs):
        return self.sp.current_user(*args, **kwargs)

    def user_playlist_create(self, *args, **kwargs):
        return self.sp.user_playlist_create(*args, **kwargs)

    def current_user_saved_tracks(self, limit: int = 20, offset: int = 0):
        return self.sp.current_user_saved_tracks(limit=limit, offset=offset)

    def current_user_saved_tracks_add(self, tracks: List[str]):
        # max 50 tracks per request
        chunk_size = 50
        chunks = [tracks[i : i + chunk_size] for i in range(0, len(tracks), chunk_size)]
        for chunk in chunks:
            self.sp.current_user_saved_tracks_add(chunk)

    def current_user_saved_tracks_delete(self, tracks: List[str]):
        # max 50 tracks per request
        chunk_size = 50
        chunks = [tracks[i : i + chunk_size] for i in range(0, len(tracks), chunk_size)]
        for chunk in chunks:
            self.sp.current_user_saved_tracks_delete(chunk)

    def change_details(self, playlist_id: str, title: str, description: str):
        if playlist_id == "Liked Songs":
            # Liked songs has no metadata
            return

        if not description:
            self.sp.user_playlist_change_details(
                self.sp.me()["id"], playlist_id, name=title
            )
        else:
            self.sp.user_playlist_change_details(
                self.sp.me()["id"], playlist_id, name=title, description=description
            )


class SpotifyService(StreamingService):
    wrapper: SpotifyAPIWrapper
    config: SpotifyConfig

    def __init__(self, name: str, config: SpotifyConfig, cache_root: Path) -> None:
        super().__init__(name, ServiceType.SPOTIFY, cache_root)
        self.load_config(config)

    def load_config(self, config: SpotifyConfig) -> None:
        self.config = config
        self.wrapper = SpotifyAPIWrapper(config, self.cache_root)

    def get_playlist_metadatas(self) -> list[PlaylistMetadata]:
        results = self.wrapper.current_user_playlists()

        return [
            PlaylistMetadata(
                name=playlist["name"],
                description=playlist["description"],
                uri=SpotifyPlaylistURI.from_url(playlist["external_urls"]["spotify"]),
            )
            for playlist in results["items"]
        ] + [
            PlaylistMetadata(
                name="Liked Songs",
                description="",
                uri=SpotifyPlaylistURI.from_url("spotify:liked_songs"),
            )
        ]

    def pull_tracks(self, uri: SpotifyPlaylistURI) -> List[Track]:
        # query spotify until we get all tracks

        def get_playlist_tracks(offset: int) -> list[Track]:
            results = self.wrapper.playlist_tracks(
                playlist_id=uri.uri,
                fields="items(track(name,artists(name),album,duration_ms,id,external_urls))",
                offset=offset,
            )
            return [self.raw_to_track(track["track"]) for track in results["items"]]

        def get_liked_tracks(offset: int) -> list[Track]:
            results = self.wrapper.current_user_saved_tracks(limit=50, offset=offset)
            return [self.raw_to_track(track["track"]) for track in results["items"]]

        tracks = []
        offset = 0
        while True:
            new_tracks = (
                get_liked_tracks(offset)
                if uri.is_liked_songs()
                else get_playlist_tracks(offset)
            )
            if not new_tracks:
                break
            tracks.extend(new_tracks)
            offset += len(new_tracks)

        # filter out tracks withouth uris
        tracks = [track for track in tracks if track.uris]
        return tracks

    def get_tracks_in_album(self, album_uri: AlbumURI) -> List[Track]:
        album_id = album_uri.uri.split("/")[-1]
        results = self.wrapper.album_tracks(album_id)
        return [self.raw_to_track(track) for track in results["items"]]

    def pull_track(self, uri: SpotifyTrackURI) -> Track:
        track_id = uri.uri.split("/")[-1]
        results = self.wrapper.track(track_id)
        if not results:
            raise ValueError(f"Track {uri} not found")
        return self.raw_to_track(results)

    def pull_metadata(self, uri: SpotifyPlaylistURI) -> PlaylistDetails:
        return self.wrapper.playlist_metadata(uri.uri)

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
        query = query[:100]

        results = self.wrapper.search(query, limit=5, type="track")
        return list(
            map(
                self.raw_to_track,
                results["tracks"]["items"],
            )
        )

    def query_generator(self, track: Track) -> List[str]:
        queries = []

        # query with all attributes
        queries.append(self._build_query(track.name, track.artists, track.albums))

        if track.artists:
            # query without artists
            queries.append(self._build_query(track.name, None, track.albums))

        if track.artists:
            # query without album
            queries.append(self._build_query(track.name, track.artists, None))

        # query with title outside track field
        # (this seems to trigger a more fuzzy search, in case the title doesn't match exactly)
        queries.append(self._build_query(None, track.artists, track.albums, track.name))

        if track.artists:
            # query without artists
            queries.append(self._build_query(None, None, track.albums, track.name))

        if track.artists:
            # query without album
            queries.append(self._build_query(None, track.artists, None, track.name))

        return queries


    def _build_query(self, name: Optional[AliasedString], artists: Optional[List[AliasedString]], albums: Optional[List[AliasedString]], other: Optional[AliasedString] = None):
        query = ''
        if name:
            query += f'track:"{name.value}"'
        if artists:
            query += (
                f" artist:\"{' '.join([artist.value for artist in artists])}\""
            )
        if albums:
            query += f' album:"{albums[0].value}"'
        if other:
            query += f' {other.value}'
        return query

    def create_playlist(self, name: str, description: str = "") -> SpotifyPlaylistURI:
        playlist = self.wrapper.user_playlist_create(
            self.wrapper.current_user()["id"],
            name,
            public=False,
            description=description,
        )
        uri = SpotifyPlaylistURI.from_url(playlist["external_urls"]["spotify"])
        return uri

    def add_tracks(self, playlist_uri: SpotifyPlaylistURI, tracks: List[Track]) -> None:
        track_ids = []
        for track in tracks:
            uri = track.find_uri(self.type)
            assert uri
            track_ids.append(uri.uri)

        if playlist_uri.is_liked_songs():
            self.wrapper.current_user_saved_tracks_add(track_ids)
        else:
            self.wrapper.add_tracks(playlist_uri.uri, track_ids)

    def remove_tracks(
        self, playlist_uri: SpotifyPlaylistURI, tracks: List[Track]
    ) -> None:
        track_ids = []
        for track in tracks:
            uri = track.find_uri(self.type)
            assert uri
            track_ids.append(uri.uri)

        if playlist_uri.is_liked_songs():
            self.wrapper.current_user_saved_tracks_delete(track_ids)
        else:
            self.wrapper.remove_tracks(playlist_uri.uri, track_ids)

    def update_metadata(
        self, playlist_uri: SpotifyPlaylistURI, metadata: PlaylistDetails
    ) -> None:
        self.wrapper.change_details(
            playlist_uri.uri, metadata.name, metadata.description
        )
