from typing import List

from unitunes.services.services import StreamingService

from unitunes.track import Track
from unitunes.uri import TrackURIs

from unitunes.matcher import DefaultMatcherStrategy, MatcherStrategy
from unitunes.services.services import (
    Checkable,
    StreamingService,
)
from unitunes.track import Track

from unitunes.types import ServiceType
from unitunes.uri import TrackURIs


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
            print(f"Track {t.name.value} not found in playlist")
            # remove uri
            t.uris.remove(missing_uri)
            t.bad_uris.append(missing_uri)
            print(f"Removed {missing_uri.url} from {t.name.value} and marked it as bad")


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
                print(f"Removed invalid URL {uri.url} from {track.name.value}")


def tracks_match_and_on_service(
    service: ServiceType,
    t1: Track,
    t2: Track,
    matcher: MatcherStrategy = DefaultMatcherStrategy(),
) -> bool:
    return (
        matcher.are_same(t1, t2)
        and t1.is_on_service(service)
        and t2.is_on_service(service)
    )


def tracks_to_add(
    service: ServiceType, current: List[Track], new: List[Track]
) -> List[Track]:
    new_on_service = [track for track in new if track.is_on_service(service)]
    return [
        track
        for track in new_on_service
        if not any(tracks_match_and_on_service(service, track, t) for t in current)
    ]


def tracks_to_remove(
    service: ServiceType, current: List[Track], new: List[Track]
) -> List[Track]:
    current_on_service = [track for track in current if track.is_on_service(service)]
    return [
        track
        for track in current_on_service
        if not any(tracks_match_and_on_service(service, t, track) for t in new)
    ]
