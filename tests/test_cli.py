from pathlib import Path
import pytest
from typer.testing import CliRunner
import shutil

from universal_playlists.cli.cli import app
from universal_playlists.cli.utils import get_playlist_manager
from universal_playlists.main import PlaylistManager

runner = CliRunner()


@pytest.fixture
def playlist_manager():
    test_dir = Path("tests") / "test_lib"
    test_dir.mkdir(exist_ok=True)
    result = runner.invoke(app, ["init", "tests/test_lib"])
    assert result.exit_code == 0

    yield get_playlist_manager(test_dir)

    shutil.rmtree(test_dir)


def test_init(playlist_manager):
    assert isinstance(playlist_manager, PlaylistManager)
