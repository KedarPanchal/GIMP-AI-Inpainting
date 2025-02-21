#!/usr/bin/env python3
import sys
import gi
import time
import platform
import re

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
        
        if torch.cuda.is_available():
            pipeline = pipeline.to("cuda")
        elif torch.backends.mps.is_available():
            pipeline = pipeline.to("mps")

        if args["cpu_offload"]:
            pipeline.enable_sequential_cpu_offload()    

        if args["attention_slicing"]:
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
        prompt_label = Gtk.Label(label="Prompt:")
        prompt_entry = Gtk.Entry()
        prompt_entry.set_placeholder_text("Enter prompt...")
        text_input_box.pack_start(prompt_label, False, False, 0)
        text_input_box.pack_start(prompt_entry, True, True, 0)

        # Add input for negative inpaint prompt
        negative_input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        negative_input_box.set_border_width(10)
        negative_prompt_label = Gtk.Label(label="Negative Prompt:")
        negative_prompt_entry = Gtk.Entry()
        negative_prompt_entry.set_placeholder_text("Enter negative prompt...")
        negative_input_box.pack_start(negative_prompt_label, False, False, 0)
        negative_input_box.pack_start(negative_prompt_entry, True, True, 0)

        # Add input for steps, CFG, strength
        parameter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        parameter_box.set_border_width(10)

        steps_label = Gtk.Label(label="Steps:")
        steps_entry = Gtk.Entry()
        steps_entry.set_input_purpose(Gtk.InputPurpose.DIGITS)
        steps_entry.set_width_chars(5)
        steps_entry.set_text("10")

        cfg_label = Gtk.Label(label="CFG:")
        cfg_entry = Gtk.Entry()
        cfg_entry.set_input_purpose(Gtk.InputPurpose.NUMBER)
        cfg_entry.set_width_chars(5)
        cfg_entry.set_text("7.5")

        strength_label = Gtk.Label(label="Strength:")
        strength_entry = Gtk.Entry()
        strength_entry.set_input_purpose(Gtk.InputPurpose.NUMBER)
        strength_entry.set_width_chars(5)
        strength_entry.set_text("0.5")

        seed_label = Gtk.Label(label="Seed:")
        seed_entry = Gtk.Entry()
        seed_entry.set_input_purpose(Gtk.InputPurpose.DIGITS)
        seed_entry.set_text(f"{round(time.time())}")

        parameter_box.pack_start(steps_label, False, False, 0)
        parameter_box.pack_start(steps_entry, False, False, 0)

        parameter_box.pack_start(cfg_label, False, False, 0)
        parameter_box.pack_start(cfg_entry, False, False, 0)

        parameter_box.pack_start(strength_label, False, False, 0)
        parameter_box.pack_start(strength_entry, False, False, 0)

        parameter_box.pack_start(seed_label, False, False, 0)
        parameter_box.pack_start(seed_entry, True, True, 0)

        # Add checkboxes for CPU usage & performance optimization
        performance_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        performance_box.set_border_width(10)

        cpu_checkbox = Gtk.CheckButton.new_with_label("CPU Offloading")
        slicing_checkbox = Gtk.CheckButton.new_with_label("Attention Slicing (recommended for low VRAM computers)")

        performance_box.pack_start(cpu_checkbox, False, False, 0)
        performance_box.pack_start(slicing_checkbox, False, False, 0)

        dialog.get_content_area().add(text_input_box)
        dialog.get_content_area().add(negative_input_box)
        dialog.get_content_area().add(parameter_box)
        dialog.get_content_area().add(performance_box)
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
                Gimp.Selection.invert(image)
                Gimp.Image.undo_group_end(image)
                Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path(f"{fname}.png"), None)

                self.inpaint(
                    image=f"{fname}.png", 
                    mask=f"{fname}_mask.png", 
                    prompt=prompt_entry.get_text(), 
                    negative_prompt=negative_prompt_entry.get_text(),
                    steps=steps_entry.get_text(),
                    cfg=cfg_entry.get_text(),
                    strength=strength_entry.get_text(),
                    cpu_offload=cpu_checkbox.get_active(),
                    attention_slicing=slicing_checkbox.get_active()).show()
                dialog.destroy()
                return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

        else:
            dialog.destroy()
            Gimp.message("CANCEL Pressed!")

            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())


Gimp.main(AiIntegration.__gtype__, sys.argv)