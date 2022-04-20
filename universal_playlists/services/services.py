from enum import Enum
import json
from pathlib import Path
from typing import List, Optional, TypedDict
import spotipy
from spotipy import SpotifyOAuth
from ytmusicapi import YTMusic
import musicbrainzngs as mb
from pydantic import BaseModel


class ServiceType(Enum):
    SPOTIFY = "spotify"
    YTM = "youtube-music"
    MB = "musicbrainz"


class URI(BaseModel):
    service: str
    uri: str

    class Config:
        frozen = True


class SpotifyURI(URI):
    def __init__(self, uri: str):
        super().__init__(service=ServiceType.SPOTIFY.value, uri=uri)


class YtmURI(URI):
    def __init__(self, uri: str):
        super().__init__(service=ServiceType.YTM.value, uri=uri)


class MB_RECORDING_URI(URI):
    def __init__(self, uri: str):
        super().__init__(service=ServiceType.MB.value, uri=uri)


class MB_RELEASE(URI):
    def __init__(self, uri: str):
        super().__init__(service=ServiceType.MB.value, uri=uri)


class Track(BaseModel):
    name: str
    album: Optional[str] = None
    album_position: Optional[int] = None
    artists: List[str] = []
    uris: List[URI] = []

    def matches(self, track: "Track") -> bool:
        # check if any URI in track matches any URI in self
        for uri in track.uris:
            if uri in self.uris:
                return True

        if self.name == track.name:
            # check if any artist in track matches any artist in self
            for artist in track.artists:
                if artist in self.artists:
                    return True

        return False


class PlaylistMetadata(TypedDict):
    name: str
    description: str
    uri: URI


class Playlist(BaseModel):
    name: str
    description: str = ""
    uris: List[URI] = []
    tracks: List[Track] = []

    def merge_metadata(self, metadata: PlaylistMetadata) -> None:
        self.name = self.name or metadata["name"]
        self.description = self.description or metadata["description"]
        if metadata["uri"] not in self.uris:
            self.uris.append(metadata["uri"])


class StreamingService:
    def __init__(self, name: str, config_path: Path) -> None:
        self.name = name
        self.config_path = config_path

    @staticmethod
    def service_builder(
        service_type: ServiceType,
        name: str,
        config_path: Path,
    ) -> "StreamingService":
        if service_type == ServiceType.SPOTIFY:
            return Spotify(name, config_path)
        elif service_type == ServiceType.YTM:
            return YTM(name, config_path)
        elif service_type == ServiceType.MB:
            return MusicBrainz()
        else:
            raise ValueError(f"Unknown service type: {service_type}")

    def get_playlist_metadatas(self) -> list[PlaylistMetadata]:
        raise NotImplementedError

    def get_playlist_metadata(self, playlist_name: str) -> PlaylistMetadata:
        metas = self.get_playlist_metadatas()
        for meta in metas:
            if meta["name"] == playlist_name:
                return meta
        raise ValueError(f"Playlist {playlist_name} not found in {self.name}")

    def pull_tracks(self, uri: URI) -> List[Track]:
        raise NotImplementedError

    def pull_track(self, uri: URI) -> Track:
        raise NotImplementedError

    def search_track(self, track: Track) -> List[Track]:
        """Search for a track in the streaming service. Returns a list of potential matches."""
        raise NotImplementedError


class Spotify(StreamingService):
    def __init__(self, name: str, config_path: Path) -> None:
        super().__init__(name, config_path)
        credentials = json.load(open(config_path, "r"))
        self.sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=credentials["client_id"],
                client_secret=credentials["client_secret"],
                redirect_uri=credentials["redirect_uri"],
                scope="user-library-read",
            )
        )

    def get_playlist_metadatas(self) -> list[PlaylistMetadata]:
        results = self.sp.current_user_playlists()

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
            results = self.sp.user_playlist_tracks(
                user=self.sp.current_user()["id"],
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


class YTM(StreamingService):
    def __init__(self, name: str, config_path: Path) -> None:
        super().__init__(name, config_path)
        self.ytm = YTMusic(config_path.__str__())

    def get_playlist_metadatas(self) -> list[PlaylistMetadata]:
        results = self.ytm.get_library_playlists()

        def playlistFromResponse(response):
            return PlaylistMetadata(
                name=response["title"],
                description=response["description"],
                uri=YtmURI(response["playlistId"]),
            )

        playlists = list(map(playlistFromResponse, results))
        return playlists

    def pull_tracks(self, uri: YtmURI) -> List[Track]:
        tracks = self.ytm.get_playlist(uri.uri)["tracks"]
        tracks = filter(lambda x: x["videoId"] is not None, tracks)
        tracks = list(
            map(
                lambda x: Track(
                    name=x["title"],
                    artists=[artist["name"] for artist in x["artists"]],
                    uris=[YtmURI(x["videoId"])],
                ),
                tracks,
            )
        )
        return tracks

    def pull_track(self, uri: YtmURI) -> Track:
        track = self.ytm.get_song(uri.uri)
        return Track(
            name=track["title"],
            artists=[artist["name"] for artist in track["artists"]],
            uris=[YtmURI(track["videoId"])],
        )


class MusicBrainz(StreamingService):
    def __init__(
        self,
    ) -> None:
        super().__init__("MusicBrainz", Path())
        mb.set_useragent("universal-playlist", "0.1")

    def pull_track(self, uri: MB_RECORDING_URI) -> Track:
        results = mb.get_recording_by_id(
            uri.uri, includes=["releases", "artists", "aliases", "media"]
        )
        if not results:
            raise ValueError(f"Recording {uri} not found")
        recording = results["recording"]

        print(json.dumps(recording, indent=4))
        track = Track(
            name=recording["title"],
            artists=[artist["artist"]["name"] for artist in recording["artist-credit"]],
        )
        if "release-list" not in recording or not recording["release-list"]:
            return track

        first_release = recording["release-list"][0]

        release_results = mb.get_release_by_id(
            first_release["id"], includes=["url-rels", "recordings"]
        )
        if not release_results:
            return track

        release = release_results["release"]
        track.album = release["title"]
        track.album_position = first_release["medium-list"][0]["position"]
        return track

    def search_track(self, track: Track) -> List[Track]:
        fields = [
            "recording:{}".format(track.name),
            "artist:{}".format(" ".join(track.artists)),
        ]
        query = " AND ".join(fields)

        results = mb.search_recordings(
            query=query,
            limit=1,
        )

        def parse_track(recording):
            return Track(
                name=recording["title"],
                artists=[
                    artist["name"]
                    for artist in recording["artist-credit"]
                    if "name" in artist
                ],
                uris=[MB_RECORDING_URI(recording["id"])],
            )

        return list(map(parse_track, results["recording-list"]))
