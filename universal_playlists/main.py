from typing import Dict, List, Optional
import pandas as pd
from pathlib import Path
import os
from pydantic import BaseModel
from universal_playlists.playlist import Playlist
from universal_playlists.services.musicbrainz import MusicBrainz
from universal_playlists.services.services import StreamingService


from universal_playlists.services.spotify import SpotifyService
from universal_playlists.services.ytm import YTM
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
    services: List[ConfigServiceEntry] = []
    playlists: Dict[str, UPRelations] = {}

    def add_playlist(self, name: str, uris: List[PlaylistURIs] = []):
        if name in self.playlists:
            for uri in uris:
                self.playlists[name].add_uri(uri)
        self.playlists[name] = UPRelations(uris=uris)

    def playlist_names(self) -> List[str]:
        return list(self.playlists.keys())


def service_factory(
    service_type: ServiceType,
    name: str,
    config_path: Path,
) -> StreamingService:
    if service_type == ServiceType.SPOTIFY:
        return SpotifyService(name, config_path)
    elif service_type == ServiceType.YTM:
        return YTM(name, config_path)
    elif service_type == ServiceType.MB:
        return MusicBrainz()
    else:
        raise ValueError(f"Unknown service type: {service_type}")


class FileManager:
    dir: Path
    config_path = Path("config.json")
    playlist_folder = Path("playlists")

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

    def __init__(self, config: Config, file_manager: FileManager) -> None:
        self.config = config
        self.file_manager = file_manager

        # create service objects
        self.services: Dict[str, StreamingService] = {}
        self.services[ServiceType.MB.value] = MusicBrainz()
        for s in self.config.services:
            service_config_path = Path(s.config_path)
            self.services[s.name] = service_factory(
                ServiceType(s.service), s.name, config_path=service_config_path
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
            for s in self.config.services:
                if s.service == service.value:
                    name = service.value + " " + service_config_path.name

        self.config.services.append(
            ConfigServiceEntry(
                name=name,
                service=service.value,
                config_path=service_config_path.__str__(),
            )
        )

        self.file_manager.save_config(self.config)

    def add_playlist(self, name: str, uris: List[PlaylistURIs]) -> None:
        self.config.add_playlist(name, uris)
        self.playlists[name] = Playlist(name=name)
        self.file_manager.save_config(self.config)
        self.file_manager.save_playlist(self.playlists[name])

    def pull_tracks(self, playlist_name: str) -> None:
        if playlist_name not in self.playlists:
            raise ValueError("Playlist not found")

        playlist = self.playlists[playlist_name]
        for uri in playlist.uris:
            service = self.services[uri.service]
            tracks = service.pull_tracks(uri)

            # merge tracks into playlist
            for track in tracks:
                matches = [t for t in playlist.tracks if t.matches(track)]
                if matches:
                    assert len(matches) == 1  # TODO: handle multiple matches
                    matches[0].merge(track)
                else:
                    playlist.tracks.append(track)

        self.file_manager.save_playlist(playlist)


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
