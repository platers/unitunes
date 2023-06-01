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

playlist_header = st.empty()


class Action(Enum):
    SYNC = "Sync"
    PULL = "Pull"
    PUSH = "Push"
    SEARCH = "Search"


playlist_containers = {}
for playlist in pm.playlists:
    container = st.container()
    playlist_containers[playlist] = container


def apply_action(playlist: str, action: Action, save: bool = True):
    container = playlist_containers[playlist]
    bar = container.progress(0.0, f"{action.value}ing {playlist}")

    def progress_callback(progress: int, size: int):
        if size == 0:
            return
        bar.progress(progress / size)

    if action == Action.PULL:
        pm.pull_playlist(playlist, progress_callback=progress_callback)
    elif action == Action.SEARCH:
        pm.search_playlist(playlist, progress_callback=progress_callback)
    elif action == Action.PUSH:
        pm.push_playlist(playlist, progress_callback=progress_callback)
    elif action == Action.SYNC:
        pm.pull_playlist(playlist, progress_callback=progress_callback)
        pm.search_playlist(playlist, progress_callback=progress_callback)
        pm.push_playlist(playlist, progress_callback=progress_callback)

    container.success(f"{action.value}ed {playlist}")
    print(f"{action.value}ed {playlist}")

    if save:
        pm.save_playlist(playlist)
        print(f"Saved {playlist}")


def apply_all(action: Action):
    for playlist in pm.playlists:
        apply_action(playlist, action)


with playlist_header.container():
    st.button("Sync All", on_click=partial(apply_all, Action.SYNC))
    st.button("Pull All", on_click=partial(apply_all, Action.PULL))
    st.button("Search All", on_click=partial(apply_all, Action.SEARCH))
    st.button("Push All", on_click=partial(apply_all, Action.PUSH))

for playlist in pm.playlists:
    pl = pm.playlists[playlist]
    container = playlist_containers[playlist]
    container.divider()

    col1, col2 = container.columns(2)
    with col1:
        st.subheader(playlist)
        st.write(f"Tracks: {len(pl.tracks)}")
    with col2:
        st.button(
            "Sync",
            key=f"sync_{playlist}",
            on_click=partial(apply_action, playlist, Action.SYNC),
        )
        st.button(
            "Pull",
            key=f"pull_{playlist}",
            on_click=partial(apply_action, playlist, Action.PULL),
        )
        st.button(
            "Search",
            key=f"search_{playlist}",
            on_click=partial(apply_action, playlist, Action.SEARCH),
        )
        st.button(
            "Push",
            key=f"push_{playlist}",
            on_click=partial(apply_action, playlist, Action.PUSH),
        )
