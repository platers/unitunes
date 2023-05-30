from pydantic import BaseModel
from typing import Dict, List

from unitunes.common_types import ServiceType


class IndexServiceEntry(BaseModel):
    name: str
    service: ServiceType
    config_path: str


class Index(BaseModel):
    """
    The index stores the services and playlists tracked by unitunes.
    """

    services: Dict[str, IndexServiceEntry] = {}
    playlists: List[str] = []

    def add_playlist(self, playlist_id: str):
        if playlist_id in self.playlists:
            raise ValueError(f"Playlist {playlist_id} already exists")
        self.playlists.append(playlist_id)

    def add_service(self, name: str, service: ServiceType, config_path: str):
        if name in self.services:
            raise ValueError(f"Service {name} already exists")
        self.services[name] = IndexServiceEntry(
            name=name, service=service, config_path=config_path
        )

    def remove_service(self, name: str):
        if name not in self.services:
            raise ValueError(f"Service {name} does not exist")
        del self.services[name]

    def remove_playlist(self, name: str):
        if name not in self.playlists:
            raise ValueError(f"Playlist {name} does not exist")
        self.playlists.remove(name)
