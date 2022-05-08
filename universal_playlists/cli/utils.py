from pathlib import Path
from typing import Any, List

import typer
from universal_playlists.main import FileManager, PlaylistManager
from rich import print
from rich.table import Table


def get_playlist_manager() -> PlaylistManager:
    dir = Path.cwd()
    fm = FileManager(dir)

    try:
        config = fm.load_config()
    except FileNotFoundError:
        typer.echo(
            "Config file not found. Please run `universal-playlists init` to create a config file."
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
