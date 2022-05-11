from tqdm import tqdm
import typer
from universal_playlists.cli.utils import (
    get_playlist_manager,
    print_grid,
    print_playlist,
    print_tracks,
)
from universal_playlists.main import (
    Config,
    FileManager,
    get_predicted_tracks,
    get_prediction_track,
)
from typing import List, Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table
from universal_playlists.cli.service_cli import service_app
from universal_playlists.matcher import DefaultMatcherStrategy
from universal_playlists.searcher import DefaultSearcherStrategy
from universal_playlists.services.services import PlaylistPullable, Pushable
from universal_playlists.track import Track, tracks_to_add, tracks_to_remove

from universal_playlists.types import ServiceType
from universal_playlists.uri import playlistURI_from_url


console = Console()
app = typer.Typer(no_args_is_help=True)
app.add_typer(service_app, name="service", help="Manage services")


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
    fm = FileManager(directory)

    try:
        fm.save_config(Config())
    except FileExistsError:
        console.print(
            f"A playlist manager is already initialized in {directory}",
            style="red",
        )
        raise typer.Exit()

    fm.make_playlist_dir()


@app.command()
def view(playlist: str) -> None:
    """View a playlist"""
    pm = get_playlist_manager()
    if playlist not in pm.playlists:
        console.print(f"{playlist} is not a playlist", style="red")
        raise typer.Exit()
    pl = pm.playlists[playlist]

    print_playlist(pl)


@app.command()
def pull(
    playlists: Optional[List[str]] = typer.Argument(None),
    services: Optional[List[str]] = typer.Option(
        None,
        "--service",
        "-s",
        help="Service to pull from",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
    ),
):
    """Pull a playlist from a service"""
    pm = get_playlist_manager()

    if not playlists:
        playlists = list(pm.config.playlists.keys())

    if not services:
        services = list(pm.config.services.keys())

    for playlist_name in playlists:
        if playlist_name not in pm.playlists:
            console.print(f"{playlist_name} is not a playlist", style="red")
            raise typer.Exit()
        pl = pm.playlists[playlist_name]

        new_tracks: List[Track] = []
        removed_tracks: List[Track] = []

        for service_name in services:
            if service_name not in pm.services:
                console.print(f"{service_name} is not a service", style="red")
                raise typer.Exit()
            service = pm.services[service_name]
            if not isinstance(service, PlaylistPullable):
                console.print(
                    f"{service} is not a playlist pullable service", style="red"
                )
                raise typer.Exit()

            uri = pl.find_uri(service.type)
            if not uri:
                continue
            remote_tracks = service.pull_tracks(uri)
            added = tracks_to_add(service.type, pl.tracks, remote_tracks)
            removed = tracks_to_remove(service.type, pl.tracks, remote_tracks)

            if added:
                console.print(f"{uri.url} added {len(added)} tracks")
                print_tracks(added)
            if removed:
                console.print(f"{uri.url} removed {len(removed)} tracks")
                print_tracks(removed)

            new_tracks.extend(added)
            removed_tracks.extend(removed)

        console.print(f"{len(new_tracks)} new tracks")
        if verbose:
            print_tracks(new_tracks)
        console.print(f"{len(removed_tracks)} removed tracks")
        if verbose:
            print_tracks(removed_tracks)

        matcher = DefaultMatcherStrategy()

        def merge_new_tracks(tracks: List[Track], new_tracks: List[Track]) -> None:
            for track in new_tracks:
                matches = [t for t in tracks if matcher.are_same(t, track)]
                if matches:
                    for match in matches:
                        match.merge(track)
                else:
                    tracks.append(track)

        merge_new_tracks(pl.tracks, new_tracks)

        def remove_tracks(tracks: List[Track], removed_tracks: List[Track]) -> None:
            for track in removed_tracks:
                matches = [t for t in tracks if t.shares_uri(track)]
                if not matches:
                    # already removed
                    continue

                console.print(f"Track {track.name.value} not found in playlist")
                incorrect = typer.confirm("Incorrect match?")
                if incorrect:
                    # remove uri
                    for t in matches:
                        t.uris.remove(track.uris[0])
                        console.print(f"Removed {track.uris[0]} from {t}")
                else:
                    # remove track
                    for t in matches:
                        tracks.remove(t)
                        console.print(f"Removed {t}")

        remove_tracks(pl.tracks, removed_tracks)

        pm.save_playlist(pl.name)


