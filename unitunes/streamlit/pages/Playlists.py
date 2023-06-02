from datetime import datetime
import streamlit as st
import pandas as pd

from unitunes.streamlit.Unitunes import pm
from unitunes.main import Track
from unitunes.uri import playlistURI_from_url

st.title("Playlists")

st.header("Add playlist")

new_playlist_name = st.text_input("Playlist name")
if st.button("Add Playlist"):
    try:
        pm.add_playlist(new_playlist_name)
    except ValueError as e:
        st.error(e)
        st.stop()

    st.success(
        f"Added playlist {new_playlist_name}. Select it from the dropdown to configure it."
    )
    st.experimental_rerun()


st.header("Edit playlist")

playlist = st.selectbox("Playlist", pm.playlists)
pl = pm.playlists[playlist]
service_types = [s.type for s in pm.services.values()]

st.write(f"Number of songs: {len(pl.tracks)}")


with st.form("Edit Playlist"):
    pm.playlists[playlist].name = st.text_input("Name", value=pl.name)
    pm.playlists[playlist].description = st.text_area(
        "Description", value=pl.description
    )
    if st.form_submit_button("Save"):
        pm.save_playlist(playlist)
        st.experimental_rerun()

st.subheader("URIs")

with st.form("Add URI"):
    service_name = st.selectbox("Service", [s.name for s in pm.services.values()])
    uri = st.text_input("URL")
    if st.form_submit_button("Add URI"):
        try:
            uri = playlistURI_from_url(uri)
            pl.add_uri(service_name, uri)
        except ValueError as e:
            st.error(e)
            st.stop()
        pm.save_playlist(playlist)
        st.experimental_rerun()


for name, uri in pl.list_uris():
    cols = st.columns([1, 1])
    with cols[0]:
        st.write(uri.url)
    with cols[1]:
        if st.button(
            "Remove",
            args=(uri,),
            key=f"delete_{uri}",
            help="Remove URI from playlist",
        ):
            pl.remove_uri(name, uri)
            pm.save_playlist(playlist)
            st.experimental_rerun()

st.subheader("Tracks")


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
