from tqdm import tqdm
import typer
from unitunes.cli.utils import (
    get_playlist_manager,
    print_grid,
    print_playlist,
    print_tracks,
)
from unitunes.main import (
    Config,
    FileManager,
    PlaylistManager,
    get_predicted_tracks,
    get_prediction_track,
)
from typing import List, Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table
from unitunes.cli.service_cli import service_app
from unitunes.matcher import DefaultMatcherStrategy, MatcherStrategy
from unitunes.playlist import Playlist
from unitunes.searcher import DefaultSearcherStrategy
from unitunes.services.services import (
    PlaylistPullable,
    Pushable,
    StreamingService,
    UserPlaylistPullable,
)
from unitunes.track import Track, tracks_to_add, tracks_to_remove

from unitunes.types import ServiceType
from unitunes.uri import playlistURI_from_url


console = Console()
app = typer.Typer(
    no_args_is_help=True,
    help="Unitunes playlist manager. https://github.com/platers/unitunes",
)
app.add_typer(service_app, name="service", help="Manage services.")


@app.command()
def init(
    directory: Optional[Path] = typer.Argument(
        Path("."),
        help="Directory to store playlist files in.",
    )
) -> None:
    """
    Create a new playlist manager.

    Creates a new playlist manager in the given directory.
    """
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
    """Show a playlists metadata and tracks."""
    pm = get_playlist_manager(Path.cwd())
    if playlist not in pm.playlists:
        console.print(f"{playlist} is not a playlist", style="red")
        raise typer.Exit()
    pl = pm.playlists[playlist]

    print_playlist(pl)


def expand_playlists(
    pm: PlaylistManager, playlist_names: Optional[List[str]]
) -> List[Playlist]:
    if not playlist_names:
        playlist_names = pm.config.playlists

    for playlist_name in playlist_names:
        if playlist_name not in pm.playlists:
            console.print(f"{playlist_name} is not a playlist", style="red")
            raise typer.Exit()

    return [pm.playlists[playlist_name] for playlist_name in playlist_names]


def expand_services(
    pm: PlaylistManager, service_names: Optional[List[str]]
) -> List[StreamingService]:
    if not service_names:
        service_names = list(pm.config.services.keys())

    for service_name in service_names:
        if service_name not in pm.services:
            console.print(f"{service_name} is not a service", style="red")
            raise typer.Exit()

    return [pm.services[service_name] for service_name in service_names]


@app.command()
def pull(
    playlist_names: Optional[List[str]] = typer.Argument(
        None,
        help="Playlists to pull from services. If not specified, all playlists are pulled.",
    ),
    service_names: Optional[List[str]] = typer.Option(
        None,
        "--service",
        "-s",
        help="Services to pull from. If not specified, all services are used.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
    ),
):
    """
    Pull playlist tracks from services.

    If no playlist is specified, all playlists are pulled.
    If no service is specified, all services are used.
    """

    def merge_new_tracks(
        tracks: List[Track], new_tracks: List[Track], matcher: MatcherStrategy
    ) -> None:
        for track in new_tracks:
            matches = [t for t in tracks if matcher.are_same(t, track)]
            if matches:
                for match in matches:
                    match.merge(track)
            else:
                tracks.append(track)

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

    pm = get_playlist_manager(Path.cwd())

    playlists = expand_playlists(pm, playlist_names)
    services = [
        service
        for service in expand_services(pm, service_names)
        if isinstance(service, PlaylistPullable)
    ]

    for pl in playlists:
        new_tracks: List[Track] = []
        removed_tracks: List[Track] = []

        for service in services:
            uri = pl.find_uri(service.type)
            if not uri:
                continue

            remote_tracks = service.pull_tracks(uri)

            added = tracks_to_add(service.type, pl.tracks, remote_tracks)
            removed = tracks_to_remove(service.type, pl.tracks, remote_tracks)

            if added:
                console.print(
                    f"{uri.url} added {len(added)} tracks from {service.name}"
                )
                print_tracks(added)
            if removed:
                console.print(
                    f"{uri.url} removed {len(removed)} tracks from {service.name}"
                )
                print_tracks(removed)

            new_tracks.extend(added)
            removed_tracks.extend(removed)

        console.print(f"{len(new_tracks)} new tracks in {pl.name}")
        if verbose:
            print_tracks(new_tracks)
        console.print(f"{len(removed_tracks)} removed tracks in {pl.name}")
        if verbose:
            print_tracks(removed_tracks)

        merge_new_tracks(pl.tracks, new_tracks, DefaultMatcherStrategy())
        remove_tracks(pl.tracks, removed_tracks)

        pm.save_playlist(pl.name)


