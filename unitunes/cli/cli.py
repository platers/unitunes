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
from unitunes.track import Track

from unitunes.types import ServiceType
from unitunes.uri import TrackURIs, playlistURI_from_url


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


def tracks_match_and_on_service(
    service: ServiceType,
    t1: Track,
    t2: Track,
    matcher: MatcherStrategy = DefaultMatcherStrategy(),
) -> bool:
    return (
        matcher.are_same(t1, t2)
        and t1.is_on_service(service)
        and t2.is_on_service(service)
    )


def tracks_to_add(
    service: ServiceType, current: List[Track], new: List[Track]
) -> List[Track]:
    new_on_service = [track for track in new if track.is_on_service(service)]
    return [
        track
        for track in new_on_service
        if not any(tracks_match_and_on_service(service, track, t) for t in current)
    ]


def tracks_to_remove(
    service: ServiceType, current: List[Track], new: List[Track]
) -> List[Track]:
    current_on_service = [track for track in current if track.is_on_service(service)]
    return [
        track
        for track in current_on_service
        if not any(tracks_match_and_on_service(service, t, track) for t in new)
    ]


def get_missing_uris(
    service: ServiceType, current: List[Track], new: List[Track]
) -> List[TrackURIs]:
    def tracks_to_uris(tracks: List[Track]) -> List[TrackURIs]:
        uris = [track.uris for track in tracks]
        flat_uris = [uri for uri_list in uris for uri in uri_list]
        return flat_uris

    uris_on_service = [uri for uri in tracks_to_uris(current) if uri.service == service]
    remote = tracks_to_uris(new)
    missing = [uri for uri in uris_on_service if uri not in remote]
    return missing


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
    dont_remove: bool = typer.Option(
        False,
        "--dont-remove",
        "-d",
        help="Remove tracks from playlist that are not on the service anymore.",
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

    def remove_tracks(current_tracks: List[Track], missing: List[TrackURIs]) -> None:
        for missing_uri in missing:
            matches = [t for t in current_tracks if missing_uri in t.uris]
            for t in matches:
                console.print(f"Track {t.name.value} not found in playlist")
                prompt: str = typer.prompt(
                    f"Remove {missing_uri.url} from track (u), remove track from playlist (r), or skip (s)?",
                    default="s",
                )

                if prompt.startswith("u"):
                    # remove uri
                    t.uris.remove(missing_uri)
                    console.print(f"Removed {missing_uri.url} from {t.name.value}")
                elif prompt.startswith("r"):
                    # remove track
                    current_tracks.remove(t)
                    console.print(f"Removed {t.name.value}")
                elif prompt.startswith("s"):
                    console.print("Skipping")

    pm = get_playlist_manager(Path.cwd())

    playlists = expand_playlists(pm, playlist_names)
    services = [
        service
        for service in expand_services(pm, service_names)
        if isinstance(service, PlaylistPullable)
    ]

    for pl in playlists:
        console.print(f"Pulling {pl.name}...")
        new_tracks: List[Track] = []
        missing_uris: List[TrackURIs] = []

        for service in services:
            if service.name not in pl.uris:
                continue

            for playlist_uri in pl.uris[service.name]:
                remote_tracks = service.pull_tracks(playlist_uri)

                added = tracks_to_add(service.type, pl.tracks, remote_tracks)
                print(f"Added {len(added)} tracks")

                if added:
                    console.print(
                        f"{playlist_uri.url} added {len(added)} tracks from {service.name}"
                    )
                    print_tracks(added)
                new_tracks.extend(added)

                if not dont_remove:
                    missing = get_missing_uris(service.type, pl.tracks, remote_tracks)
                    if missing:
                        console.print(
                            f"{playlist_uri.url} missing {len(missing)} tracks from {pl.name}"
                        )

                    missing_uris.extend(missing)

        if verbose:
            print_tracks(new_tracks)
        console.print(f"{len(missing_uris)} missing tracks")
        if verbose:
            for playlist_uri in missing_uris:
                console.print(f"{playlist_uri.url}")

        merge_new_tracks(pl.tracks, new_tracks, DefaultMatcherStrategy())
        remove_tracks(pl.tracks, missing_uris)

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

    Asks for confirmation before pushing.

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
        console.print(f"Calculating changes to {pl.name}")
        for service in services:
            if not any([t.find_uri(service.type) for t in pl.tracks]):
                continue

            if not service.name in pl.uris:
                console.print(f"{pl.name} does not have a uri for {service.type}")
                create_new = typer.confirm("Create new playlist?", default=False)
                if not create_new:
                    continue
                playlist_uri = service.create_playlist(pl.name)
                console.print(f"Created {playlist_uri.url}")
                pl.add_uri(service.name, playlist_uri)
                pm.save_playlist(pl.name)

            for playlist_uri in pl.uris[service.name]:
                current_tracks = service.pull_tracks(playlist_uri)
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

                if not typer.confirm(f"Push to {playlist_uri.url}?", default=False):
                    continue

                if added:
                    service.add_tracks(playlist_uri, added)
                if removed:
                    service.remove_tracks(playlist_uri, removed)

                console.print(f"Pushed {pl.name} to {playlist_uri.url}")


@app.command()
def search(
    service: ServiceType,
    playlist_name: str,
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
    Search for tracks on a service. Adds found URI's to tracks.

    If the preview flag is set, URI's will not be added.
    """
    typer.echo(f"Searching {service.value} for {playlist_name}")

    pm = get_playlist_manager(Path.cwd())
    pl = pm.playlists[playlist_name]
    original_tracks = [track for track in pl.tracks if not track.find_uri(service)]
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
        pm.save_playlist(playlist_name)

    if debug:
        all_predicted_tracks = [
            get_predicted_tracks(streaming_service, track, searcher)
            for track in original_tracks
        ]

        table = Table(
            title=f"Uncertain {service.value} search results for {playlist_name}"
        )
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

    if service_name not in pm.services:
        console.print(f"Service {service_name} not found", style="red")
        return

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
    """
    Quickly add playlists from a service.

    Asks for confirmation before adding each playlist unless the force flag is set.
    """

    if service_name is None:
        console.print("Please specify a service.")
        raise typer.Exit(1)

    pm = get_playlist_manager(Path.cwd())
    service = pm.services[service_name]
    if not isinstance(service, UserPlaylistPullable):
        console.print(f"Cannot fetch user playlists from {service.type}", style="red")
        raise typer.Exit(1)

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


@app.command()
def merge(
    source_playlist_name: str,
    target_playlist_name: str,
) -> None:
    """
    Merge a playlist into another playlist.
    """

    pm = get_playlist_manager(Path.cwd())

    source_playlist = pm.playlists[source_playlist_name]
    target_playlist = pm.playlists[target_playlist_name]
    original_length = len(target_playlist.tracks)

    matcher = DefaultMatcherStrategy()

    target_playlist.merge_playlist(source_playlist, matcher)
    pm.save_playlist(target_playlist_name)

    new_length = len(target_playlist.tracks)
    console.print(f"Merged {source_playlist_name} into {target_playlist_name}")
    console.print(f"{original_length} -> {new_length} tracks")


@app.command()
def remove(
    playlist_name: str,
):
    """
    Remove a playlist.
    """

    pm = get_playlist_manager(Path.cwd())

    if playlist_name not in pm.playlists:
        console.print(f"Playlist {playlist_name} not found", style="red")
        raise typer.Exit(1)

    pm.remove_playlist(playlist_name)
    console.print(f"Removed playlist {playlist_name}")
