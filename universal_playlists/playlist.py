from typing import (
    List,
)
from pydantic import BaseModel
from universal_playlists.track import Track
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

    def merge_metadata(self, metadata: PlaylistMetadata) -> None:
        self.name = self.name or metadata.name
        self.description = self.description or metadata.description
        if metadata.uri not in self.uris:
            self.uris.append(metadata.uri)
