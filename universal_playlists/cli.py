from tqdm import tqdm
import typer
from universal_playlists.main import (
    PlaylistManager,
    get_predicted_tracks,
    get_prediction_track,
)
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table

from universal_playlists.services.services import Playlist, ServiceType

console = Console()
app = typer.Typer(no_args_is_help=True)
service_app = typer.Typer()


@app.command()
def init(
    directory: Optional[Path] = typer.Argument(
        Path("."),
        help="Directory to store playlist files in",
    )
) -> None:
    """Initialize a new playlist manager"""
    if not directory:
        directory = Path(".")

    try:
        PlaylistManager.create_config(directory)
    except FileExistsError:
        console.print(
            f"A playlist manager is already initialized in {directory}",
            style="red",
        )
        raise typer.Exit()

    PlaylistManager()


@service_app.command()
def add(
    service: ServiceType,
    service_config_path: str,
    name: Optional[str] = typer.Argument(None),
) -> None:
    """Add a service to the config file"""

    pm = PlaylistManager()
    # check if service is already added
    for s in pm.config.services:
        if s.service == service.value and s.config_path == service_config_path:
            typer.echo(f"{service.value, service_config_path} is already added")
            return

    if not name:
        name = ""
    pm.add_service(service, Path(service_config_path), name)
    typer.echo(f"Added {service.value, service_config_path}")


@service_app.callback(invoke_without_command=True)
def list() -> None:
    """List all services"""
    pm = PlaylistManager()
    table = Table(title="Services")
    table.add_column("Name", justify="left")
    table.add_column("Service", justify="left")
    table.add_column("Config Path", justify="left")
    for s in pm.config.services:
        table.add_row(s.name, s.service, s.config_path)
    console.print(table)


@service_app.command()
def remove(name: str) -> None:
    """Remove a service from the config file"""
    raise NotImplementedError  # TODO


@app.command()
def pull_metadata() -> None:
    """Pull playlists from services"""
    pm = PlaylistManager()
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
            if service_name not in row or type(row[service_name]) is not str:
                continue
            metadata = service.get_playlist_metadata(row[service_name])
            playlist.merge_metadata(metadata)

            with playlist_config_path.open("w") as f:
                f.write(playlist.json(indent=4))

    typer.echo("Done")


@app.command()
def pull_tracks(playlist_name: str) -> None:
    """Pull tracks from services and merge into Unified Playlist"""
    pm = PlaylistManager()
    pm.pull_tracks(playlist_name)


@app.command()
def search(
    service: ServiceType,
    playlist: str,
    showall: bool = False,
    debug: bool = False,
    onlyfailed: bool = False,
) -> None:
    """Search for every track in the playlist on the service"""
    typer.echo(f"Searching {service.value} for {playlist}")

    pm = PlaylistManager()
    pl = pm.playlists[playlist]
    original_tracks = pl.tracks
    streaming_service = [s for s in pm.services.values() if s.type == service][0]
    predicted_tracks = [
        get_prediction_track(streaming_service, track, threshold=0.5)
        for track in tqdm(original_tracks)
    ]
    all_predicted_tracks = [
        get_predicted_tracks(streaming_service, track) for track in original_tracks
    ]

    table = Table(title=f"Uncertain {service.value} search results for {playlist}")
    table.add_column("Original Track")
    table.add_column("Predicted Track")
    table.add_column("Confidence")
    table.show_lines = True

    for i, (original, predicted) in enumerate(zip(original_tracks, predicted_tracks)):
        if predicted is None:
            if showall or onlyfailed:
                table.add_row(original, "", "")
                for track in all_predicted_tracks[i]:
                    table.add_row("", track, f"{original.similarity(track):.2f}")
            continue
        elif onlyfailed:
            continue

        similarity = original.similarity(predicted)
        if not showall and similarity >= 0.7:
            continue

        table.add_row(original, predicted, f"{original.similarity(predicted):.2f}")
        if debug:
            for track in all_predicted_tracks[i][1:]:
                table.add_row("", track, f"{original.similarity(track):.2f}")

    console.print(table)
    num_not_found = len([t for t in predicted_tracks if t is None])
    console.print(f"{len(predicted_tracks) - num_not_found} tracks found")
    console.print(f"{num_not_found} tracks not found")
