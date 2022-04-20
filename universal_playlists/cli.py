import typer
from universal_playlists.main import PlaylistManager
from typing import Dict, List, Optional
from pathlib import Path
from pydantic import BaseModel

from universal_playlists.services.services import Playlist, ServiceType

app = typer.Typer()

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
            s.service == ServiceType[service].value
            and s.config_path == service_config_path
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
            playlist = Playlist(name=name)
            with playlist_config_path.open("w") as f:
                f.write(playlist.json(indent=4))
        else:
            playlist = Playlist.parse_file(playlist_config_path)

        for service_name, service in pm.services.items():
            if type(row[service_name]) is not str:
                continue
            metadata = service.get_playlist_metadata(row[service_name])
            playlist.merge_metadata(metadata)

            with playlist_config_path.open("w") as f:
                print(playlist)
                f.write(playlist.json(indent=4))

    typer.echo("Done")


@app.command()
def pull_tracks(playlist_name: str) -> None:
    """Pull tracks from services and merge into Unified Playlist"""
    pm.pull_tracks(playlist_name)
