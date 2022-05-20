from typing import (
    Dict,
    List,
    Optional,
)
from pydantic import BaseModel
from unitunes.matcher import MatcherStrategy
from unitunes.track import Track
from unitunes.types import ServiceType
from unitunes.uri import PlaylistURIs


class PlaylistMetadata(BaseModel):
    name: str
    description: str
    uri: PlaylistURIs


class Playlist(BaseModel):
    name: str
    description: str = ""
    uris: Dict[str, List[PlaylistURIs]] = {}
    tracks: List[Track] = []

    def __rich__(self):
        s = f"[b]{self.name}[/b]\n"
        s += f"Description: {self.description}\n"
        if self.uris:
            for service_name, uris in self.uris.items():
                s += f"{service_name}: "
                for uri in uris:
                    s += f"{uri.url} "
        if self.tracks:
            joined = "\n".join(track.__rich__() for track in self.tracks)
            s += f"\nTracks:\n{joined}"

        return s

    def add_uri(self, service_name: str, uri: PlaylistURIs) -> None:
        if service_name not in self.uris:
            self.uris[service_name] = []
        self.uris[service_name].append(uri)

    def remove_uri(self, service_name: str, uri: PlaylistURIs) -> None:
        self.uris[service_name].remove(uri)
        if not self.uris[service_name]:
            del self.uris[service_name]

    def remove_service(self, service_name: str) -> None:
        del self.uris[service_name]

    def contains_uri(self, uri: PlaylistURIs) -> bool:
        for service_name, uris in self.uris.items():
            if uri in uris:
                return True
        return False

    def merge_track(self, track: Track, matcher: MatcherStrategy) -> None:
        for t in self.tracks:
            if matcher.are_same(t, track):
                t.merge(track)
                return

        self.tracks.append(track)

    def merge_playlist(self, playlist: "Playlist", matcher: MatcherStrategy) -> None:
        """Merges another playlist into this one."""

        def merge_uris():
            for service_name, uris in playlist.uris.items():
                if service_name not in self.uris:
                    self.uris[service_name] = []
                for uri in uris:
                    if uri not in self.uris[service_name]:
                        self.uris[service_name].append(uri)

        merge_uris()

        for track in playlist.tracks:
            self.merge_track(track, matcher)
