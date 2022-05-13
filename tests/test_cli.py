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

runner = CliRunner()
test_dir = Path("tests") / "test_lib"


@pytest.fixture(scope="module")
def ytm_config(pytestconfig):
    config_path = pytestconfig.getoption("ytm", skip=True)
    return Path(config_path)


@pytest.fixture(scope="module")
def spotify_config(pytestconfig):
    config_path = pytestconfig.getoption("spotify", skip=True)
    with Path(config_path).open() as f:
        config = json.load(f)
    return config


@pytest.fixture
def playlist_manager():
    test_dir.mkdir(exist_ok=True)
    result = runner.invoke(app, ["init", "tests/test_lib"])
    assert result.exit_code == 0

    yield get_playlist_manager(test_dir)

    shutil.rmtree(test_dir)


def test_init(playlist_manager):
    assert isinstance(playlist_manager, PlaylistManager)
    assert "mb" in playlist_manager.services
    assert (test_dir / "config.json").exists()
    assert playlist_manager.file_manager.dir == test_dir


def invoke_cli(args: List[str]):
    cwd = os.getcwd()
    os.chdir(test_dir)
    print(os.getcwd())
    result = runner.invoke(app, args)
    os.chdir(cwd)
    return result


def test_add_ytm_service(playlist_manager, ytm_config):
    if not ytm_config:
        return

    result = invoke_cli(["service", "add", "ytm", ytm_config.as_posix()])
    assert result.exit_code == 0
    assert "Added" in result.stdout
    pm = get_playlist_manager(test_dir)

    assert "ytm" in pm.services


def test_add_spotify_service(playlist_manager, pytestconfig):
    spotify_config_path = pytestconfig.getoption("spotify")
    if not spotify_config_path:
        return

    result = invoke_cli(["service", "add", "spotify", spotify_config_path])
    assert result.exit_code == 0
    assert "Added" in result.stdout
    pm = get_playlist_manager(test_dir)
    assert "spotify" in pm.services


@pytest.fixture
def pm_with_spotify_service(playlist_manager, spotify_config):
    if not spotify_config:
        return

    result = invoke_cli(["service", "add", "spotify", spotify_config])
    yield get_playlist_manager(test_dir)


@pytest.fixture
def pm_added_playlist(pm_with_spotify_service):
    result = invoke_cli(
        [
            "add",
            "headphones",
            "https://open.spotify.com/playlist/19TGUNYKnJ8N1bFe0oA5lv",
        ],
    )

    assert result.exit_code == 0
    yield get_playlist_manager(test_dir)


def test_pull_playlist(pm_added_playlist):
    assert "spotify" in pm_added_playlist.services
    assert len(pm_added_playlist.playlists) == 1
