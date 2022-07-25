import dearpygui.dearpygui as dpg

dpg.create_context()
dpg.create_viewport(title="Custom Title", width=600, height=600)


def settings_tab_setup():
    with dpg.tab(label="Settings"):
        dpg.add_text("This is the settings tab!")


def playlists_tab_setup():
    with dpg.tab(label="Playlists"):
        with dpg.child_window(tag="playlist_window"):
            dpg.add_text("This is the playlist window!")


def add_playlist_row(name: str):
    with dpg.child_window(
        tag=f"playlist_row_{name}", parent="playlist_window", height=40
    ):
        with dpg.group(horizontal=True):
            dpg.add_text(name)


def services_tab_setup():
    with dpg.tab(label="Services"):
        dpg.add_text("This is the services tab!")


def main_window_setup():
    with dpg.window(label="Example Window", tag="Primary"):
        with dpg.tab_bar():
            playlists_tab_setup()
            services_tab_setup()
            settings_tab_setup()


main_window_setup()

for i in range(10):
    add_playlist_row(str(i))


dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("Primary", True)
dpg.start_dearpygui()
dpg.destroy_context()
