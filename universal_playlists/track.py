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
from universal_playlists.types import ServiceType
from universal_playlists.uri import TrackURIs


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

    def uri_matches(self, track: "Track") -> bool:
        return any(uri in track.uris for uri in self.uris)

    def merge(self, other: "Track") -> None:
        for uri in other.uris:
            if uri not in self.uris:
                self.uris.append(uri)

        # TODO: merge other fields

    def is_on_service(self, service: ServiceType) -> bool:
        return any(uri.service == service for uri in self.uris)

    def find_uri(self, service: ServiceType) -> Optional[TrackURIs]:
        for uri in self.uris:
            if uri.service == service:
                return uri
        return None
