from typing import List, Optional
import typer

from universal_playlists.cli.utils import get_playlist_manager
from universal_playlists.uri import playlistURI_from_url


playlist_app = typer.Typer()


@playlist_app.command()
def add(name: str, urls: Optional[List[str]] = typer.Argument(None)) -> None:
    """Add a playlist to the config file"""
    pm = get_playlist_manager()
    uris = [playlistURI_from_url(url) for url in urls or []]
    pm.add_playlist(name, uris)
    typer.echo(f"Added {name}")
