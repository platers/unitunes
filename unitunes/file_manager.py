import json
from pathlib import Path
import string

from unitunes.index import Index
from unitunes.playlist import Playlist
from unitunes.services.services import ServiceConfig


def format_filename(s):
    """Take a string and return a valid filename constructed from the string.
    Uses a whitelist approach: any characters not present in valid_chars are
    removed. Also spaces are replaced with underscores.
    Source: https://gist.github.com/seanh/93666
    """
    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    filename = "".join(c for c in s if c in valid_chars)
    filename = filename.replace(" ", "_")
    return filename


class FileManager:
    dir: Path
    index_path: Path
    playlist_folder: Path
    cache_path: Path
    service_configs_path: Path

    def __init__(self, dir: Path) -> None:
        self.dir = dir
        self.index_path = dir / "index.json"
        self.playlist_folder = dir / "playlists"
        self.cache_path = dir / "cache"
        self.service_configs_path = dir / "service_configs"

    def get_playlist_path(self, name: str) -> Path:
        return self.playlist_folder / f"{format_filename(name)}.json"

    def save_index(self, index: Index) -> None:
        with open(self.index_path, "w") as f:
            f.write(index.json(indent=4))

    def load_index(self) -> Index:
        if not self.index_path.exists():
            raise FileNotFoundError(f"index file not found: {self.index_path}")
        return Index.parse_file(self.index_path)

    def save_playlist(self, playlist: Playlist, playlist_id: str) -> None:
        self.playlist_folder.mkdir(exist_ok=True)
        with open(self.get_playlist_path(playlist_id), "w") as f:
            f.write(playlist.json(indent=4))

    def load_playlist(self, name: str) -> Playlist:
        path = self.get_playlist_path(name)
        if not path.exists():
            raise FileNotFoundError(f"Playlist file not found: {path}")
        return Playlist.parse_file(path)

    def delete_playlist(self, name: str) -> None:
        path = self.get_playlist_path(name)
        if not path.exists():
            raise FileNotFoundError(f"Playlist file not found: {path}")
        path.unlink()

    def service_config_path(self, service_name: str) -> Path:
        return (
            self.service_configs_path / f"{format_filename(service_name)}_config.json"
        )

    def save_service_config(self, service_name: str, config: ServiceConfig) -> None:
        self.service_configs_path.mkdir(exist_ok=True)
        path = self.service_config_path(service_name)
        with open(path, "w") as f:
            f.write(config.json(indent=4))

    def delete_service_config(self, service_name: str) -> None:
        path = self.service_config_path(service_name)
        if not path.exists():
            raise FileNotFoundError(f"Service config file not found: {path}")
        path.unlink()
