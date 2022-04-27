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

    def search_track_fields(self, fields) -> List[Track]:
        # remove empty fields
        fields = {k: v for k, v in fields.items() if v}

        results = self.mb.search_recordings(
            limit=10,
            **fields,
        )
        # if "Eve" in json.dumps(results):
        #     print(json.dumps(results, indent=2))

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
            artists = []
            for artist in recording["artist-credit"]:
                if "artist" in artist:
                    a = artist["artist"]
                    if "name" in a:
                        aliases = (
                            [alias["alias"] for alias in a["alias-list"]]
                            if "alias-list" in a
                            else []
                        )
                        if "sort-name" in a:
                            aliases.append(a["sort-name"])
                        artists.append(AliasedString(value=a["name"], aliases=aliases))

            return Track(
                name=AliasedString(value=recording["title"]),
                artists=artists,
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
            "artist": escape_special_chars(
                " ".join([artist.value for artist in track.artists])
            ),
            "release": escape_special_chars(" ".join([a.value for a in track.albums])),
        }

        fields_to_remove = [
            [],
            ["release"],
            ["artist"],
            ["recording"],
            ["artist", "release"],
        ]

        def can_stop(matches: List[Track]) -> bool:
            if not matches:
                return False

            max_similarity = max(matches, key=lambda m: track.similarity(m)).similarity(
                track
            )
            return max_similarity >= stop_threshold

        matches = []
        for removed_fields in fields_to_remove:
            fields = {
                field: all_fields[field]
                for field in all_fields
                if field not in removed_fields
            }
            if not any(fields.values()):
                continue

            matches.extend(self.search_track_fields(fields))
            if can_stop(matches):
                break

        return matches
