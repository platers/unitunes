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
from universal_playlists.uri import TrackURI


class ConfigServiceEntry(BaseModel):
    name: str
    service: str
    config_path: str


class Config(BaseModel):
    dir: Path
    services: List[ConfigServiceEntry] = []


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


class PlaylistManager:
    def __init__(
        self, config_path=Path("config.json"), table_path=Path("playlists.csv")
    ) -> None:
        self.config_path = config_path
        if not self.config_path.exists():
            raise ValueError(f"Config file not found at {self.config_path}")

        self.config = Config.parse_file(self.config_path)
        os.chdir(self.config.dir)

        self.table_path = table_path
        self.playlist_table = self.create_playlist_table()

        # create playlist directory
        Path("./playlists").mkdir(exist_ok=True)

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
        for i, row in self.playlist_table.iterrows():
            name = row["Unified Playlist"]
            if type(name) == str:
                path = self.playlist_path(name)
                if path.exists():
                    self.playlists[name] = Playlist.parse_file(self.playlist_path(name))

    @staticmethod
    def create_config(dir: Path) -> None:
        config = Config(dir=dir)
        os.chdir(config.dir)
        if Path("config.json").exists():
            raise FileExistsError("Config file already exists")

        with Path("config.json").open("w") as f:
            f.write(config.json(indent=4))

    def playlist_path(self, playlist_name: str) -> Path:
        return Path("./playlists") / (playlist_name + ".json")

    def create_playlist_table(self) -> pd.DataFrame:
        if self.table_path.exists():
            return pd.read_csv(self.table_path)

        # create a csv. headers are services
        headers = ["Unified Playlist"] + [s.name for s in self.config.services]
        table = pd.DataFrame(columns=headers)
        # add empty row
        table.loc[0] = [""] * len(headers)  # type: ignore

        table.to_csv(self.table_path, index=False)
        return table

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
        with self.config_path.open("w") as f:
            f.write(self.config.json(indent=4))

        # add service to table header
        table_path = Path("playlists.csv")
        if table_path.exists():
            table = pd.read_csv(table_path)
            table.insert(len(table.columns), name, "")
            table.to_csv(table_path, index=False)
        else:
            self.create_playlist_table()

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

        # save playlist
        with self.playlist_path(playlist_name).open("w") as f:
            f.write(playlist.json(indent=4))


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
