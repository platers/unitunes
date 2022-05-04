from typing import List
import typer

from universal_playlists.cli.utils import get_playlist_manager


playlist_app = typer.Typer()


@playlist_app.command()
def add(name: str, urls: List[str]) -> None:
    """Add a playlist to the config file"""
    pm = get_playlist_manager()
    # pm.add_playlist(name, urls)
    typer.echo(f"Added {name}")
