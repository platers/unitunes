from pathlib import Path
from typing import Optional
import typer

from unitunes.cli.utils import get_playlist_manager, print_grid
from unitunes.services.services import UserPlaylistPullable
from unitunes.types import ServiceType

from rich.console import Console
from rich.table import Table

service_app = typer.Typer(no_args_is_help=True)

console = Console()


@service_app.command()
def add(
    service_type: ServiceType = typer.Argument(None, help="Service to add."),
    service_config_path: str = typer.Argument(None, help="Path to service config."),
    service_name: Optional[str] = typer.Argument(
        None, help="Name of service. Defaults to service type."
    ),
) -> None:
    """
    Add a service.

    If no namm is provided, the service type will be used as the name.
    """

    pm = get_playlist_manager(Path.cwd())
    if not service_name:
        service_name = service_type.value
    assert service_name
    try:
        pm.add_service(service_type, Path(service_config_path), service_name)
    except ValueError as e:
        console.print(f"Service with name {service_name} already exists")
        raise typer.Exit(1)
    typer.echo(f"Added {service_type.value, service_config_path}")


@service_app.command()
def list(plain: bool = False) -> None:
    """List all services."""

    pm = get_playlist_manager(Path.cwd())
    grid = [[s.name, s.service, s.config_path] for s in pm.config.services.values()]
    print_grid(
        "Services", headers=["Name", "Service", "Config Path"], rows=grid, plain=plain
    )


@service_app.command()
def remove(
    service_name: str, force: Optional[bool] = typer.Option(False, "--force", "-f")
) -> None:
    """Remove a service."""

    pm = get_playlist_manager(Path.cwd())
    if service_name not in pm.config.services:
        console.print(f"Service with name {service_name} does not exist")
        raise typer.Exit(1)

    if not force:
        typer.confirm(
            f"Are you sure you want to remove service{service_name}? This will remove {service_name} from all playlists.",
            abort=True,
        )
    pm.remove_service(service_name)
    typer.echo(f"Removed {service_name}")


@service_app.command()
def playlists(service_name: str) -> None:
    """List all user playlists on a service."""

    pm = get_playlist_manager(Path.cwd())
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
