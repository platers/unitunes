from universal_playlists.track import AliasedString, Track
from universal_playlists.uri import SpotifyTrackURI


def test_track_uri_matches():
    uri1 = SpotifyTrackURI.from_uri("123456")
    uri2 = SpotifyTrackURI.from_uri("1234567")
    track1 = Track(name=AliasedString("test"), uris=[uri1])
    track2 = Track(name=AliasedString("test"), uris=[uri2])

    assert not track1.uri_matches(track2)
    assert track1.uri_matches(track1)
    assert track2.uri_matches(track2)
