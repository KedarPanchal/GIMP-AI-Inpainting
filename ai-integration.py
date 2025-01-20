#!/usr/bin/env python3
import sys
import gi

gi.require_version("Gimp", "3.0")
from gi.repository import Gimp
gi.require_version("GimpUi", "3.0")
from gi.repository import GimpUi
from gi.repository import GLib
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

class AiIntegration(Gimp.PlugIn):
    def do_query_procedures(self):
        return ["ai-integration"]
    
    def do_set_i18n(self, name):
        False
    
    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, self.run, None)
        procedure.set_image_types("*")
        procedure.set_menu_label("Flux 1.x generative AI integration in GIMP")
        procedure.add_menu_path("<Image>/Filters/Render/")
        procedure.set_attribution("K Panchal", "K Panchal", "2024")

        return procedure

    def run(self, procedure, run_mode, image, drawables, config, run_data):
        GimpUi.init("ai-integration.py")
        dialog = GimpUi.Dialog(use_header_bar=True, title="AI Integration")
        dialog.set_size_request(300, 400)
        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("_OK", Gtk.ResponseType.OK)

        while True:
            response = dialog.run()
            if response == Gtk.ResponseType.OK:
                dialog.destroy()
                Gimp.message("OK Pressed!")
                break
            else:
                dialog.destroy()
                Gimp.message("CANCEL Pressed!")
                dialog.destroy()

        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

Gimp.main(AiIntegration.__gtype__, sys.argv)