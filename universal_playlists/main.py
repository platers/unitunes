import json
from typing import Dict, List, Optional
import pandas as pd
from pathlib import Path
import os
from pydantic import BaseModel
from universal_playlists.services.musicbrainz import MusicBrainz


from universal_playlists.services.services import (
    Playlist,
    ServiceType,
    StreamingService,
)
from universal_playlists.services.spotify import SpotifyService
from universal_playlists.services.ytm import YTM


class ConfigServiceEntry(BaseModel):
    name: str
    service: str
    config_path: str


class Config(BaseModel):
    dir: Path
    services: List[ConfigServiceEntry] = []


def service_builder(
    service_type: ServiceType,
    name: str,
    config_path: Path,
) -> "StreamingService":
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
            # ask user for confirmation
            print("Config file not found. Create new config?")
            if not input("[y/n] ").lower().startswith("y"):
                raise ValueError("No config file found")

            self.config = Config(dir=Path(os.getcwd()))
            os.chdir(self.config.dir)
            with self.config_path.open("w") as f:
                f.write(self.config.json(indent=4))

        self.config = Config.parse_file(self.config_path)
        os.chdir(self.config.dir)

        self.table_path = table_path
        self.create_playlist_table()
        self.playlist_table = pd.read_csv(self.table_path)
        # create playlist directory
        Path("./playlists").mkdir(exist_ok=True)

        self.services: Dict[str, StreamingService] = {}
        for s in self.config.services:
            service_config_path = Path(s.config_path)
            self.services[s.name] = service_builder(
                ServiceType(s.service), s.name, config_path=service_config_path
            )

        self.playlists: Dict[str, Playlist] = {}
        for i, row in self.playlist_table.iterrows():
            name = row["Unified Playlist"]
            if type(name) == str:
                path = self.playlist_path(name)
                if path.exists():
                    self.playlists[name] = Playlist.parse_file(self.playlist_path(name))

    def playlist_path(self, playlist_name: str) -> Path:
        return Path("./playlists") / (playlist_name + ".json")

    def create_playlist_table(self) -> bool:
        if self.table_path.exists():
            return False

        # create a csv. headers are services
        headers = ["Unified Playlist"] + [s.name for s in self.config.services]
        table = pd.DataFrame(columns=headers)
        # add empty row
        table.loc[0] = [""] * len(headers)  # type: ignore

        table.to_csv(self.table_path, index=False)

        return True

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
                if any(t.matches(track) for t in playlist.tracks):
                    if service.name == "youtube-music":
                        print(f"Track {track.name} already in playlist")
                    continue
                if service.name == "spotify":  # TODO: remove this
                    playlist.tracks.append(track)
                # print("Added track: " + track.name)

        # save playlist
        with self.playlist_path(playlist_name).open("w") as f:
            f.write(playlist.json(indent=4))
