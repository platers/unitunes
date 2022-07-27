from pathlib import Path
import dearpygui.dearpygui as dpg
from appdirs import user_data_dir
from pydantic import BaseModel
from unitunes import PlaylistManager, FileManager, Index

dpg.create_context()
dpg.create_viewport(title="Unitunes", width=600, height=600)


class AppConfig(BaseModel):
    unitunes_dir: Path


class GUI:
    app_config: AppConfig
    pm: PlaylistManager

    def load_playlist_manager(self):
        fm = FileManager(self.app_config.unitunes_dir)
        try:
            fm.load_index()
        except FileNotFoundError:
            # Create a new index if it doesn't exist
            fm.save_index(Index())
            print(f"Created new index at {fm.index_path.absolute()}")

        self.pm = PlaylistManager(fm.load_index(), fm)

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

    def playlists_tab_setup(self):
        with dpg.tab(label="Playlists"):
            with dpg.child_window(tag="playlist_window"):

                def add_playlist_row(name: str):
                    with dpg.child_window(tag=f"playlist_row_{name}", height=40):
                        with dpg.group(horizontal=True):
                            dpg.add_text(name)

                for playlist in self.pm.playlists:
                    add_playlist_row(playlist)

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

    def main_window_setup(self):
        with dpg.window(label="Example Window", tag="Primary"):
            with dpg.tab_bar():
                self.playlists_tab_setup()
                self.services_tab_setup()
                self.settings_tab_setup()

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

    def setup(self):
        self.load_app_config()
        self.load_playlist_manager()
        self.main_window_setup()


gui = GUI()
gui.setup()


dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("Primary", True)
dpg.start_dearpygui()
dpg.destroy_context()
