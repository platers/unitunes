from typing import (
    List,
    Optional,
)
from pydantic import BaseModel
from universal_playlists.track import Track
from universal_playlists.uri import PlaylistURIs, TrackURIs


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

    def find_uri(self, service_name: str) -> PlaylistURIs:
        for uri in self.uris:
            if uri.service == service_name:
                return uri
        raise ValueError(f"URI for service {service_name} not found")

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

    def tracks_on_service(self, service_name: str) -> List[Track]:
        return [track for track in self.tracks if track.is_on_service(service_name)]

    def get_new_tracks(self, remote_tracks: List[Track]) -> List[Track]:
        """Get tracks from a service whose URIs are not in the playlist"""
        new_tracks = [r for r in remote_tracks if not self.find_track_with_uri(r)]
        return new_tracks

    def get_removed_tracks(
        self, service_name: str, remote_tracks: List[Track]
    ) -> List[Track]:
        """Get tracks from a service whose URIs are not in the playlist"""
        tracks_on_service = self.tracks_on_service(service_name)
        removed_tracks = [r for r in tracks_on_service if r not in remote_tracks]
        return removed_tracks
