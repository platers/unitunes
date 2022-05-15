from unitunes.track import AliasedString, Track
from unitunes.uri import SpotifyTrackURI, YtmTrackURI


def test_track_uri_matches():
    uri1 = SpotifyTrackURI.from_uri("123456")
    uri2 = SpotifyTrackURI.from_uri("1234567")
    track1 = Track(name=AliasedString("test"), uris=[uri1])
    track2 = Track(name=AliasedString("test"), uris=[uri2])

    assert not track1.shares_uri(track2)
    assert track1.shares_uri(track1)
    assert track2.shares_uri(track2)


def test_track_merge():
    uri1 = SpotifyTrackURI.from_uri("123456")
    uri2 = YtmTrackURI.from_uri("1234567")
    artist1 = AliasedString("John")
    artist2 = AliasedString("Jon", aliases=["John"])
    album2 = AliasedString("Album 2")
    track1 = Track(name=AliasedString("test"), artists=[artist1], uris=[uri1])
    track2 = Track(
        name=AliasedString("test1"), artists=[artist2], albums=[album2], uris=[uri2]
    )

    track1.merge(track2)
    assert track1.uris == [uri1, uri2]
    assert track1.artists == [artist1]
    assert track1.albums == [album2]
