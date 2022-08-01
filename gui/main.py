from datetime import datetime
from pathlib import Path
import webbrowser
import dearpygui.dearpygui as dpg
from appdirs import user_data_dir
from pydantic import BaseModel
from gui.engine import Engine, Job, JobStatus, JobType
from unitunes import PlaylistManager, FileManager, Index
from unitunes.uri import PlaylistURIs, playlistURI_from_url

dpg.create_context()
dpg.create_viewport(title="Unitunes", width=600, height=600)


class AppConfig(BaseModel):
    unitunes_dir: Path


def hyperlink(url: str) -> None:
    b = dpg.add_button(label=url, callback=lambda: webbrowser.open(url))
    dpg.bind_item_theme(b, "hyperlinkTheme")


class GUI:
    app_config: AppConfig
    pm: PlaylistManager
    engine: Engine
    touched_playlists: set[str] = set()

    def __init__(self):
        self.load_app_config()
        self.load_playlist_manager()
        self.main_window_setup()
        self.engine = Engine(self.pm)

    def load_playlist_manager(self):
        fm = FileManager(self.app_config.unitunes_dir)
        try:
            fm.load_index()
        except FileNotFoundError:
            # Create a new index if it doesn't exist
            fm.save_index(Index())
            print(f"Created new index at {fm.index_path.absolute()}")

        self.pm = PlaylistManager(fm.load_index(), fm)

    def load_app_config(self):
        # If the config file doesn't exist, create it
        config_dir = Path(user_data_dir("unitunes"))
        config_dir.mkdir(exist_ok=True)
        config_path = config_dir / "config.json"
        if not config_path.exists():
            config_path.touch()
            self.app_config = AppConfig(unitunes_dir=config_dir)
        # Load the config file
        try:
            self.app_config = AppConfig.parse_file(config_path)
        except Exception as e:
            print(e)
            print("Could not load config file. Using default config.")
            self.app_config = AppConfig(unitunes_dir=config_dir)
            self.save_app_config()

    def save_app_config(self):
        config_path = Path(user_data_dir("unitunes")) / "config.json"
        with open(config_path, "w") as f:
            f.write(self.app_config.json())

    def init_themes(self):
        with dpg.theme(tag="hyperlinkTheme"):
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, [0, 0, 0, 0])
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, [0, 0, 0, 0])
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, [29, 151, 236, 25])
                dpg.add_theme_color(dpg.mvThemeCol_Text, [29, 151, 236])

    def main_window_setup(self):
        self.init_themes()
        with dpg.window(label="Example Window", tag="Primary"):
            with dpg.tab_bar():
                self.playlists_tab_setup()
                self.services_tab_setup()
                self.jobs_tab_setup()
                self.settings_tab_setup()

    ########################################
    # Jobs tab
    ########################################

    def jobs_tab_setup(self):
        with dpg.tab(label="Jobs"):
            with dpg.child_window(tag="jobs_window"):

                def clear_completed_jobs():
                    # loop children of jobs_window and remove those that are complete
                    children: list[int] = dpg.get_item_children("jobs_window", 1)  # type: ignore
                    for child in children:
                        tag = dpg.get_item_alias(child)
                        if tag.startswith("job_row_"):
                            job_id = int(tag.split("_")[-1])
                            if self.engine.get_job(job_id).status == JobStatus.SUCCESS:
                                dpg.delete_item(child)

                dpg.add_button(
                    label="Clear Completed",
                    tag="clear_completed_button",
                    callback=clear_completed_jobs,
                )

    def add_job_row_placeholder(self, job_id: int):
        with dpg.child_window(tag=f"job_row_{job_id}", height=60, parent="jobs_window"):
            with dpg.group(horizontal=True):
                dpg.add_text("placeholder", tag=f"job_description_{job_id}")
                dpg.add_progress_bar(tag=f"job_progress_{job_id}")
                dpg.add_text("placeholder", tag=f"job_progress_text_{job_id}")
            with dpg.group(horizontal=True):
                # dpg.add_button(label="Cancel", tag=f"cancel_button_{job_id}")
                dpg.add_text("placeholder", tag=f"job_status_text_{job_id}")

    def touch_playlist(self, playlist: str):
        self.touched_playlists.add(playlist)
        dpg.show_item("save_changes_button")

    def sync_job_row(self, job_id: int):
        job = self.engine.get_job(job_id)
        dpg.set_value(f"job_description_{job_id}", job.description)
        dpg.set_value(f"job_status_text_{job_id}", job.status.name)
        if job.status == JobStatus.SUCCESS:
            status_color = (0, 255, 0)  # green
        elif job.status == JobStatus.FAILED:
            status_color = (255, 0, 0)  # red
        elif job.status == JobStatus.RUNNING:
            status_color = (255, 255, 0)  # yellow
        else:
            status_color = (255, 255, 255)  # white

        dpg.configure_item(f"job_status_text_{job_id}", color=status_color)

        if job.size > 0:
            dpg.set_value(f"job_progress_{job_id}", job.progress / job.size)
            dpg.set_value(f"job_progress_text_{job_id}", f"{job.progress}/{job.size}")
        else:
            dpg.set_value(f"job_progress_{job_id}", 0)
            dpg.set_value(f"job_progress_text_{job_id}", "")

        self.touch_playlist(job.playlist_name)

    def add_job(self, job_type: JobType, playlist: str):
        job_id = self.engine.push_job(
            Job(
                job_type,
                playlist,
                lambda: self.sync_job_row(job_id),
                self.pm,
            )
        )
        self.add_job_row_placeholder(job_id)
        self.sync_job_row(job_id)

    ########################################
    # Settings tab
    ########################################
    def settings_tab_setup(self):
        with dpg.tab(label="Settings"):
            with dpg.child_window(tag="settings_window"):
                with dpg.group(horizontal=True):
                    # File Dialog
                    def change_unitunes_dir(sender, app_data):
                        self.app_config.unitunes_dir = Path(app_data["current_path"])
                        self.save_app_config()
                        self.load_playlist_manager()
                        sync_unitunes_dir_text()

                    file_dialog = dpg.add_file_dialog(
                        label="Unitunes Directory",
                        tag="unitunes_dir_dialog",
                        directory_selector=True,
                        show=False,
                        height=300,
                        width=600,
                        callback=change_unitunes_dir,
                    )

                    dpg.add_text(
                        "Unitunes Directory:",
                    )

                    # Button
                    def sync_unitunes_dir_text():
                        dpg.set_item_label(
                            "unitunes_dir_button",
                            str(self.app_config.unitunes_dir),
                        )

                    dpg.add_button(
                        tag="unitunes_dir_button",
                        label="placeholder",
                        callback=lambda: dpg.show_item(file_dialog),
                    )
                    sync_unitunes_dir_text()

    ########################################
    # Playlists tab
    ########################################

    def playlists_tab_setup(self):
        with dpg.tab(label="Playlists"):
            with dpg.child_window(tag="playlist_window"):
                with dpg.group(horizontal=True):

                    def save_changes_callback():
                        self.pm.save_index()
                        for playlist_name in self.touched_playlists:
                            self.pm.save_playlist(playlist_name)
                        self.touched_playlists.clear()
                        dpg.hide_item("save_changes_button")

                    # Red button
                    dpg.add_button(
                        label="Save Changes",
                        tag="save_changes_button",
                        show=False,
                        callback=save_changes_callback,
                    )

                    def pull_all_callback():
                        for playlist in self.pm.playlists:
                            self.add_job(JobType.PULL, playlist)

                    dpg.add_button(
                        label="Pull All",
                        tag="pull_all_button",
                        callback=pull_all_callback,
                    )

                    def search_all_callback():
                        for playlist in self.pm.playlists:
                            self.add_job(JobType.SEARCH, playlist)

                    dpg.add_button(
                        label="Search All",
                        tag="search_all_button",
                        callback=search_all_callback,
                    )

                    def push_all_callback():
                        for playlist in self.pm.playlists:
                            self.add_job(JobType.PUSH, playlist)

                    dpg.add_button(
                        label="Push All",
                        tag="push_all_button",
                        callback=push_all_callback,
                    )

                    def add_playlist_callback():
                        playlist_id = f"New Playlist {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        self.pm.add_playlist(playlist_id)
                        self.touch_playlist(playlist_id)
                        self.sync_playlist_list()
                        # Open playlist edit window
                        self.edit_playlist_row(playlist_id)

                    dpg.add_button(
                        label="Add Playlist",
                        tag="add_playlist_button",
                        callback=add_playlist_callback,
                    )

                with dpg.window(
                    tag="edit_playlist_window",
                    modal=True,
                    show=False,
                    label="Edit Playlist",
                    width=500,
                    height=600,
                ):
                    dpg.add_input_text(
                        tag="playlist_name_input",
                        label="Playlist Name",
                    )
                    dpg.add_input_text(
                        tag="playlist_description_input",
                        label="Playlist Description",
                        multiline=True,
                        height=50,
                    )
                    with dpg.child_window(
                        tag="add_playlist_url_window",
                        label="Add Playlist URL",
                        height=100,
                    ):
                        with dpg.group(horizontal=True):
                            dpg.add_combo(
                                tag="service_combo", label="Service", width=100
                            )
                            dpg.add_input_text(
                                tag="playlist_url_input",
                                hint="Playlist URL",
                                width=200,
                            )
                            dpg.add_button(
                                label="Add URL",
                                tag="add_playlist_url_button_2",
                            )

                        with dpg.table(
                            tag="uri_table",
                            resizable=True,
                            policy=dpg.mvTable_SizingStretchProp,
                        ):
                            dpg.add_table_column(
                                label="Service",
                                width_stretch=True,
                                init_width_or_weight=0.5,
                            )
                            dpg.add_table_column(label="URL")
                            dpg.add_table_column()  # Delete button

                with dpg.window(
                    tag="delete_playlist_window",
                    modal=True,
                    label="Delete Playlist",
                    width=400,
                    height=100,
                    show=False,
                    pos=(100, 200),
                ):
                    dpg.add_text(
                        f"placeholder",
                        tag="delete_playlist_text",
                    )
                    with dpg.group(horizontal=True):
                        dpg.add_button(
                            label="Yes",
                            tag="delete_playlist_yes_button",
                        ),
                        dpg.add_button(
                            label="No",
                            tag="delete_playlist_no_button",
                            callback=lambda: dpg.hide_item("delete_playlist_window"),
                        )
        self.sync_playlist_list()

    def edit_playlist_row(self, playlist_id: str):
        dpg.show_item("edit_playlist_window")
        dpg.set_value("playlist_name_input", self.pm.playlists[playlist_id].name)
        dpg.set_value(
            "playlist_description_input",
            self.pm.playlists[playlist_id].description,
        )

        def name_input_callback(sender, app_data):
            self.pm.playlists[playlist_id].name = app_data
            print(f"Renamed {playlist_id} to {app_data}")
            self.touch_playlist(playlist_id)
            self.sync_playlist_row(playlist_id)

        dpg.set_item_callback(
            "playlist_name_input",
            name_input_callback,
        )

        def description_input_callback(sender, app_data):
            self.pm.playlists[playlist_id].description = app_data
            print(f"Renamed {playlist_id} to {app_data}")
            self.touch_playlist(playlist_id)
            self.sync_playlist_row(playlist_id)

        dpg.set_item_callback(
            "playlist_description_input",
            description_input_callback,
        )

        # Set up URI table
        def delete_uri_callback(sender, app_data, user_data):
            (service_name, uri) = user_data
            print(f"Deleted {service_name} {uri}")
            self.pm.playlists[playlist_id].remove_uri(service_name, uri)
            self.touch_playlist(playlist_id)
            self.edit_playlist_row(playlist_id)

        # Delete current rows
        rows: list[int] = dpg.get_item_children("uri_table", 1)  # type: ignore
        for row in rows:
            dpg.delete_item(row)

        for service_name, uris in self.pm.playlists[playlist_id].uris.items():
            service_type = self.pm.services[service_name].type
            for uri in uris:
                with dpg.table_row(parent="uri_table"):
                    dpg.add_text(service_name)
                    hyperlink(uri.url)
                    dpg.add_button(
                        label="Delete",
                        callback=delete_uri_callback,
                        tag=f"delete_uri_button_{service_name}_{uri.url}",
                        user_data=(service_name, uri),
                    )

        dpg.set_value("playlist_url_input", "")
        # Set up service combo
        dpg.set_value("service_combo", "")
        dpg.configure_item("service_combo", items=list(self.pm.services.keys()))

        # Set up add playlist URL button
        def add_playlist_url_callback(sender, app_data):
            service_name = dpg.get_value("service_combo")
            url = dpg.get_value("playlist_url_input")
            if service_name and url:
                self.pm.playlists[playlist_id].add_uri(
                    service_name, playlistURI_from_url(url)
                )
                self.touch_playlist(playlist_id)
                self.edit_playlist_row(playlist_id)

        dpg.set_item_callback(
            "add_playlist_url_button_2",
            add_playlist_url_callback,
        )

    def add_placeholder_playlist_row(self, playlist_id: str):
        pl = self.pm.playlists[playlist_id]
        with dpg.child_window(
            tag=f"playlist_row_{playlist_id}", height=60, parent="playlist_window"
        ):
            with dpg.group(horizontal=True):
                dpg.add_text(pl.name, tag=f"playlist_row_name_{playlist_id}")
            with dpg.group(horizontal=True):
                dpg.add_text(
                    "placeholder",
                    tag=f"playlist_track_count_{playlist_id}",
                )
                dpg.add_button(
                    label="Pull",
                    tag=f"pull_button_{playlist_id}",
                    callback=lambda: self.add_job(JobType.PULL, playlist_id),
                )
                dpg.add_button(
                    label="Search",
                    tag=f"search_button_{playlist_id}",
                    callback=lambda: self.add_job(JobType.SEARCH, playlist_id),
                )
                dpg.add_button(
                    label="Push",
                    tag=f"push_button_{playlist_id}",
                    callback=lambda: self.add_job(JobType.PUSH, playlist_id),
                )

                dpg.add_button(
                    label="Edit",
                    tag=f"edit_button_{playlist_id}",
                    callback=lambda: self.edit_playlist_row(playlist_id),
                )

                dpg.add_button(
                    label="Delete",
                    tag=f"delete_button_{playlist_id}",
                    callback=lambda: self.delete_playlist(playlist_id),
                )

    def sync_playlist_list(self):
        """Remove all playlist rows and add them again."""
        for playlist in self.pm.playlists:
            # Delete row if it exists
            if dpg.does_item_exist(f"playlist_row_{playlist}"):
                dpg.delete_item(f"playlist_row_{playlist}")
            self.add_placeholder_playlist_row(playlist)
            self.sync_playlist_row(playlist)

    def sync_playlist_row(self, playlist_id: str):
        pl = self.pm.playlists[playlist_id]
        dpg.set_value(f"playlist_track_count_{playlist_id}", f"{len(pl.tracks)} tracks")
        dpg.set_value(f"playlist_row_name_{playlist_id}", pl.name)

    def delete_playlist(self, playlist_id: str):
        dpg.show_item("delete_playlist_window")
        dpg.set_value(
            "delete_playlist_text",
            f"Are you sure you want to delete {self.pm.playlists[playlist_id].name}?",
        )

        def delete_playlist_yes_callback():
            self.pm.remove_playlist(playlist_id)
            self.pm.save_index()
            self.sync_playlist_list()
            dpg.hide_item("delete_playlist_window")

        dpg.set_item_callback(
            "delete_playlist_yes_button",
            delete_playlist_yes_callback,
        )

        def delete_playlist_no_callback():
            dpg.hide_item("delete_playlist_window")

        dpg.set_item_callback(
            "delete_playlist_no_button",
            delete_playlist_no_callback,
        )

    ########################################
    # Services tab
    ########################################

    def services_tab_setup(self):
        with dpg.tab(label="Services"):
            with dpg.child_window(tag="services_window"):
                with dpg.tab_bar(tag="services_tab_bar"):

                    def add_service_tab(service_name: str):
                        with dpg.tab(
                            label=service_name, tag=f"service_tab_{service_name}"
                        ):
                            with dpg.child_window(tag=f"service_window_{service_name}"):
                                dpg.add_text(service_name)

                    for service_name in self.pm.services:
                        add_service_tab(service_name)
                    dpg.add_tab(label="+", tag="add_service_tab")


gui = GUI()


dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("Primary", True)
dpg.start_dearpygui()
dpg.destroy_context()
