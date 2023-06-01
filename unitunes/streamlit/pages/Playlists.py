import streamlit as st
import pandas as pd

from unitunes.streamlit.Unitunes import pm
from unitunes.main import Track

st.title("Playlists")

playlist = st.selectbox("Playlist", pm.playlists)
pl = pm.playlists[playlist]
service_types = [s.type for s in pm.services.values()]

st.write(f"Number of songs: {len(pl.tracks)}")


def tracks_to_df(tracks: list[Track]):
    rows = []
    for track in tracks:
        row = {
            "Title": track.name.value,
            "Artist": [artist.value for artist in track.artists],
            # "Album": [album.value for album in track.albums],
            "Length": track.length,
        }
        for service_type in service_types:
            uri = track.find_uri(service_type)
            row[service_type.value] = uri.url if uri else None
        rows.append(row)
    return pd.DataFrame(rows)


df = tracks_to_df(pl.tracks)
st.dataframe(df)
