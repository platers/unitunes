from typing import (
    List,
    Optional,
)
from pydantic import BaseModel
from unitunes.types import ServiceType
from unitunes.uri import TrackURIs


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

    def add_alias(self, alias: str) -> None:
        """Add an alias to the list of aliases if it doesn't already exist."""
        if alias not in self.all_values():
            self.aliases.append(alias)

    def shares_alias(self, other: "AliasedString") -> bool:
        return any(a in other.all_values() for a in self.all_values())

    def merge(self, other: "AliasedString") -> None:
        for alias in other.all_values():
            self.add_alias(alias)


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

    def shares_uri(self, track: "Track") -> bool:
        return any(uri in track.uris for uri in self.uris)

    def shared_uri(self, track: "Track") -> Optional[TrackURIs]:
        for uri in self.uris:
            if uri in track.uris:
                return uri
        return None

    def merge(self, other: "Track") -> None:
        def merge_aliased_str_into_list(
            astr: AliasedString, list_: List[AliasedString]
        ) -> None:
            for other_astr in list_:
                if astr.shares_alias(other_astr):
                    astr.merge(other_astr)
                    return
            list_.append(astr)

        def merge_albums(other_albums: List[AliasedString]) -> None:
            for other_album in other_albums:
                merge_aliased_str_into_list(other_album, self.albums)

        def merge_artists(other_artists: List[AliasedString]) -> None:
            for other_artist in other_artists:
                merge_aliased_str_into_list(other_artist, self.artists)

        def merge_uris(other_uris: List[TrackURIs]) -> None:
            for other_uri in other_uris:
                if other_uri not in self.uris:
                    self.uris.append(other_uri)

        def merge_length(other_length: Optional[int]) -> None:
            if other_length is not None and self.length is None:
                self.length = other_length

        merge_uris(other.uris)
        merge_albums(other.albums)
        merge_artists(other.artists)
        merge_length(other.length)

    def is_on_service(self, service: ServiceType) -> bool:
        return any(uri.service == service for uri in self.uris)

    def uris_on_service(self, service: ServiceType) -> List[TrackURIs]:
        return [uri for uri in self.uris if uri.service == service]

    def find_uri(self, service: ServiceType) -> Optional[TrackURIs]:
        for uri in self.uris:
            if uri.service == service:
                return uri
        return None
