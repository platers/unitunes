import json
import string
from typing import Dict, List, Optional
from pathlib import Path
from pydantic import BaseModel
from unitunes.matcher import MatcherStrategy
from unitunes.playlist import Playlist
from unitunes.searcher import SearcherStrategy
from unitunes.services.musicbrainz import MusicBrainz, MusicBrainzWrapper
from unitunes.services.services import (
    Searchable,
    StreamingService,
    TrackPullable,
)


from unitunes.services.spotify import (
    SpotifyAPIWrapper,
    SpotifyService,
)
from unitunes.services.ytm import YTM, YtmAPIWrapper
from unitunes.track import Track
from unitunes.types import ServiceType
from unitunes.uri import PlaylistURIs, TrackURI


class ConfigServiceEntry(BaseModel):
    name: str
    service: str
    config_path: str


class Config(BaseModel):
    services: Dict[str, ConfigServiceEntry] = {}
    playlists: List[str] = []

    def add_playlist(self, name: str):
        if name in self.playlists:
            raise ValueError(f"Playlist {name} already exists")
        self.playlists.append(name)

    def add_service(self, name: str, service: str, config_path: str):
        if name in self.services:
            raise ValueError(f"Service {name} already exists")
        self.services[name] = ConfigServiceEntry(
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


def service_factory(
    service_type: ServiceType,
    name: str,
    cache_path: Path,
    config_path: Optional[Path] = None,
) -> StreamingService:

    if service_type == ServiceType.SPOTIFY:
        assert config_path is not None
        config = json.load(config_path.open())
        return SpotifyService(name, SpotifyAPIWrapper(config, cache_path))
    elif service_type == ServiceType.YTM:
        assert config_path is not None
        return YTM(name, YtmAPIWrapper(config_path, cache_path))
    elif service_type == ServiceType.MB:
        return MusicBrainz(MusicBrainzWrapper(cache_path))
    else:
        raise ValueError(f"Unknown service type: {service_type}")


class FileManager:
    dir: Path
    config_path: Path
    playlist_folder: Path
    cache_path: Path

    def __init__(self, dir: Path) -> None:
        self.dir = dir
        self.config_path = dir / "config.json"
        self.playlist_folder = dir / "playlists"
        self.cache_path = dir / "cache"

    def get_playlist_path(self, name: str) -> Path:
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

        return self.playlist_folder / f"{format_filename(name)}.json"

    def make_playlist_dir(self) -> None:
        self.playlist_folder.mkdir(exist_ok=True)

    def save_config(self, config: Config) -> None:
        with open(self.config_path, "w") as f:
            f.write(config.json(indent=4))

    def load_config(self) -> Config:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        return Config.parse_file(self.config_path)

    def save_playlist(self, playlist: Playlist) -> None:
        with open(self.get_playlist_path(playlist.name), "w") as f:
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


class PlaylistManager:
    config: Config
    file_manager: FileManager
    playlists: Dict[str, Playlist]
    services: Dict[str, StreamingService]

    def __init__(self, config: Config, file_manager: FileManager) -> None:
        self.config = config
        self.file_manager = file_manager
        self.playlists = {}
        self.services = {}

        self.load_services()

        # create playlist objects
        for name in self.config.playlists:
            self.playlists[name] = self.file_manager.load_playlist(name)

    def load_services(self) -> None:
        self.services[ServiceType.MB.value] = service_factory(
            ServiceType.MB,
            "MusicBrainz",
            cache_path=self.file_manager.cache_path,
        )
        for s in self.config.services.values():
            service_config_path = Path(s.config_path)
            self.services[s.name] = service_factory(
                ServiceType(s.service),
                s.name,
                config_path=service_config_path,
                cache_path=self.file_manager.cache_path,
            )

    def add_service(
        self, service: ServiceType, service_config_path: Path, name: str
    ) -> None:
        self.config.add_service(name, service.value, service_config_path.as_posix())
        self.load_services()
        self.file_manager.save_config(self.config)

    def remove_service(self, name: str) -> None:
        if name not in self.config.services:
            raise ValueError(f"Service {name} not found")
        self.config.remove_service(name)

        for playlist in self.playlists.values():
            playlist.remove_service(name)
            self.file_manager.save_playlist(playlist)

        self.file_manager.save_config(self.config)

    def add_playlist(self, name: str) -> None:
        """Initialize a UP. Raise ValueError if the playlist already exists."""
        self.config.add_playlist(name)
        self.playlists[name] = Playlist(name=name)
        self.file_manager.save_config(self.config)
        self.file_manager.save_playlist(self.playlists[name])

    def remove_playlist(self, name: str) -> None:
        """Remove a playlist from the config and filesystem."""
        if name not in self.config.playlists:
            raise ValueError(f"Playlist {name} not found")
        self.file_manager.delete_playlist(name)
        del self.playlists[name]
        self.config.remove_playlist(name)
        self.file_manager.save_config(self.config)

    def add_uri_to_playlist(
        self, playlist_name: str, service_name: str, uri: PlaylistURIs
    ) -> None:
        """Link a playlist URI to a UP. UP must exist."""
        pl = self.playlists[playlist_name]
        pl.add_uri(service_name, uri)

        self.file_manager.save_config(self.config)
        self.file_manager.save_playlist(pl)

    def save_playlist(self, playlist_name: str) -> None:
        self.file_manager.save_playlist(self.playlists[playlist_name])

    def is_tracking_playlist(self, uri: PlaylistURIs) -> bool:
        for playlist in self.playlists.values():
            for uris in playlist.uris.values():
                if uri in uris:
                    return True
        return False


def get_predicted_tracks(
    target_service: StreamingService,
    track: Track,
    searcher: SearcherStrategy,
) -> List[Track]:
    if not isinstance(target_service, Searchable):
        raise ValueError(f"Service {target_service.name} is not searchable")

    return searcher.search(target_service, track)


def get_prediction_track(
    target_service: StreamingService,
    track: Track,
    matcher: MatcherStrategy,
    searcher: SearcherStrategy,
    threshold: float = 0.8,
) -> Optional[Track]:
    matches = get_predicted_tracks(target_service, track, searcher)
    if len(matches) == 0:
        return None
    best_match = matches[0]

    if matcher.similarity(track, best_match) >= threshold:
        return best_match
    return None


def get_prediction_uri(
    source_service: StreamingService,
    target_service: StreamingService,
    uri: TrackURI,
    matcher: MatcherStrategy,
    searcher: SearcherStrategy,
    threshold: float = 0.8,
) -> Optional[TrackURI]:
    if not isinstance(source_service, TrackPullable):
        raise ValueError(f"Service {source_service} is not pullable")
    track = source_service.pull_track(uri)
    prediction = get_prediction_track(
        target_service, track, matcher, searcher, threshold
    )
    return prediction.uris[0] if prediction else None
