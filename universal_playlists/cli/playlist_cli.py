from typing import List, Optional
import typer

from universal_playlists.cli.utils import get_playlist_manager
from universal_playlists.uri import playlistURI_from_url


playlist_app = typer.Typer()


@playlist_app.command()
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


@playlist_app.command()
def list() -> None:
    """List all playlists"""
    pm = get_playlist_manager()
    for name in pm.playlists:
        typer.echo(name)
