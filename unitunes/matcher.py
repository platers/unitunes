from abc import ABC, abstractmethod
from typing import Any, Dict, List, Callable
from strsimpy.jaro_winkler import JaroWinkler

from unitunes.track import AliasedString, Track


def pairwise_max(a: List[Any], b: List[Any], f: Callable[[Any, Any], float]) -> float:
    mx = 0
    for i in a:
        for j in b:
            mx = max(mx, f(i, j))
    return mx


def normalized_string_similarity(s1: str, s2: str) -> float:
    """Returns a similarity score between 0 and 1. Penalizes differences in keywords like 'instrumental'"""
    special_terms = [
        "instrumental",
        "remix",
        "cover",
        "live",
        "version",
        "edit",
    ]

    for term in special_terms:
        in_s1 = term in s1.lower()
        in_s2 = term in s2.lower()

        if in_s1 ^ in_s2:
            return 0

    return JaroWinkler().similarity(s1.lower(), s2.lower())


class MatcherStrategy(ABC):
    @abstractmethod
    def similarity(self, track1: Track, track2: Track) -> float:
        """
        Returns a similarity score between 0 and 1.
        """

    def are_same(self, track1: Track, track2: Track, theshold=0.7) -> bool:
        return self.similarity(track1, track2) >= theshold


class DefaultMatcherStrategy(MatcherStrategy):
    def aliased_string_similarity(self, s1: AliasedString, s2: AliasedString) -> float:
        return pairwise_max(
            s1.all_values(), s2.all_values(), normalized_string_similarity
        )

    def similarity(self, track1: Track, track2: Track) -> float:
        # check if any uris match
        if any(uri1 in track2.uris for uri1 in track1.uris):
            return 1

        def artists_similarity(
            artists1: List[AliasedString], artists2: List[AliasedString]
        ) -> float:
            if len(artists1) == 0 or len(artists2) == 0:
                return 0.5

            sim = pairwise_max(artists1, artists2, self.aliased_string_similarity)
            return sim

        def album_similarity(
            album1: List[AliasedString], album2: List[AliasedString]
        ) -> float:
            sim = pairwise_max(album1, album2, self.aliased_string_similarity)
            return sim

        def length_similarity(length_sec_1: int, length_sec_2: int) -> float:
            d = abs(length_sec_1 - length_sec_2)
            max_dist = 5
            if d > max_dist:
                return 0
            return 1 - d / max_dist

        weights = {
            "name": 50,
            "album": 20,
            "artists": 30,
            "length": 20,
        }

        feature_scores: Dict[str, float] = {}

        if track1.name and track2.name:
            feature_scores["name"] = self.aliased_string_similarity(
                track1.name, track2.name
            )

        if track1.artists and track2.artists:
            feature_scores["artists"] = artists_similarity(
                track1.artists, track2.artists
            )

        if track1.albums and track2.albums:
            feature_scores["album"] = album_similarity(track1.albums, track2.albums)

        if track1.length and track2.length:
            feature_scores["length"] = length_similarity(track1.length, track2.length)

        used_features = feature_scores.keys()
        if not used_features:
            return 0

        weighted_sum = sum(
            feature_scores[feature] * weights[feature] for feature in used_features
        )
        total_weight = sum(weights[feature] for feature in used_features)

        similarity = weighted_sum / total_weight
        assert 0 <= similarity <= 1
        return similarity
