from pathlib import Path

import typer
from universal_playlists.main import FileManager, PlaylistManager


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