@app.command()
def push(
    playlists: Optional[List[str]] = typer.Argument(None),
    services: Optional[List[str]] = typer.Option(
        None,
        "--service",
        "-s",
        help="Service to push to",
    ),
):
    """Push a playlist to a service."""
    pm = get_playlist_manager()

    if not playlists:
        playlists = list(pm.config.playlists.keys())

    if not services:
        services = list(pm.config.services.keys())

    for playlist_name in playlists:
        if playlist_name not in pm.playlists:
            console.print(f"{playlist_name} is not a playlist", style="red")
            raise typer.Exit()
        pl = pm.playlists[playlist_name]
        for service_name in services:
            if service_name not in pm.services:
                console.print(f"{service_name} is not a service", style="red")
                raise typer.Exit()

            service = pm.services[service_name]
            if not isinstance(service, Pushable):
                console.print(f"{service} is not a pushable service", style="red")
                continue

            if not any([t.find_uri(service.type) for t in pl.tracks]):
                continue

            uri = pl.find_uri(service.type)
            if not uri:
                console.print(f"{pl.name} does not have a uri for {service.type}")
                create_new = typer.confirm("Create new playlist?", default=False)
                if not create_new:
                    continue
                uri = service.create_playlist(pl.name)
                console.print(f"Created {uri.url}")
                pl.add_uri(uri)
                pm.save_playlist(pl.name)

            current_tracks = service.pull_tracks(uri)
            added = tracks_to_add(service.type, current_tracks, pl.tracks)
            removed = tracks_to_remove(service.type, current_tracks, pl.tracks)
            if added:
                console.print(f"{len(added)} new tracks")
                console.print("Added tracks:")
                print_tracks(added)
            if removed:
                console.print("Removed tracks:")
                console.print(f"{len(removed)} removed tracks")
                print_tracks(removed)

            if not added and not removed:
                continue

            if not typer.confirm(f"Push to {uri.url}?", default=False):
                continue

            if added:
                service.add_tracks(uri, added)
            if removed:
                service.remove_tracks(uri, removed)

            console.print(f"Pushed {pl.name} to {uri.url}")


@app.command()
def search(
    service: ServiceType,
    playlist: str,
    showall: bool = False,
    debug: bool = False,
    onlyfailed: bool = False,
    save: bool = True,
) -> None:
    """Search for every track in the playlist on the service"""
    typer.echo(f"Searching {service.value} for {playlist}")

    pm = get_playlist_manager()
    pl = pm.playlists[playlist]
    original_tracks = pl.tracks
    streaming_service = [s for s in pm.services.values() if s.type == service][0]
    matcher = DefaultMatcherStrategy()
    searcher = DefaultSearcherStrategy(matcher)

    predicted_tracks = [
        get_prediction_track(streaming_service, track, matcher, searcher, threshold=0.7)
        for track in tqdm(original_tracks)
    ]
    num_not_found = len([t for t in predicted_tracks if t is None])
    console.print(f"{len(predicted_tracks) - num_not_found} tracks found")
    console.print(f"{num_not_found} tracks not found")

    for (original, predicted) in zip(original_tracks, predicted_tracks):
        if predicted is None:
            console.print(f"{original.name.value} ->", style="red")
            continue
        print(
            f"{original.name.value} -> {predicted.name.value}"
        )  # no highlight for clarity
        original.merge(predicted)

    if save:
        pm.save_playlist(playlist)

    if debug:
        all_predicted_tracks = [
            get_predicted_tracks(streaming_service, track, searcher)
            for track in original_tracks
        ]

        table = Table(title=f"Uncertain {service.value} search results for {playlist}")
        table.add_column("Original Track")
        table.add_column("Predicted Track")
        table.add_column("Confidence")
        table.show_lines = True

        for i, (original, predicted) in enumerate(
            zip(original_tracks, predicted_tracks)
        ):
            if predicted is None:
                if showall or onlyfailed:
                    table.add_row(original, "", "")
                    for track in all_predicted_tracks[i]:
                        table.add_row(
                            "", track, f"{matcher.similarity(original, track):.2f}"
                        )
                continue
            elif onlyfailed:
                continue

            similarity = matcher.similarity(original, predicted)
            if not showall and similarity >= 0.7:
                continue

            table.add_row(original, predicted, f"{similarity:.2f}")
            if debug:
                for track in all_predicted_tracks[i][1:]:
                    table.add_row(
                        "", track, f"{matcher.similarity(original, track):.2f}"
                    )

        console.print(table)


@app.command()
def add(name: str, urls: Optional[List[str]] = typer.Argument(None)) -> None:
    """Add a playlist to the config file"""
    pm = get_playlist_manager()
    urls = urls or []
    uris = [playlistURI_from_url(url) for url in urls]

    if name in pm.playlists:
        pm.add_uris_to_playlist(name, uris)
        typer.echo(f"Added {', '.join(urls)} to {name}")
    else:
        pm.add_playlist(name, uris)
        typer.echo(f"Added playlist {name}")


@app.command(name="list")
def list_cmd(plain: bool = False) -> None:
    """List all playlists"""
    pm = get_playlist_manager()
    grid = [
        [
            pl.name,
            len(pl.uris),
            len(pl.tracks),
        ]
        for pl in pm.playlists.values()
    ]

    print_grid(
        "Playlists", headers=["Name", "URIs", "# Tracks"], rows=grid, plain=plain
    )
