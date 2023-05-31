import streamlit as st
from pathlib import Path

from unitunes.main import PlaylistManager, FileManager

st.title("Unitunes")

music_dir = Path("/home/victor/dev/music")
fm = FileManager(music_dir)

pm = PlaylistManager(fm.load_index(), fm)

# List services
st.header("Services")
for service in pm.services:
    st.write(service)

# List playlists
st.header("Playlists")
for playlist in pm.playlists:
    st.write(playlist)
