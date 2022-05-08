from pathlib import Path
from typing import List, Optional
import typer

from universal_playlists.cli.utils import get_playlist_manager
from universal_playlists.services.services import UserPlaylistPullable
from universal_playlists.types import ServiceType

from rich.console import Console
from rich.table import Table

service_app = typer.Typer()

console = Console()


@service_app.command()
def add(
    service: ServiceType,
    service_config_path: str,
    name: Optional[str] = typer.Argument(None),
) -> None:
    """Add a service to the config file"""

    pm = get_playlist_manager()
    # check if service is already added
    for s in pm.config.services.values():
        if s.service == service.value and s.config_path == service_config_path:
            typer.echo(f"{service.value, service_config_path} is already added")
            return

    if not name:
        name = ""
    pm.add_service(service, Path(service_config_path), name)
    typer.echo(f"Added {service.value, service_config_path}")


@service_app.command()
def list() -> None:
    """List all services"""

    pm = get_playlist_manager()
    table = Table(title="Services")
    table.add_column("Name", justify="left")
    table.add_column("Service", justify="left")
    table.add_column("Config Path", justify="left")
    for s in pm.config.services.values():
        table.add_row(s.name, s.service, s.config_path)
    console.print(table)


@service_app.command()
def remove(name: str) -> None:
    """Remove a service from the config file"""
    raise NotImplementedError  # TODO


@service_app.command()
def playlists(service_name: str) -> None:
    """List all user playlists on a service"""

    pm = get_playlist_manager()
    service = pm.services[service_name]
    if not isinstance(service, UserPlaylistPullable):
        console.print(f"Cannot fetch user playlists from {service.type}", style="red")
        raise typer.Exit()

    playlists = service.get_playlist_metadatas()

    table = Table(title="Playlists")
    table.add_column("Name", justify="left")
    table.add_column(
        "Description",
        justify="left",
    )
    table.add_column("URL", justify="left", no_wrap=True)

    for pl in playlists:
        table.add_row(pl.name, pl.description, pl.uri.url)
    console.print(table)
