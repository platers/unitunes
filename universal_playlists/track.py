from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
)
from pydantic import BaseModel
from strsimpy.jaro_winkler import JaroWinkler
from rich import print
from universal_playlists.uri import TrackURIs


def pairwise_max(a: List[Any], b: List[Any], f: Callable[[Any, Any], float]) -> float:
    mx = 0
    for i in a:
        for j in b:
            mx = max(mx, f(i, j))
    return mx


def normalized_string_similarity(s1: str, s2: str) -> float:
    jw = JaroWinkler().similarity(s1.lower(), s2.lower())
    # convert to [-1, 1]
    return (jw - 0.5) * 2


class AliasedString(BaseModel):
    value: str
    aliases: List[str] = []

    def __init__(self, value: str, aliases: List[str] = []):
        super().__init__(value=value, aliases=aliases)
        # remove duplicates
        self.aliases = list(set(self.aliases))
        if self.value in self.aliases:
            self.aliases.remove(self.value)

    def __rich__(self):
        s = self.value
        if self.aliases:
            s += f" ({', '.join(self.aliases)})"
        return s

    def all_values(self) -> List[str]:
        return [self.value] + self.aliases

    def pairwise_max_similarity(self, other: "AliasedString") -> float:
        return pairwise_max(
            self.all_values(), other.all_values(), normalized_string_similarity
        )


def artists_similarity(
    artists1: List[AliasedString], artists2: List[AliasedString]
) -> float:
    if len(artists1) == 0 or len(artists2) == 0:
        return 0

    sim = pairwise_max(artists1, artists2, lambda a, b: a.pairwise_max_similarity(b))
    return sim


def album_similarity(album1: List[AliasedString], album2: List[AliasedString]) -> float:
    sim = pairwise_max(album1, album2, lambda a, b: a.pairwise_max_similarity(b))
    if sim < 0:
        sim /= 5

    return sim


def length_similarity(length_sec_1: int, length_sec_2: int) -> float:
    d = abs(length_sec_1 - length_sec_2)
    max_dist = 4
    if d > max_dist:
        return -1
    return 1 - d / max_dist


class Track(BaseModel):
    name: AliasedString
    albums: List[AliasedString] = []
    artists: List[AliasedString] = []
    length: Optional[int] = None
    uris: List[TrackURIs] = []

    def __rich__(self):
        s = f"[b]{self.name.__rich__()}[/b]"
        if self.artists:
            s += f"\nArtists: {', '.join(a.__rich__() for a in self.artists)}"
        if self.albums:
            s += f"\nAlbums: {', '.join([a.__rich__() for a in self.albums])}"
        if self.length:
            s += f"\nLength: {self.length}"
        if self.uris:
            s += f"\nURIs: {', '.join(uri.__rich__() for uri in self.uris)}"

        return s

    def similarity(self, other: "Track", verbose=False) -> float:
        # check if any URI in track matches any URI in self
        for uri in self.uris:
            if uri in other.uris:
                return 1

        weights = {
            "name": 50,
            "album": 20,
            "artists": 30,
            "length": 20,
        }

        feature_scores: Dict[str, float] = {}

        if self.name and other.name:
            feature_scores["name"] = self.name.pairwise_max_similarity(other.name)

        if self.artists and other.artists:
            feature_scores["artists"] = artists_similarity(self.artists, other.artists)

        if self.albums and other.albums:
            feature_scores["album"] = album_similarity(self.albums, other.albums)

        if self.length and other.length:
            feature_scores["length"] = length_similarity(self.length, other.length)

        if verbose:
            print(f"{self.name} vs {other.name}")
            print(other)
            print(feature_scores)

        used_features = feature_scores.keys()
        if not used_features:
            return 0

        weighted_sum = sum(
            feature_scores[feature] * weights[feature] for feature in used_features
        )
        total_weight = sum(weights[feature] for feature in used_features)

        similarity = weighted_sum / total_weight
        assert -1 <= similarity <= 1
        return similarity

    def matches(self, track: "Track", threshold: float = 0.8) -> bool:
        return self.similarity(track) > threshold

    def uri_matches(self, track: "Track") -> bool:
        return any(uri in track.uris for uri in self.uris)

    def merge(self, other: "Track") -> None:
        for uri in other.uris:
            if uri not in self.uris:
                self.uris.append(uri)

        # TODO: merge other fields

    def is_on_service(self, service_name: str) -> bool:
        return any(uri.service == service_name for uri in self.uris)
