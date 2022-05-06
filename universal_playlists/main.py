from curses import wrapper
import json
from typing import Dict, List, Optional
import pandas as pd
from pathlib import Path
import os
from pydantic import BaseModel
from universal_playlists.playlist import Playlist
from universal_playlists.services.musicbrainz import MusicBrainz
from universal_playlists.services.services import StreamingService


from universal_playlists.services.spotify import SpotifyService, SpotifyWrapper
from universal_playlists.services.ytm import YTM, YtmWrapper
from universal_playlists.track import Track
from universal_playlists.types import ServiceType
from universal_playlists.uri import PlaylistURIs, TrackURI


class ConfigServiceEntry(BaseModel):
    name: str
    service: str
    config_path: str


class UPRelations(BaseModel):
    uris: List[PlaylistURIs] = []

    def add_uri(self, uri: PlaylistURIs):
        if uri not in self.uris:
            self.uris.append(uri)


class Config(BaseModel):
    services: Dict[str, ConfigServiceEntry] = {}
    playlists: Dict[str, UPRelations] = {}

    def add_playlist(self, name: str, uris: List[PlaylistURIs] = []):
        if name in self.playlists:
            for uri in uris:
                self.playlists[name].add_uri(uri)
        else:
            self.playlists[name] = UPRelations(uris=uris)

    def playlist_names(self) -> List[str]:
        return list(self.playlists.keys())


def service_factory(
    service_type: ServiceType,
    name: str,
    cache_path: Path,
    config_path: Optional[Path] = None,
) -> StreamingService:

    if service_type == ServiceType.SPOTIFY:
        assert config_path is not None
        config = json.load(config_path.open())
        return SpotifyService(name, SpotifyWrapper(config, cache_path))
    elif service_type == ServiceType.YTM:
        assert config_path is not None
        return YTM(name, YtmWrapper(config_path, cache_path))
    elif service_type == ServiceType.MB:
        return MusicBrainz()
    else:
        raise ValueError(f"Unknown service type: {service_type}")


class FileManager:
    dir: Path
    config_path = Path("config.json")
    playlist_folder = Path("playlists")
    cache_path = Path("cache")

    def __init__(self, dir: Path) -> None:
        self.dir = dir
        os.chdir(self.dir)

    def get_playlist_path(self, name: str) -> Path:
        return self.playlist_folder / f"{name}.json"

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


class PlaylistManager:
    config: Config
    file_manager: FileManager
    playlists: Dict[str, Playlist]
    services: Dict[str, StreamingService] = {}

    def __init__(self, config: Config, file_manager: FileManager) -> None:
        self.config = config
        self.file_manager = file_manager

        # create service objects
        self.services[ServiceType.MB.value] = MusicBrainz()
        for s in self.config.services.values():
            service_config_path = Path(s.config_path)
            self.services[s.name] = service_factory(
                ServiceType(s.service),
                s.name,
                config_path=service_config_path,
                cache_path=self.file_manager.cache_path,
            )

        # create playlist objects
        self.playlists: Dict[str, Playlist] = {}
        names = self.config.playlist_names()
        for name in names:
            self.playlists[name] = self.file_manager.load_playlist(name)

    def add_service(
        self, service: ServiceType, service_config_path: Path, name=""
    ) -> None:
        if name == "":
            name = service.value
            # check if service is already in config
            for s in self.config.services.values():
                if s.service == service.value:
                    name = service.value + " " + service_config_path.name

        self.config.services[name] = ConfigServiceEntry(
            name=name,
            service=service.value,
            config_path=service_config_path.__str__(),
        )

        self.file_manager.save_config(self.config)

    def add_playlist(self, name: str, uris: List[PlaylistURIs]) -> None:
        self.config.add_playlist(name, uris)
        self.playlists[name] = Playlist(name=name, uris=uris)
        self.file_manager.save_config(self.config)
        self.file_manager.save_playlist(self.playlists[name])

    def add_uris_to_playlist(
        self, playlist_name: str, uris: List[PlaylistURIs]
    ) -> None:
        self.config.add_playlist(playlist_name, uris)
        pl = self.playlists[playlist_name]
        for uri in uris:
            pl.add_uri(uri)

        self.file_manager.save_config(self.config)
        self.file_manager.save_playlist(pl)

    def save_playlist(self, playlist_name: str) -> None:
        self.file_manager.save_playlist(self.playlists[playlist_name])


def get_predicted_tracks(
    target_service: StreamingService,
    track: Track,
) -> List[Track]:
    matches = target_service.search_track(track)
    if len(matches) == 0:
        return []
    # sort by score
    matches.sort(key=lambda m: m.similarity(track), reverse=True)
    return matches


def get_prediction_track(
    target_service: StreamingService,
    track: Track,
    threshold: float = 0.8,
) -> Optional[Track]:
    matches = get_predicted_tracks(target_service, track)
    if len(matches) == 0:
        return None
    best_match = matches[0]

    if best_match.similarity(track) < threshold:
        return None

    return best_match


def get_prediction_uri(
    source_service: StreamingService,
    target_service: StreamingService,
    uri: TrackURI,
    threshold: float = 0.8,
) -> Optional[TrackURI]:
    track = source_service.pull_track(uri)
    prediction = get_prediction_track(target_service, track, threshold)
    return prediction.uris[0] if prediction else None


def augment_track(track: Track):
    """Tries to find metadata from musicbrainz. Adds metadata to track if found."""
    mb = MusicBrainz()
    match = mb.best_match(track)
    if match and track.matches(match):
        track.merge(match)
