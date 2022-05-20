from pathlib import Path
from typing import Any, List

import typer
from unitunes.main import FileManager, PlaylistManager
from rich import print
from rich.table import Table
from rich.console import Console
from unitunes.playlist import Playlist

from unitunes.track import Track

console = Console()


def get_playlist_manager(dir: Path) -> PlaylistManager:
    fm = FileManager(dir)
    try:
        config = fm.load_config()
    except FileNotFoundError:
        typer.echo(
            "Config file not found. Please run `unitunes init` to create a config file."
        )
        raise typer.Exit()

    return PlaylistManager(config, fm)


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
