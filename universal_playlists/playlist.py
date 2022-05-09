from typing import (
    List,
    Optional,
)
from pydantic import BaseModel
from universal_playlists.track import Track
from universal_playlists.types import ServiceType
from universal_playlists.uri import PlaylistURIs


class PlaylistMetadata(BaseModel):
    name: str
    description: str
    uri: PlaylistURIs


class Playlist(BaseModel):
    name: str
    description: str = ""
    uris: List[PlaylistURIs] = []
    tracks: List[Track] = []

    def __rich__(self):
        s = f"[b]{self.name}[/b]\n"
        s += f"Description: {self.description}\n"
        if self.uris:
            s += f"\nURIs: {', '.join(uri.__rich__() for uri in self.uris)}"
        if self.tracks:
            joined = "\n".join(track.__rich__() for track in self.tracks)
            s += f"\nTracks:\n{joined}"

        return s

    def merge_metadata(self, metadata: PlaylistMetadata) -> None:
        self.name = self.name or metadata.name
        self.description = self.description or metadata.description
        if metadata.uri not in self.uris:
            self.uris.append(metadata.uri)

    def find_uri(self, service: ServiceType) -> Optional[PlaylistURIs]:
        for uri in self.uris:
            if uri.service == service:
                return uri
        return None

    def add_uri(self, uri: PlaylistURIs) -> None:
        if uri not in self.uris:
            self.uris.append(uri)
