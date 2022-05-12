from pathlib import Path


cache_path = Path("tests/cache")


def pytest_addoption(parser):
    parser.addoption("--spotify", action="store", default="")
    parser.addoption("--ytm", action="store", default="")
