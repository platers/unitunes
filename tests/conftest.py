import json
from pathlib import Path

import pytest


cache_path = Path("tests/cache")


def pytest_addoption(parser):
    parser.addoption(
        "--spotify", action="store", default=None, help="Spotify config path"
    )
    parser.addoption(
        "--ytm", action="store", default=None, help="Youtube Music config path"
    )
    parser.addoption(
        "--beatsaver", action="store", default=None, help="BeatSaver config path"
    )
