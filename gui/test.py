import dearpygui.dearpygui as dpg

dpg.create_context()


def change_text(sender, app_data):
    if dpg.is_item_hovered("text item"):
        dpg.set_value("text item", f"Stop Hovering Me, Go away!!")
    else:
        dpg.set_value("text item", f"Hover Me!")


with dpg.handler_registry():
    dpg.add_mouse_move_handler(callback=change_text)

with dpg.window(width=500, height=300):
    dpg.add_text("Hover Me!", tag="text item")


dpg.create_viewport(title="Custom Title", width=800, height=600)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()
