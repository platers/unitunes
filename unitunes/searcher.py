from abc import ABC, abstractmethod
from typing import List
from unitunes.matcher import MatcherStrategy
from unitunes.services.services import Searchable

from unitunes.track import Track


class SearcherStrategy(ABC):
    @abstractmethod
    def search(self, service: Searchable, track: Track) -> List[Track]:
        """Search for a track in the streaming service.
        Returns a sorted list of potential matches."""


class DefaultSearcherStrategy(SearcherStrategy):
    matcher: MatcherStrategy

    def __init__(self, matcher: MatcherStrategy) -> None:
        self.matcher = matcher

    def search(self, service: Searchable, track: Track, limit=3) -> List[Track]:
        queries = service.query_generator(track)
        stop_threshold = 0.8
        matches = []

        for query in queries:
            new_matches = service.search_query(query)
            for new_match in new_matches:
                if new_match not in matches:
                    matches.append(new_match)
            if any(
                self.matcher.similarity(track, match) >= stop_threshold
                for match in new_matches
            ):
                break

        matches.sort(key=lambda t: self.matcher.similarity(track, t), reverse=True)
        return matches[:limit]
