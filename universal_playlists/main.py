import json
from typing import Dict, List, NewType, Optional, TypedDict
import typer
import pandas as pd
from pathlib import Path
import os


from universal_playlists.services.services import (
    MusicBrainz,
    Playlist,
    ServiceType,
    StreamingService,
    Track,
)

app = typer.Typer()


class ConfigServiceEntry(TypedDict):
    name: str
    service: str
    config_path: str


class Config:
    def __init__(self, dir=Path(__file__).parent, services=[]):
        self.dir = dir
        self.services: List[ConfigServiceEntry] = services

    @staticmethod
    def from_file(path: Path) -> "Config":
        with path.open("r") as f:
            j = json.loads(f.read())
            return Config(Path(j["dir"]), j["services"])

    def to_file(self, path: Path) -> None:
        j = {"dir": self.dir.__str__(), "services": self.services}
        with path.open("w") as f:
            json.dump(j, f, indent=4)


class PlaylistManager:
    def __init__(
        self, config_path=Path("config.json"), table_path=Path("playlists.csv")
    ) -> None:
        self.config_path = config_path
        if not self.config_path.exists():
            self.config = Config()
            self.config.to_file(self.config_path)

        self.config = Config.from_file(self.config_path)
        os.chdir(self.config.dir)

        self.table_path = table_path
        self.create_playlist_table()
        self.playlist_table = pd.read_csv(self.table_path)

        self.services: Dict[str, StreamingService] = {}
        for s in self.config.services:
            service_config_path = Path(s["config_path"])
            self.services[s["name"]] = StreamingService.service_builder(
                ServiceType(s["service"]), s["name"], service_config_path
            )

        self.playlists: Dict[str, Playlist] = {}
        for i, row in self.playlist_table.iterrows():
            name = row["Unified Playlist"]
            if type(name) == str:
                path = self.playlist_path(name)
                if path.exists():
                    self.playlists[name] = Playlist.from_file(self.playlist_path(name))

    def playlist_path(self, playlist_name: str) -> Path:
        return Path("./playlists") / (playlist_name + ".json")

    def create_playlist_table(self) -> bool:
        if self.table_path.exists():
            return False

        # create a csv. headers are services
        headers = ["Unified Playlist"] + [s["name"] for s in self.config.services]
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
                if s["service"] == service.value:
                    name = service.value + " " + service_config_path.name

        self.config.services.append(
            {
                "name": name,
                "service": service.value,
                "config_path": service_config_path.__str__(),
            }
        )
        self.config.to_file(self.config_path)

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

        playlist.to_file(self.playlist_path(playlist_name))


pm = PlaylistManager()


@app.command()
def add_service(
    service: str, service_config_path: str, name: Optional[str] = typer.Argument(None)
) -> None:
    """Add a service to the config file"""
    # check if service name is valid
    service = service.upper()
    if service not in ServiceType.__members__:
        typer.echo(f"{service} is not a valid service")
        typer.echo(f"Valid services: {', '.join(ServiceType.__members__.keys())}")
        return

    # check if service is already added
    for s in pm.config.services:
        if (
            s["service"] == ServiceType[service].value
            and s["config_path"] == service_config_path
        ):
            typer.echo(
                f"{ServiceType[service].value, service_config_path} is already added"
            )
            return

    if not name:
        name = ""
    pm.add_service(ServiceType[service], Path(service_config_path), name)
    typer.echo(f"Added {ServiceType[service].value, service_config_path}")


@app.command()
def create_playlist_table() -> None:
    """Create a csv file with the playlists"""
    if not pm.create_playlist_table():
        typer.echo(f"playlists.csv already exists")


@app.command()
def pull_metadata() -> None:
    """Pull playlists from services"""
    # loop rows of table after header
    for i, row in pm.playlist_table.iterrows():  # type: ignore
        name = row["Unified Playlist"]
        if type(name) is not str:
            continue
        playlist_config_path = Path("./playlists") / (name + ".json")
        if not playlist_config_path.exists():
            playlist = Playlist(name, playlist_config_path=playlist_config_path)
            playlist.to_file(playlist_config_path)
        else:
            playlist = Playlist.from_file(playlist_config_path)

        for service_name, service in pm.services.items():
            if type(row[service_name]) is not str:
                continue
            metadata = service.get_playlist_metadata(row[service_name])
            playlist.merge_metadata(metadata)

    typer.echo("Done")


@app.command()
def pull_tracks(playlist_name: str) -> None:
    """Pull tracks from services and merge into Unified Playlist"""
    pm.pull_tracks(playlist_name)
