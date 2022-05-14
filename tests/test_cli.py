import json
import os
from pathlib import Path
from typing import List
import pytest
from typer.testing import CliRunner
import shutil

from universal_playlists.cli.cli import app
from universal_playlists.cli.utils import get_playlist_manager
from universal_playlists.main import PlaylistManager
from universal_playlists.services.spotify import SpotifyAPIWrapper, SpotifyService
from universal_playlists.types import ServiceType
from universal_playlists.uri import SpotifyPlaylistURI


runner = CliRunner()
test_dir = Path("tests") / "test_lib"


@pytest.fixture(scope="module")
def ytm_config_path(pytestconfig):
    config_path = pytestconfig.getoption("ytm", skip=True)
    return Path(config_path).absolute()


@pytest.fixture(scope="module")
def spotify_config_path(pytestconfig):
    config_path = pytestconfig.getoption("spotify", skip=True)
    return Path(config_path).absolute()


@pytest.fixture
def playlist_manager():
    test_dir.mkdir(exist_ok=True)
    result = runner.invoke(app, ["init", "tests/test_lib"])
    assert result.exit_code == 0

    yield get_playlist_manager(test_dir)

    # delete all files except .cache and cache
    for f in test_dir.glob("*"):
        if f.name == ".cache" or f.name == "cache":
            continue
        if f.is_dir():
            shutil.rmtree(f)
        else:
            f.unlink()


def test_init(playlist_manager):
    assert isinstance(playlist_manager, PlaylistManager)
    assert "mb" in playlist_manager.services
    assert (test_dir / "config.json").exists()
    assert playlist_manager.file_manager.dir == test_dir


def invoke_cli(args: List[str]):
    cwd = os.getcwd()
    os.chdir(test_dir)
    result = runner.invoke(app, args)
    os.chdir(cwd)
    return result


def test_add_ytm_service(playlist_manager, ytm_config_path):
    result = invoke_cli(["service", "add", "ytm", ytm_config_path.as_posix()])
    assert result.exit_code == 0
    assert "Added" in result.stdout
    pm = get_playlist_manager(test_dir)

    assert "ytm" in pm.services


def test_add_spotify_service(playlist_manager, spotify_config_path):
    result = invoke_cli(["service", "add", "spotify", spotify_config_path.as_posix()])
    assert result.exit_code == 0
    assert "Added" in result.stdout
    pm = get_playlist_manager(test_dir)
    assert "spotify" in pm.services


@pytest.fixture
def pm_with_spotify_service(playlist_manager, spotify_config_path):
    result = invoke_cli(["service", "add", "spotify", spotify_config_path.as_posix()])
    assert result.exit_code == 0
    yield get_playlist_manager(test_dir)


def test_add_same_service(pm_with_spotify_service, spotify_config_path):
    result = invoke_cli(["service", "add", "spotify", spotify_config_path.as_posix()])
    assert result.exit_code == 1
    assert "already exists" in result.stdout.lower()


@pytest.fixture
def pm_added_playlist(pm_with_spotify_service):
    result = invoke_cli(
        [
            "add",
            "headphones",
            "spotify",
            "https://open.spotify.com/playlist/19TGUNYKnJ8N1bFe0oA5lv",
        ],
    )

    assert result.exit_code == 0
    yield get_playlist_manager(test_dir)


def test_add_playlist(pm_added_playlist):
    assert "spotify" in pm_added_playlist.services
    assert len(pm_added_playlist.playlists) == 1
    assert "headphones" in pm_added_playlist.playlists
    pl = pm_added_playlist.playlists["headphones"]
    assert "spotify" in pl.uris


def test_remove_service(pm_added_playlist):
    result = invoke_cli(["service", "remove", "spotify", "-f"])
    assert result.exit_code == 0
    assert "Removed" in result.stdout
    pm = get_playlist_manager(test_dir)
    assert "spotify" not in pm.config.services
    assert "spotify" not in pm.services
    assert "spotify" not in pm.playlists["headphones"].uris


@pytest.fixture
def pm_pulled_playlist(pm_added_playlist, spotify_config_path):
    # Pull a playlist with spotify service first to ensure .cache is created
    # typer.invoke cant take input
    with open(spotify_config_path, "r") as f:
        config = json.load(f)
    wrapper = SpotifyAPIWrapper(config, test_dir / "cache")
    service = SpotifyService("temp", wrapper)

    owd = os.getcwd()
    os.chdir(test_dir)
    service.pull_tracks(
        SpotifyPlaylistURI.from_url(
            "https://open.spotify.com/playlist/19TGUNYKnJ8N1bFe0oA5lv"
        )
    )
    os.chdir(owd)

    result = invoke_cli(["pull", "headphones"])
    assert result.exit_code == 0
    yield get_playlist_manager(test_dir)


def test_pull_playlist(pm_pulled_playlist):
    assert "spotify" in pm_pulled_playlist.services
    assert len(pm_pulled_playlist.playlists) == 1
    assert "headphones" in pm_pulled_playlist.playlists
    pl = pm_pulled_playlist.playlists["headphones"]
    assert len(pl.tracks) > 5
    assert pl.tracks[0].name.value == "Wilderness"


@pytest.fixture
def pm_searched_playlist(pm_pulled_playlist):
    result = invoke_cli(["search", "mb", "headphones"])
    assert result.exit_code == 0
    yield get_playlist_manager(test_dir)


def test_search_playlist(pm_searched_playlist):
    assert "mb" in pm_searched_playlist.services
    assert len(pm_searched_playlist.playlists) == 1
    assert "headphones" in pm_searched_playlist.playlists
    pl = pm_searched_playlist.playlists["headphones"]
    assert len(pl.tracks) > 5
    assert pl.tracks[0].name.value == "Wilderness"
    print(pl.tracks[0])
    track1 = pl.tracks[0]
    assert track1.find_uri(ServiceType.MB)
    assert track1.find_uri(ServiceType.SPOTIFY)
    assert (
        track1.find_uri(ServiceType.MB).url
        == "https://musicbrainz.org/recording/8c7959e9-7487-485e-be9d-f00cd7e1d2be"
    )


def test_fetch(pm_with_spotify_service):
    result = invoke_cli(["fetch", "spotify"])
    assert result.exit_code == 0
    # cant test much more, user specific
