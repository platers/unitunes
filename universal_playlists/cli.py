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
app = typer.Typer()

pm = PlaylistManager()


@app.command()
def add_service(
    service: ServiceType,
    service_config_path: str,
    name: Optional[str] = typer.Argument(None),
) -> None:
    """Add a service to the config file"""

    # check if service is already added
    for s in pm.config.services:
        if s.service == service.value and s.config_path == service_config_path:
            typer.echo(f"{service.value, service_config_path} is already added")
            return

    if not name:
        name = ""
    pm.add_service(service, Path(service_config_path), name)
    typer.echo(f"Added {service.value, service_config_path}")


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
            if service_name not in row or type(row[service_name]) is not str:
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


@app.command()
def search(
    service: ServiceType, playlist: str, verbose: bool = False, debug: bool = False
) -> None:
    """Search for every track in the playlist on the service"""
    typer.echo(f"Searching {service.value} for {playlist}")

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
            # table.add_row(original, "", "")
            continue

        similarity = original.similarity(predicted)
        if not verbose and similarity >= 0.7:
            continue

        table.add_row(original, predicted, f"{original.similarity(predicted):.2f}")
        if debug:
            for track in all_predicted_tracks[i][1:]:
                table.add_row("", track, f"{original.similarity(track):.2f}")

    console.print(table)
    num_not_found = len([t for t in predicted_tracks if t is None])
    console.print(f"{len(predicted_tracks) - num_not_found} tracks found")
    console.print(f"{num_not_found} tracks not found")
