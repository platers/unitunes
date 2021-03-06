import json
from typing import Dict, List, Optional
from pathlib import Path
from unitunes.file_manager import FileManager
from unitunes.index import Index
from unitunes.matcher import MatcherStrategy
from unitunes.playlist import Playlist
from unitunes.searcher import SearcherStrategy
from unitunes.services.beatsaber import (
    BeatsaberService,
    BeatsaverAPIWrapper,
)
from unitunes.services.musicbrainz import MusicBrainz, MusicBrainzWrapper
from unitunes.services.services import (
    Searchable,
    StreamingService,
    TrackPullable,
)


from unitunes.services.spotify import (
    SpotifyAPIWrapper,
    SpotifyService,
)
from unitunes.services.ytm import YTM, YtmAPIWrapper
from unitunes.track import Track
from unitunes.types import ServiceType
from unitunes.uri import PlaylistURIs, TrackURI


def service_factory(
    service_type: ServiceType,
    name: str,
    cache_path: Path,
    config_path: Optional[Path] = None,
) -> StreamingService:

    if service_type == ServiceType.SPOTIFY:
        assert config_path is not None
        index = json.load(config_path.open())
        return SpotifyService(name, SpotifyAPIWrapper(index, cache_path))
    elif service_type == ServiceType.YTM:
        assert config_path is not None
        return YTM(name, YtmAPIWrapper(config_path, cache_path))
    elif service_type == ServiceType.MB:
        return MusicBrainz(MusicBrainzWrapper(cache_path))
    elif service_type == ServiceType.BEATSABER:
        assert config_path is not None
        config = json.load(config_path.open())
        return BeatsaberService(name, BeatsaverAPIWrapper(cache_path), config)
    else:
        raise ValueError(f"Unknown service type: {service_type}")


class PlaylistManager:
    index: Index
    file_manager: FileManager
    playlists: Dict[str, Playlist]
    services: Dict[str, StreamingService]

    def __init__(self, index: Index, file_manager: FileManager) -> None:
        self.index = index
        self.file_manager = file_manager
        self.playlists = {}
        self.services = {}

        self.load_services()

        # create playlist objects
        for name in self.index.playlists:
            self.playlists[name] = self.file_manager.load_playlist(name)

    def load_services(self) -> None:
        self.services[ServiceType.MB.value] = service_factory(
            ServiceType.MB,
            "MusicBrainz",
            cache_path=self.file_manager.cache_path,
        )
        for s in self.index.services.values():
            service_config_path = Path(s.config_path)
            self.services[s.name] = service_factory(
                ServiceType(s.service),
                s.name,
                config_path=service_config_path,
                cache_path=self.file_manager.cache_path,
            )

    def add_service(
        self, service: ServiceType, service_config_path: Path, name: str
    ) -> None:
        self.index.add_service(
            name, service.value, service_config_path.absolute().as_posix()
        )
        self.load_services()
        self.file_manager.save_index(self.index)

    def remove_service(self, name: str) -> None:
        if name not in self.index.services:
            raise ValueError(f"Service {name} not found")
        self.index.remove_service(name)

        for playlist in self.playlists.values():
            playlist.remove_service(name)
            self.file_manager.save_playlist(playlist)

        self.file_manager.save_index(self.index)

    def add_playlist(self, name: str) -> None:
        """Initialize a UP. Raise ValueError if the playlist already exists."""
        self.index.add_playlist(name)
        self.playlists[name] = Playlist(name=name)
        self.file_manager.save_index(self.index)
        self.file_manager.save_playlist(self.playlists[name])

    def remove_playlist(self, name: str) -> None:
        """Remove a playlist from the index and filesystem."""
        if name not in self.index.playlists:
            raise ValueError(f"Playlist {name} not found")
        self.file_manager.delete_playlist(name)
        del self.playlists[name]
        self.index.remove_playlist(name)
        self.file_manager.save_index(self.index)

    def add_uri_to_playlist(
        self, playlist_name: str, service_name: str, uri: PlaylistURIs
    ) -> None:
        """Link a playlist URI to a UP. UP must exist."""
        pl = self.playlists[playlist_name]
        pl.add_uri(service_name, uri)

        self.file_manager.save_index(self.index)
        self.file_manager.save_playlist(pl)

    def save_playlist(self, playlist_name: str) -> None:
        self.file_manager.save_playlist(self.playlists[playlist_name])

    def is_tracking_playlist(self, uri: PlaylistURIs) -> bool:
        for playlist in self.playlists.values():
            for uris in playlist.uris.values():
                if uri in uris:
                    return True
        return False


def get_predicted_tracks(
    target_service: StreamingService,
    track: Track,
    searcher: SearcherStrategy,
) -> List[Track]:
    if not isinstance(target_service, Searchable):
        raise ValueError(f"Service {target_service.name} is not searchable")

    return searcher.search(target_service, track)


def get_prediction_track(
    target_service: StreamingService,
    track: Track,
    matcher: MatcherStrategy,
    searcher: SearcherStrategy,
    threshold: float = 0.8,
) -> Optional[Track]:
    matches = get_predicted_tracks(target_service, track, searcher)
    matches = [m for m in matches if not any(uri in track.bad_uris for uri in m.uris)]
    if len(matches) == 0:
        return None
    best_match = matches[0]

    if matcher.similarity(track, best_match) >= threshold:
        return best_match
    return None


def get_prediction_uri(
    source_service: StreamingService,
    target_service: StreamingService,
    uri: TrackURI,
    matcher: MatcherStrategy,
    searcher: SearcherStrategy,
    threshold: float = 0.8,
) -> Optional[TrackURI]:
    if not isinstance(source_service, TrackPullable):
        raise ValueError(f"Service {source_service} is not pullable")
    track = source_service.pull_track(uri)
    prediction = get_prediction_track(
        target_service, track, matcher, searcher, threshold
    )
    return prediction.uris[0] if prediction else None
