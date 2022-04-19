from enum import Enum
import json
from pathlib import Path
from typing import List, NewType, Optional, Set, TypedDict
import spotipy
from spotipy import SpotifyOAuth
from ytmusicapi import YTMusic
import musicbrainzngs as mb


class ServiceType(Enum):
    SPOTIFY = "spotify"
    YTM = "youtube-music"
    MB = "musicbrainz"


class URI:
    def __init__(self, service: str, uri: str):
        self.service = service
        self.uri = uri

    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, URI):
            return False
        return self.service == __o.service and self.uri == __o.uri

    def __hash__(self) -> int:
        return hash(self.service) ^ hash(self.uri)

    def toJSON(self) -> dict:
        return {
            "service": self.service,
            "uri": self.uri,
        }

    def __repr__(self) -> str:
        return f"URI('{self.service}', '{self.uri}')"


class SpotifyURI(URI):
    def __init__(self, uri: str):
        super().__init__(ServiceType.SPOTIFY.value, uri)


class YtmURI(URI):
    def __init__(self, uri: str):
        super().__init__(ServiceType.YTM.value, uri)


class MB_RECORDING_URI(URI):
    def __init__(self, uri: str):
        super().__init__("mb_recording", uri)


class MB_RELEASE(URI):
    def __init__(self, uri: str):
        super().__init__("mb_release", uri)


class Track:
    def __init__(
        self,
        name: str,
        album: str = "",
        album_position: int = 0,
        artists: list[str] = [],
        uris: list[URI] = [],
    ) -> None:
        self.name = name
        self.album = album
        self.album_position = album_position
        self.artists = artists
        self.uris = uris

    def toJSON(self) -> dict:
        return {
            "name": self.name,
            "album": self.album,
            "album_position": self.album_position,
            "artists": self.artists,
            "uris": [u.toJSON() for u in self.uris],
        }

    @staticmethod
    def fromJSON(json: dict) -> "Track":
        return Track(
            json["name"],
            json["artists"],
            json["album"] if "album" in json else "",
            json["album_position"] if "album_position" in json else 0,
            [URI(u["service"], u["uri"]) for u in json["uris"]],
        )

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


class Playlist:
    def __init__(
        self,
        name: str,
        description: str = "",
        uris: Set[URI] = set(),
        tracks: List[Track] = [],
        playlist_config_path: Path = Path(),
    ) -> None:
        self.name = name
        self.description = description
        self.uris = uris
        self.tracks = tracks
        self.playlist_config_path = playlist_config_path

    @classmethod
    def from_file(cls, file_path: Path) -> "Playlist":
        with open(file_path, "r") as f:
            data = json.load(f)
            data["playlist_config_path"] = file_path
            data["uris"] = set([URI(**x) for x in data["uris"]])
            data["tracks"] = [Track.fromJSON(x) for x in data["tracks"]]
        return cls(**data)

    def to_file(self, file_path: Path) -> None:
        # touch file
        file_path.touch(exist_ok=True)
        with open(file_path, "w") as f:
            d = {
                "name": self.name,
                "description": self.description,
                "uris": [x.toJSON() for x in list(self.uris)],
                "tracks": [track.toJSON() for track in self.tracks],
            }
            json.dump(d, f, indent=4)

    def merge_metadata(self, metadata: PlaylistMetadata) -> None:
        self.name = self.name or metadata["name"]
        self.description = self.description or metadata["description"]
        self.uris.add(metadata["uri"])
        self.to_file(self.playlist_config_path)


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
        '''Search for a track in the streaming service. Returns a list of potential matches.'''
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
            # tracks = self.ytm.get_playlist(response["playlistId"])["tracks"]
            # tracks = filter(lambda x: x["videoId"] is not None, tracks)
            # tracks = list(
            #     map(
            #         lambda x: Track(
            #             x["title"],
            #             artist=x["artists"][0]["name"],
            #             ytm_url="https://music.youtube.com/watch?v=" + x["videoId"],
            #         ),
            #         tracks,
            #     )
            # )

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
                    x["title"],
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

    def pull_track(self, uri: MB_RECORDING_URI) -> Optional[Track]:
        results = mb.get_recording_by_id(
            uri.uri, includes=["releases", "artists", "aliases", "media"]
        )
        if not results:
            return None
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

    def search_track(self, track: Track) -> Optional[MB_RECORDING_URI]:
        fields = [
            "recording:{}".format(track.name),
            "artist:{}".format(" ".join(track.artists)),
        ]
        query = " AND ".join(fields)

        results = mb.search_recordings(
            query=query,
            limit=1,
        )
        print(track.name, track.artists)
        print(json.dumps(results, indent=4))
        if not results:
            return None

        return MB_RECORDING_URI(results["recording-list"][0]["id"])
