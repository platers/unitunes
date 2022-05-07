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

    def is_linked_to_service(self, service_name: str) -> bool:
        for uri in self.uris:
            if uri.service == service_name:
                return True
        return False

    def find_track_with_uri(self, track: Track) -> Optional[Track]:
        for t in self.tracks:
            if t.uri_matches(track):
                return t
        return None

    def find_matching_track(self, track: Track) -> Optional[Track]:
        for t in self.tracks:
            if t.matches(track):
                return t
        return None

    def merge_new_tracks(self, new_tracks: List[Track]) -> None:
        for track in new_tracks:
            match = self.find_matching_track(track)
            if match is None:
                self.tracks.append(track)
            else:
                match.merge(track)

    def remove_tracks(self, tracks: List[Track]) -> None:
        self.tracks = [track for track in self.tracks if track not in tracks]

    def tracks_on_service(self, service: ServiceType) -> List[Track]:
        return [track for track in self.tracks if track.is_on_service(service)]

    def get_new_tracks(self, remote_tracks: List[Track]) -> List[Track]:
        """Get tracks from a service whose URIs are not in the playlist"""
        new_tracks = [r for r in remote_tracks if not self.find_track_with_uri(r)]
        return new_tracks

    def get_removed_tracks(
        self, service: ServiceType, remote_tracks: List[Track]
    ) -> List[Track]:
        """Get tracks from a service whose URIs are not in the playlist"""
        tracks_on_service = self.tracks_on_service(service)
        removed_tracks = [
            r
            for r in tracks_on_service
            if not any(r.uri_matches(t) for t in remote_tracks)
        ]
        return removed_tracks
