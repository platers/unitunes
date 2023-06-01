import streamlit as st
from pathlib import Path
from functools import partial
from enum import Enum

from unitunes.main import PlaylistManager, FileManager

st.title("Unitunes")

music_dir = Path("/home/victor/dev/music")
fm = FileManager(music_dir)


@st.cache_resource
def playlist_manager():
    pm = PlaylistManager(fm.load_index(), fm)
    return pm


pm = playlist_manager()

# List services
st.header("Services")
# for service in pm.services:
#     st.write(service)
tabs = st.tabs(pm.services)
for tab, service in zip(tabs, pm.services):
    with tab:
        st.write(service)

st.header("Playlists")

# st.button("Sync All")
# st.button("Pull All")
# st.button("Push All")


class Action(Enum):
    SYNC = "Sync"
    PULL = "Pull"
    PUSH = "Push"


with st.container():
    containers = {}
    for playlist in pm.playlists:
        container = st.container()
        containers[playlist] = container

    def pull(playlist: str, action: Action):
        container = containers[playlist]
        bar = container.progress(0.0, f"{action.value}ing {playlist}")

        def progress_callback(progress: int, size: int):
            bar.progress(progress / size)

        pm.pull_playlist(playlist, progress_callback=progress_callback)
        container.success(f"{action.value}ed {playlist}")
        print(f"{action.value}ed {playlist}")

    for playlist in pm.playlists:
        pl = pm.playlists[playlist]
        container = containers[playlist]
        container.divider()

        col1, col2 = container.columns(2)
        with col1:
            st.subheader(playlist)
            st.write(f"Tracks: {len(pl.tracks)}")
        with col2:
            st.button(
                "Sync",
                key=f"sync_{playlist}",
                on_click=partial(pull, playlist, Action.SYNC),
            )
            st.button(
                "Pull",
                key=f"pull_{playlist}",
                on_click=partial(pull, playlist, Action.PULL),
            )
            st.button(
                "Push",
                key=f"push_{playlist}",
                on_click=partial(pull, playlist, Action.PUSH),
            )
