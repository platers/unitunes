from typing import List

from rich.console import Console
import typer
from unitunes.playlist import Playlist
from unitunes.services.services import StreamingService

from unitunes.track import Track
from unitunes.uri import TrackURIs

from unitunes.cli.utils import (
    print_tracks,
    tracks_to_add,
)
from unitunes.matcher import DefaultMatcherStrategy, MatcherStrategy
from unitunes.services.services import (
    Checkable,
    PlaylistPullable,
    StreamingService,
)
from unitunes.track import Track

from unitunes.types import ServiceType
from unitunes.uri import PlaylistURIs, TrackURIs, playlistURI_from_url

console = Console()


def get_missing_uris(
    service: ServiceType, current: List[Track], new: List[Track]
) -> List[TrackURIs]:
    def tracks_to_uris(tracks: List[Track]) -> List[TrackURIs]:
        uris = [track.uris for track in tracks]
        flat_uris = [uri for uri_list in uris for uri in uri_list]
        return flat_uris

    uris_on_service = [uri for uri in tracks_to_uris(current) if uri.service == service]
    remote = tracks_to_uris(new)
    missing = [uri for uri in uris_on_service if uri not in remote]
    return missing


def get_invalid_uris(
    service: StreamingService, uris: List[TrackURIs]
) -> List[TrackURIs]:
    return [
        uri
        for uri in uris
        if isinstance(service, Checkable) and not service.is_uri_alive(uri)
    ]


def merge_new_tracks(
    tracks: List[Track], new_tracks: List[Track], matcher: MatcherStrategy
) -> None:
    for track in new_tracks:
        matches = [t for t in tracks if matcher.are_same(t, track)]
        if matches:
            for match in matches:
                match.merge(track)
        else:
            tracks.append(track)


def remove_tracks(current_tracks: List[Track], missing: List[TrackURIs]) -> None:
    for missing_uri in missing:
        matches = [t for t in current_tracks if missing_uri in t.uris]
        for t in matches:
            console.print(f"Track {t.name.value} not found in playlist")
            prompt: str = typer.prompt(
                f"Mark {missing_uri.url} as bad (b), remove track from playlist (r), or skip (s)?",
                default="b",
            )

            if prompt.startswith("b"):
                # remove uri
                t.uris.remove(missing_uri)
                t.bad_uris.append(missing_uri)
                console.print(
                    f"Removed {missing_uri.url} from {t.name.value} and marked it as bad"
                )
            elif prompt.startswith("r"):
                # remove track
                current_tracks.remove(t)
                console.print(f"Removed {t.name.value}")
            elif prompt.startswith("s"):
                console.print("Skipping")


def get_added(
    service: StreamingService,
    playlist_uri: PlaylistURIs,
    pl: Playlist,
    remote_tracks: List[Track],
) -> List[Track]:
    added = tracks_to_add(service.type, pl.tracks, remote_tracks)
    print(f"Added {len(added)} tracks")

    if added:
        console.print(
            f"{playlist_uri.url} added {len(added)} tracks from {service.name}"
        )
        print_tracks(added)
    return added


def add_changed_uris(current_tracks: List[Track], remote_tracks: List[Track]) -> None:
    """Finds matching tracks with different uris and adds them"""
    matcher = DefaultMatcherStrategy()

    def fix_track_uri(track: Track) -> None:
        matches = [t for t in remote_tracks if matcher.are_same(t, track)]
        if not matches:
            return
        new_uri = matches[0].uris[0]
        if new_uri not in track.uris:
            # remove other uris on this service
            track.uris = [u for u in track.uris if u.service != new_uri.service]

            track.uris.append(new_uri)
            print(f"{track.name.value} updated uri to {new_uri.url}")

    for track in current_tracks:
        fix_track_uri(track)


def remove_uris(current_tracks: List[Track], uris: List[TrackURIs]) -> None:
    for track in current_tracks:
        for uri in uris:
            if uri in track.uris:
                track.uris.remove(uri)
                track.bad_uris.append(uri)
                console.print(f"Removed invalid URL {uri.url} from {track.name.value}")


def pull_playlist(
    pl: Playlist, services: List[StreamingService], verbose: bool = False
) -> None:
    new_tracks: List[Track] = []
    missing_uris: List[TrackURIs] = []
    invalid_uris: List[TrackURIs] = []

    new_tracks = []
    services = [service for service in services if service.name in pl.uris]
    for service in services:
        for playlist_uri in pl.uris[service.name]:
            assert isinstance(service, PlaylistPullable)
            remote_tracks = service.pull_tracks(playlist_uri)
            print(f"Pulled {len(remote_tracks)} tracks from {service.name}")

            new_tracks.extend(get_added(service, playlist_uri, pl, remote_tracks))

            add_changed_uris(pl.tracks, remote_tracks)
            new_missing = get_missing_uris(service.type, pl.tracks, remote_tracks)
            invalid_uris.extend(get_invalid_uris(service, new_missing))
            new_missing = [uri for uri in new_missing if uri not in invalid_uris]
            missing_uris.extend(new_missing)

    remove_uris(pl.tracks, invalid_uris)

    if verbose:
        print_tracks(new_tracks)
    console.print(f"{len(missing_uris)} missing tracks")
    if verbose:
        for playlist_uri in missing_uris:
            console.print(f"{playlist_uri.url}")

    merge_new_tracks(pl.tracks, new_tracks, DefaultMatcherStrategy())
    remove_tracks(pl.tracks, missing_uris)
