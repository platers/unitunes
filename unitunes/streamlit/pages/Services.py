import streamlit as st
from unitunes.streamlit.Unitunes import music_dir
from unitunes.main import (
    PlaylistManager,
    FileManager,
    SpotifyConfig,
    YtmConfig,
    BeatsaberConfig,
    BeatSaverConfig,
)
from unitunes.common_types import ServiceType

fm = FileManager(music_dir)
pm = PlaylistManager(fm.load_index(), fm)

# Add service
st.header("Add service")
with st.form("add_service"):
    new_service_name = st.text_input("Service name")
    new_service_type = st.selectbox("Service type", [s.value for s in ServiceType])
    service_type = ServiceType(new_service_type)

    if st.form_submit_button("Add service"):
        if new_service_name == "":
            st.error("Service name cannot be empty")
            st.stop()

        if new_service_name in pm.services:
            st.error("Service name already exists")
            st.stop()

        if service_type == ServiceType.SPOTIFY:
            config = SpotifyConfig()
        elif type == ServiceType.YTM:
            config = YtmConfig()
        elif type == ServiceType.BEATSABER:
            config = BeatsaberConfig()
        elif type == ServiceType.BEATSAVER:
            config = BeatSaverConfig()
        else:
            raise ValueError(f"Unknown service type {type}")

        fm.save_service_config(new_service_name, config)
        pm.add_service(
            service_type, fm.service_config_path(new_service_name), new_service_name
        )
        pm.save_index()
        st.success(f"Added service {new_service_name} of type {new_service_type}")
        st.experimental_rerun()


# List service configs
tabs = st.tabs(pm.index.services)
for tab, s in zip(tabs, pm.index.services.values()):
    tab.write(s.config_path)
    service_type = s.service
    try:
        if service_type == ServiceType.SPOTIFY:
            config = SpotifyConfig.parse_file(s.config_path)
            with tab.form(f"spotify_config_{s.name}"):
                st.write(
                    "Follow the instructions to obtain a client id and secret https://spotipy.readthedocs.io/en/2.19.0/#getting-started"
                )
                config.client_id = st.text_input("Client ID", config.client_id)
                config.client_secret = st.text_input(
                    "Client secret", config.client_secret
                )
                config.redirect_uri = st.text_input("Redirect URI", config.redirect_uri)

                if st.form_submit_button("Save"):
                    fm.save_service_config(s.name, config)
                    st.success(f"Saved config for service {s.name}")
                    st.experimental_rerun()

        elif service_type == ServiceType.YTM:
            config = YtmConfig.parse_file(s.config_path)

            with tab.form(f"ytm_config_{s.name}"):
                st.write(
                    "Copy headers with the following instructions: https://ytmusicapi.readthedocs.io/en/stable/setup/browser.html#copy-authentication-headers"
                )
                config.headers = st.text_area("Headers", config.headers)

                if st.form_submit_button("Save"):
                    fm.save_service_config(s.name, config)
                    st.success(f"Saved config for service {s.name}")
                    st.experimental_rerun()

        elif service_type == ServiceType.BEATSABER:
            config = BeatsaberConfig.parse_file(s.config_path)

            with tab.form(f"beatsaber_config_{s.name}"):
                config.dir = st.text_input("Directory", config.dir)

                config.search_config.minNps = st.number_input(
                    "Min NPS", config.search_config.minNps
                )
                config.search_config.maxNps = st.number_input(
                    "Max NPS", config.search_config.maxNps
                )
                config.search_config.minRating = st.number_input(
                    "Min rating", config.search_config.minRating
                )

                if st.form_submit_button("Save"):
                    fm.save_service_config(s.name, config)
                    st.success(f"Saved config for service {s.name}")
                    st.experimental_rerun()
        elif service_type == ServiceType.BEATSAVER:
            config = BeatSaverConfig.parse_file(s.config_path)

            with tab.form(f"beatsaver_config_{s.name}"):
                config.username = st.text_input("Username", config.username)
                config.password = st.text_input("Password", config.password)

                config.search_config.minNps = st.number_input(
                    "Min NPS", config.search_config.minNps
                )
                config.search_config.maxNps = st.number_input(
                    "Max NPS", config.search_config.maxNps
                )
                config.search_config.minRating = st.number_input(
                    "Min rating", config.search_config.minRating
                )

                if st.form_submit_button("Save"):
                    fm.save_service_config(s.name, config)
                    st.success(f"Saved config for service {s.name}")
                    st.experimental_rerun()
    except Exception as e:
        print(f"Failed to load service {s.name}: {e}")

    if tab.button(f"Delete {s.name} service", key=f"delete_service_{s.name}"):
        pm.remove_service(s.name)
        st.experimental_rerun()