@app.command()
def push(
    playlist_names: Optional[List[str]] = typer.Argument(
        None,
        help="Playlists to push to services. If not specified, all playlists are pushed.",
    ),
    service_names: Optional[List[str]] = typer.Option(
        None,
        "--service",
        "-s",
        help="Services to push to. If not specified, all services are used.",
    ),
):
    """
    Push playlist tracks to services.

    If no playlist is specified, all playlists are pushed.
    If no service is specified, all services are used.
    """
    pm = get_playlist_manager(Path.cwd())

    playlists = expand_playlists(pm, playlist_names)
    services = [
        service
        for service in expand_services(pm, service_names)
        if isinstance(service, Pushable)
    ]

    for pl in playlists:
        for service in services:
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
                pl.set_uri(service.name, uri)
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
    preview: bool = typer.Option(
        False,
        "--preview",
        "-p",
        help="Preview tracks to add without adding them.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        "-d",
        help="Show debug information",
    ),
    onlyfailed: bool = typer.Option(
        False,
        "--onlyfailed",
        help="Only show failed tracks in debug information.",
    ),
    showall: bool = typer.Option(
        False,
        "--showall",
        help="Show all tracks in debug information.",
    ),
) -> None:
    """
    Search for tracks on a service.

    If preview is set, URI's will not be added to the playlist.
    """
    typer.echo(f"Searching {service.value} for {playlist}")

    pm = get_playlist_manager(Path.cwd())
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

    if not preview:
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
def add(
    playlist_name: str, service_name: str, url: Optional[str] = typer.Argument(None)
):
    """
    Add a playlist to the config file.

    If a playlist with the same name already exists, the url will be added to the playlist.
    Otherwise, a new playlist will be created.
    """
    pm = get_playlist_manager(Path.cwd())

    if playlist_name not in pm.playlists:
        pm.add_playlist(playlist_name)
        console.print(f"Created playlist {playlist_name}")

    if url is not None:
        uri = playlistURI_from_url(url)
        pm.add_uri_to_playlist(playlist_name, service_name, uri)
        console.print(f"Added {uri.url} to {playlist_name}")


@app.command(name="list")
def list_cmd(plain: bool = False) -> None:
    """List all playlists."""
    pm = get_playlist_manager(Path.cwd())
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


@app.command()
def fetch(
    service_name: str = typer.Argument(None, help="Service to fetch from."),
    force: bool = typer.Option(False, "--force", "-f", help="Auto accept prompts."),
) -> None:
    """Quickly add playlists from a service."""

    pm = get_playlist_manager(Path.cwd())
    service = pm.services[service_name]
    if not isinstance(service, UserPlaylistPullable):
        console.print(f"Cannot fetch user playlists from {service.type}", style="red")
        raise typer.Exit()

    playlists = service.get_playlist_metadatas()
    console.print(f"Found {len(playlists)} playlists")

    for pl in playlists:
        if pm.is_tracking_playlist(pl.uri):
            console.print(f"Already tracking {pl.name}")
            continue

        track_pl = force or typer.confirm(
            f"Add {pl.name} ({pl.uri.url})?", default=True
        )
        if not track_pl:
            continue

        up_name = (
            pl.name
            if force
            else typer.prompt(f"UP name for {pl.name}", default=pl.name)
        )
        if up_name in pm.playlists:
            pm.add_uri_to_playlist(up_name, service_name, pl.uri)
            console.print(f"Added {pl.uri.url} to {up_name}")
        else:
            pm.add_playlist(up_name)
            pm.add_uri_to_playlist(up_name, service_name, pl.uri)
            console.print(f"Created playlist {up_name}")

        pm.save_playlist(up_name)
