from pathlib import Path
from typing import Any, List, Optional

import typer
from unitunes.main import FileManager, PlaylistManager
from rich import print
from rich.table import Table
from rich.console import Console
from unitunes.matcher import DefaultMatcherStrategy, MatcherStrategy
from unitunes.playlist import Playlist
from unitunes.services.services import StreamingService

from unitunes.track import Track
from unitunes.types import ServiceType

console = Console()


def toggleable_confirm(prompt: str, noninteractive: bool, default: bool) -> bool:
    console.print(prompt, "YES" if default else "NO")
    if noninteractive:
        return default

    return typer.confirm(prompt, default=default)


def toggleable_prompt(prompt: str, noninteractive: bool, default: str) -> str:
    console.print(prompt, default)
    if noninteractive:
        return default

    return typer.prompt(prompt, default=default)


def get_playlist_manager(dir: Path) -> PlaylistManager:
    fm = FileManager(dir)
    try:
        index = fm.load_index()
    except FileNotFoundError:
        typer.echo(
            "Index file not found. Please run `unitunes init` to create a config file."
        )
        raise typer.Exit()

    return PlaylistManager(index, fm)


def print_grid(
    title: str, headers: List[str], rows: List[List[Any]], plain: bool
) -> None:
    if plain:
        grid = Table.grid()
    else:
        grid = Table(title=title)

    for header in headers:
        grid.add_column(header, justify="left")
    for row in rows:
        r = map(str, row)
        if plain:
            # add padding after each column
            r = map(lambda x: x + "  ", r)
        grid.add_row(*r)
    print(grid)


def print_tracks(tracks: List[Track], plain: bool = False) -> None:
    grid = []
    for track in tracks:
        artists = ", ".join([a.__rich__() for a in track.artists])
        albumms = ", ".join([a.__rich__() for a in track.albums])
        uris = ", ".join([u.__rich__() for u in track.uris])
        grid.append([track.name.__rich__(), artists, albumms, track.length, uris])

    print_grid(
        "Tracks",
        headers=["Name", "Artists", "Albums", "Length", "URIs"],
        rows=grid,
        plain=plain,
    )


def print_playlist(playlist: Playlist, plain: bool = False) -> None:
    console.print(playlist)
    print_tracks(playlist.tracks, plain=plain)


def expand_playlists(
    pm: PlaylistManager, playlist_names: Optional[List[str]]
) -> List[Playlist]:
    if not playlist_names:
        playlist_names = pm.index.playlists

    for playlist_name in playlist_names:
        if playlist_name not in pm.playlists:
            console.print(f"{playlist_name} is not a playlist", style="red")
            raise typer.Exit()

    return [pm.playlists[playlist_name] for playlist_name in playlist_names]


def expand_services(
    pm: PlaylistManager, service_names: Optional[List[str]]
) -> List[StreamingService]:
    if not service_names:
        service_names = list(pm.index.services.keys())

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
