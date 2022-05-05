import json
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel
import typer
from rich.console import Console
from universal_playlists.main import service_factory
from universal_playlists.services.services import StreamingService

from universal_playlists.types import ServiceType
from universal_playlists.uri import URI_from_url, trackURI_from_url


class Case(BaseModel):
    description: str = ""
    matches: List[str] = []
    non_matches: List[str] = []


eval_app = typer.Typer()
console = Console()

path = Path(__file__).parent / "data" / "cases.json"


def load_cases() -> List[Case]:
    with open(path) as f:
        raw = json.load(f)
    return [Case.parse_obj(case) for case in raw]


def save_cases(cases: List[Case]) -> None:
    with open(path, "w") as f:
        json.dump([case.dict() for case in cases], f, indent=4)


@eval_app.command()
def add(description: str, uri: str) -> None:
    """Add a new case"""
    cases = load_cases()
    cases.append(Case(description=description, matches=[uri]))
    save_cases(cases)


def build_service(service_type: ServiceType) -> StreamingService:
    path = (
        Path(__file__).parent
        / "data"
        / "service_configs"
        / f"{service_type}_config.json"
    )
    service = service_factory(service_type, service_type, path)
    return service


@eval_app.command()
def search(
    guess_service: Optional[ServiceType] = typer.Option(None, "--guess", "-g")
) -> None:
    """
    Evaluate search performance.
    """
    cases = load_cases()

    for case in cases:
        print(case.description)
        matches = [trackURI_from_url(url) for url in case.matches]
        non_matches = [trackURI_from_url(url) for url in case.non_matches]
        matched_services = [uri.service for uri in matches]

        if guess_service and guess_service not in matched_services:
            target_service = build_service(guess_service)

            for uri in matches:
                source_service = build_service(uri.service)
                track = source_service.pull_track(uri)
                guesses = target_service.search_track(track)

                console.print("Original:", end="\n\n")
                console.print(track, end="\n\n")
                console.print("Guesses:")

                for g in guesses:
                    uris_on_service = [
                        uri for uri in g.uris if uri.service == guess_service
                    ]
                    assert len(uris_on_service) == 1
                    guess_uri = uris_on_service[0]

                    console.print(g, end="\n\n")
                    # ask user if this is the correct match
                    correct = typer.confirm(f"Is {g.name.value} a correct match?")

                    if correct:
                        case.matches.append(guess_uri.url)
                        print("Added to matches")
                    else:
                        case.non_matches.append(guess_uri.url)
                        print("Added to non-matches")

                    save_cases(cases)
