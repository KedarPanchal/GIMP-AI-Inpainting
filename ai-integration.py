#!/usr/bin/env python3
import sys
import gi
import time
import platform

import torch
import diffusers
from PIL import Image

gi.require_version("Gimp", "3.0")
from gi.repository import Gimp
gi.require_version("GimpUi", "3.0")
from gi.repository import GimpUi
from gi.repository import GLib
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gio


class AiIntegration(Gimp.PlugIn):
    def do_query_procedures(self):
        return ["ai-integration"]
    
    def do_set_i18n(self, name):
        False
    
    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, self.run, None)
        procedure.set_image_types("*")
        procedure.set_menu_label("AI Inpainting")
        procedure.add_menu_path("<Image>/Filters/Render/")
        procedure.set_attribution("K Panchal", "K Panchal", "2025")

        return procedure 

    def inpaint(self, image, mask, **args):
        pipeline = diffusers.AutoPipelineForInpainting.from_pretrained("diffusers/stable-diffusion-xl-1.0-inpainting-0.1", torch_dtype=torch.float16, variant="fp16", safety_checker=None)
        pipeline = pipeline.to("mps")
        pipeline.enable_attention_slicing()
        
        img = Image.open(image)
        m = Image.open(mask)
        old_size = img.size
        img = img.resize((1024, 1024))
        m = m.resize((1024, 1024))
        
        output_image = pipeline(
            prompt=args.get("prompt", ""), 
            negative_prompt=args.get("negative_prompt", ""), 
            image=img, 
            mask_image=m, 
            strength=float(args.get("strength", 0.5)), 
            guidance_scale=float(args.get("cfg", 7.5)),
            num_inference_steps=int(args.get("steps", 10)), 
            generator=torch.Generator(device="mps").manual_seed(0)).images[0]
            
        output_image = output_image.resize(old_size)
        return output_image

    def run(self, procedure, run_mode, image, drawables, config, run_data):
        # Init UI
        GimpUi.init("ai-integration.py")
        dialog = GimpUi.Dialog(use_header_bar=True, title="AI Integration")
        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("_OK", Gtk.ResponseType.OK)

        # Add input for inpaint prompt
        text_input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        text_input_box.set_border_width(10)
        prompt_label = Gtk.Label(label="Enter Prompt:")
        prompt_entry = Gtk.Entry()
        prompt_entry.set_placeholder_text("Enter prompt...")
        text_input_box.pack_start(prompt_label, False, False, 0)
        text_input_box.pack_start(prompt_entry, True, True, 0)

        dialog.get_content_area().add(text_input_box)
        dialog.show_all()

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            # No selection :(
            if Gimp.Selection.is_empty(image):
                dialog.destroy()
                Gimp.message("No selection found!")

                return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, GLib.Error(message="No Selection Found!"))
            # Yay selection :)
            else:
                Gimp.Image.undo_group_start(image)

                layer = Gimp.Layer.new_from_visible(image, image, "mask")
                Gimp.Image.insert_layer(image, layer, None, -1)
                drawable = image.get_layers()[0]
                Gimp.Drawable.edit_fill(drawable, Gimp.FillType.WHITE)
                Gimp.Selection.invert(image)
                Gimp.Drawable.edit_fill(drawable, Gimp.FillType.WHITE)
                Gimp.Drawable.invert(drawable, False)
                
                fname = time.time()
                Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path(f"{fname}_mask.png"), None)
                Gimp.Image.remove_layer(image, layer)
                Gimp.Image.undo_group_end(image)
                Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path(f"{fname}.png"), None)

                dialog.destroy()
                return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

        else:
            dialog.destroy()
            Gimp.message("CANCEL Pressed!")

            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())


Gimp.main(AiIntegration.__gtype__, sys.argv)