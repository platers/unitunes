from enum import Enum


class ServiceType(str, Enum):
    SPOTIFY = "spotify"
    YTM = "ytm"
    MB = "mb"
    BEATSABER = "beatsaber"


class EntityType(str, Enum):
    TRACK = "track"
    PLAYLIST = "playlist"
    ALBUM = "album"
