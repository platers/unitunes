import json
from pathlib import Path
from typing import List
import musicbrainzngs as mb

from universal_playlists.services.services import (
    URI,
    ServiceType,
    ServiceWrapper,
    StreamingService,
    Track,
    cache,
)


class MB_RECORDING_URI(URI):
    def __init__(self, uri: str):
        super().__init__(service=ServiceType.MB.value, uri=uri)


class MB_RELEASE(URI):
    def __init__(self, uri: str):
        super().__init__(service=ServiceType.MB.value, uri=uri)


class MusicBrainzWrapper(ServiceWrapper):
    def __init__(self) -> None:
        super().__init__("musicbrainz")
        mb.set_useragent("universal-playlist", "0.1")

    @cache
    def get_recording_by_id(self, *args, use_cache=True, **kwargs):
        return mb.get_recording_by_id(*args, **kwargs)

    @cache
    def search_recordings(self, *args, use_cache=True, **kwargs):
        return mb.search_recordings(*args, **kwargs)

    @cache
    def get_release_by_id(self, *args, use_cache=True, **kwargs):
        return mb.get_release_by_id(*args, **kwargs)


class MusicBrainz(StreamingService):
    def __init__(
        self,
    ) -> None:
        super().__init__("MusicBrainz", Path())
        self.mb = MusicBrainzWrapper()

    def pull_track(self, uri: MB_RECORDING_URI) -> Track:
        results = self.mb.get_recording_by_id(
            id=uri.uri, includes=["releases", "artists", "aliases", "media"]
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

        release_results = self.mb.get_release_by_id(
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

        results = self.mb.search_recordings(
            query=query,
            limit=3,
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
