import json
from pathlib import Path
from typing import List
import musicbrainzngs as mb

from universal_playlists.services.services import (
    MB_RECORDING_URI,
    AliasedString,
    ServiceType,
    ServiceWrapper,
    StreamingService,
    Track,
    cache,
)


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
        super().__init__("MusicBrainz", ServiceType.MB, Path())
        self.mb = MusicBrainzWrapper()

    def pull_track(self, uri: MB_RECORDING_URI) -> Track:
        results = self.mb.get_recording_by_id(
            id=uri.uri, includes=["releases", "artists", "aliases", "media"]
        )
        if not results:
            raise ValueError(f"Recording {uri} not found")
        recording = results["recording"]

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

    def search_track_fields(self, track: Track, fields) -> List[Track]:
        results = self.mb.search_recordings(
            limit=10,
            **fields,
        )

        def parse_track(recording):
            albums = (
                [
                    AliasedString(value=album["title"])
                    for album in recording["release-list"]
                    if "title" in album
                ]
                if "release-list" in recording
                else []
            )
            return Track(
                name=AliasedString(value=recording["title"]),
                artists=[
                    artist["name"]
                    for artist in recording["artist-credit"]
                    if "name" in artist
                ],
                albums=albums,
                length=int(recording["length"]) // 1000
                if "length" in recording
                else None,
                uris=[MB_RECORDING_URI(uri=recording["id"])],
            )

        return list(map(parse_track, results["recording-list"]))

    def search_track(self, track: Track, stop_threshold: float = 0.8) -> List[Track]:
        def escape_special_chars(s: str) -> str:
            # + - && || ! ( ) { } [ ] ^ " ~ * ? : \
            special_chars = [
                "\\",  # \ needs to be escaped first or else it will be escaped twice
                "+",
                "-",
                "&&",
                "||",
                "!",
                "(",
                ")",
                "{",
                "}",
                "[",
                "]",
                "^",
                '"',
                "~",
                "*",
                "?",
                ":",
            ]
            for char in special_chars:
                s = s.replace(char, f"\\{char}")
            return s

        all_fields = {
            "recording": escape_special_chars(track.name.value),
            "artist": escape_special_chars(" ".join(track.artists)),
            "release": escape_special_chars(" ".join([a.value for a in track.albums])),
        }

        matches = self.search_track_fields(track, all_fields)
        max_similarity = max(matches, key=lambda m: track.similarity(m)).similarity(
            track
        )
        if max_similarity >= stop_threshold:
            return matches

        fields_no_release = all_fields.copy()
        del fields_no_release["release"]
        matches.extend(self.search_track_fields(track, fields_no_release))
        max_similarity = max(matches, key=lambda m: track.similarity(m)).similarity(
            track
        )
        if max_similarity >= stop_threshold:
            return matches

        fields_no_artist = all_fields.copy()
        del fields_no_artist["artist"]
        matches.extend(self.search_track_fields(track, fields_no_artist))
        max_similarity = max(matches, key=lambda m: track.similarity(m)).similarity(
            track
        )
        return matches
