from pathlib import Path
import dearpygui.dearpygui as dpg
from appdirs import user_data_dir
from pydantic import BaseModel

dpg.create_context()
dpg.create_viewport(title="Custom Title", width=600, height=600)


class AppConfig(BaseModel):
    unitunes_dir: Path


class GUI:
    app_config: AppConfig

    def settings_tab_setup(self):
        with dpg.tab(label="Settings"):
            with dpg.child_window(tag="settings_window"):

                with dpg.group(horizontal=True):

                    def change_unitunes_dir(sender, app_data):
                        print(sender, app_data)
                        self.app_config.unitunes_dir = Path(app_data["current_path"])
                        self.save_app_config()
                        update_unitunes_dir_text()

                    def update_unitunes_dir_text():
                        dpg.set_item_label(
                            "unitunes_dir_button",
                            str(self.app_config.unitunes_dir),
                        )

                    file_dialog = dpg.add_file_dialog(
                        label="Unitunes Directory",
                        tag="unitunes_dir_dialog",
                        directory_selector=True,
                        show=False,
                        height=300,
                        callback=change_unitunes_dir,
                    )

                    dpg.add_text(
                        "Unitunes Directory:",
                    )
                    dpg.add_button(
                        tag="unitunes_dir_button",
                        label="placeholder",
                        callback=lambda: dpg.show_item(file_dialog),
                    )
                    update_unitunes_dir_text()

    def playlists_tab_setup(self):
        with dpg.tab(label="Playlists"):
            with dpg.child_window(tag="playlist_window"):
                dpg.add_text("This is the playlist window!")

    def add_playlist_row(self, name: str):
        with dpg.child_window(
            tag=f"playlist_row_{name}", parent="playlist_window", height=40
        ):
            with dpg.group(horizontal=True):
                dpg.add_text(name)

    def services_tab_setup(self):
        with dpg.tab(label="Services"):
            dpg.add_text("This is the services tab!")

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
        self.main_window_setup()


gui = GUI()
gui.setup()

for i in range(10):
    gui.add_playlist_row(str(i))


dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("Primary", True)
dpg.start_dearpygui()
dpg.destroy_context()
