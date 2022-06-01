from pydantic import BaseModel
from typing import Dict, List


class IndexServiceEntry(BaseModel):
    name: str
    service: str
    index_path: str


class Index(BaseModel):
    """
    The index stores the services and playlists tracked by unitunes.
    """

    services: Dict[str, IndexServiceEntry] = {}
    playlists: List[str] = []

    def add_playlist(self, name: str):
        if name in self.playlists:
            raise ValueError(f"Playlist {name} already exists")
        self.playlists.append(name)

    def add_service(self, name: str, service: str, index_path: str):
        if name in self.services:
            raise ValueError(f"Service {name} already exists")
        self.services[name] = IndexServiceEntry(
            name=name, service=service, index_path=index_path
        )

    def remove_service(self, name: str):
        if name not in self.services:
            raise ValueError(f"Service {name} does not exist")
        del self.services[name]

    def remove_playlist(self, name: str):
        if name not in self.playlists:
            raise ValueError(f"Playlist {name} does not exist")
        self.playlists.remove(name)
