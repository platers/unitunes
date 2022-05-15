from pathlib import Path
from typing import List, Optional
import musicbrainzngs as mb
from ratelimit import sleep_and_retry, limits


import requests
from unitunes.services.services import (
    Query,
    Searchable,
    ServiceWrapper,
    StreamingService,
    TrackPullable,
    cache,
)
from unitunes.track import AliasedString, Track
from unitunes.types import ServiceType
from unitunes.uri import MB_RECORDING_URI


class MusicBrainzWrapper(ServiceWrapper):
    def __init__(self, cache_root: Path) -> None:
        super().__init__("musicbrainz", cache_root)
        mb.set_useragent("unitunes", "0.1")

    @sleep_and_retry
    @limits(calls=1, period=1)
    def query_mb_api(self, query: str, params):
        headers = {"User-Agent": "unitunes"}
        r = requests.get(query, params=params, headers=headers)
        if r.status_code != 200:
            raise Exception(f"MusicBrainz API returned {r.status_code}")
        if "error" in r.json():
            raise Exception(f"MusicBrainz API returned error: {r.json()['error']}")
        return r.json()

    @cache
    def get_recording_by_id(self, id: str, use_cache=True, includes: List[str] = []):
        # Send this manually because the musicbrainzngs library doesn't return aliases for some reason
        params = {
            "inc": "+".join(includes),
            "fmt": "json",
        }
        return self.query_mb_api(
            f"http://musicbrainz.org/ws/2/recording/{id}", params=params
        )

    @cache
    def search_recordings(self, *args, use_cache=True, **kwargs):
        return mb.search_recordings(*args, **kwargs)

    @cache
    def get_release_by_id(self, *args, use_cache=True, **kwargs):
        return mb.get_release_by_id(*args, **kwargs)


class MusicBrainz(StreamingService, Searchable, TrackPullable):
    wrapper: MusicBrainzWrapper

    def __init__(self, wrapper: MusicBrainzWrapper) -> None:
        super().__init__("MusicBrainz", ServiceType.MB)
        self.wrapper = wrapper

    @staticmethod
    def parse_track(recording):
        def parse_aliases(obj) -> List[str]:
            return (
                [alias["name"] for alias in obj["aliases"]]
                if "obj" in recording
                else []
            )

        def parse_aliased_string(obj) -> Optional[AliasedString]:
            if "title" not in obj:
                return None
            return AliasedString(obj["title"], parse_aliases(obj))

        name = parse_aliased_string(recording)
        if not name:
            raise ValueError(f"Recording {recording} has no name")

        albums = []
        if "releases" in recording:
            for album in recording["releases"]:
                s = parse_aliased_string(album)
                if s:
                    albums.append(s)
        if "release-list" in recording:
            for album in recording["release-list"]:
                s = parse_aliased_string(album)
                if s:
                    albums.append(s)

        artists = []
        if "artist-credit" in recording:
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
            name=name,
            artists=artists,
            albums=albums,
            length=int(recording["length"]) // 1000
            if "length" in recording and recording["length"]
            else None,
            uris=[MB_RECORDING_URI.from_uri(recording["id"])],
        )

    def pull_track(self, uri: MB_RECORDING_URI) -> Track:
        results = self.wrapper.get_recording_by_id(
            id=uri.uri, includes=["releases", "artists", "aliases"]
        )
        if not results:
            raise ValueError(f"Recording {uri} not found")
        track = self.parse_track(results)
        return track

    def search_query(self, query: Query) -> List[Track]:
        # remove empty fields
        fields = {k: v for k, v in query.items() if v}

        results = self.wrapper.search_recordings(
            limit=5,
            **fields,
        )

        return list(map(self.parse_track, results["recording-list"]))

    def query_generator(self, track: Track) -> List[Query]:
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

        queries = []
        for removed_fields in fields_to_remove:
            fields = {
                field: all_fields[field]
                for field in all_fields
                if field not in removed_fields
            }
            if not any(fields.values()):
                continue

            queries.append(fields)
        return queries
