import streamlit as st
from pathlib import Path
from functools import partial
import argparse
from enum import Enum

from unitunes.main import PlaylistManager, FileManager

st.title("Unitunes")

parser = argparse.ArgumentParser()
parser.add_argument("--music-dir", type=Path, required=True)
args = parser.parse_args()


music_dir = args.music_dir
fm = FileManager(music_dir)
pm = PlaylistManager(fm.load_index(), fm)


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
    cols = st.columns([1, 1, 1, 1])
    with cols[0]:
        st.button(
            "Sync All",
            on_click=partial(apply_all, Action.SYNC),
            help="Pull, search and push all playlists",
        )
    with cols[1]:
        st.button("Pull All", on_click=partial(apply_all, Action.PULL))
    with cols[2]:
        st.button("Search All", on_click=partial(apply_all, Action.SEARCH))
    with cols[3]:
        st.button("Push All", on_click=partial(apply_all, Action.PUSH))

for playlist in pm.playlists:
    pl = pm.playlists[playlist]
    container = playlist_containers[playlist]
    container.divider()

    cols = container.columns([3, 1, 1, 1, 1])
    with cols[0]:
        st.subheader(playlist)
        st.write(f"Tracks: {len(pl.tracks)}")
    with cols[1]:
        st.button(
            "Sync",
            key=f"sync_{playlist}",
            on_click=partial(apply_action, playlist, Action.SYNC),
            help="Pull, search and push playlist",
        )
    with cols[2]:
        st.button(
            "Pull",
            key=f"pull_{playlist}",
            on_click=partial(apply_action, playlist, Action.PULL),
            help="Pull playlist from services",
        )
    with cols[3]:
        st.button(
            "Search",
            key=f"search_{playlist}",
            on_click=partial(apply_action, playlist, Action.SEARCH),
            help="Search for tracks in services",
        )
    with cols[4]:
        st.button(
            "Push",
            key=f"push_{playlist}",
            on_click=partial(apply_action, playlist, Action.PUSH),
            help="Push local changes to services",
        )
