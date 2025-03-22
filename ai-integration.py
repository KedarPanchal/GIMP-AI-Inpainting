#!/usr/bin/env python3
import sys
import gi
import time
import os
import random
import json

import torch
import diffusers
import numpy as np
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

    def get_transparent_coords(self, image):
        pixels = np.array(image) 
        y, x = np.where(pixels[..., 3] < 255)
        colors = [tuple(color) for color in pixels[y, x]]
        return list(zip(zip(x, y), colors))

    """This is a horrible, godawful way of fixing the issue of Stable Diffusion not liking transparent images.
       This bug has given me a lot of grief, which is why I'm typing up a comment to explain its madness.
       To fix the issue I use brute force to find a color that's not present in the image.
       I then create an image that's just this color, and superimpose the transparent image atop that background.
       This creates a composite image with no transparency and a color I can easily just blanket remove from the image.
       This is really inefficient. If by some stroke of genius I find a better solution, implement it ASAP.
    """
    def find_color_not_in_image(self, image):
        colors = {color[1] for color in image.getcolors(maxcolors=image.size[0] * image.size[1])}

        if len(colors) >= 255 ** 3:
            raise ValueError("Too many colors in image!")

        while True:
            new_color = (
                random.randint(0,255),
                random.randint(0, 255),
                random.randint(0,255),
                255
            )
            if new_color not in colors:
                return new_color
    
    """Deletes all intermediate and temporary files used during the inpainting process, if they exist
    """
    def cleanup(self, fpath):
        def delete_if_exists(name):
            if os.path.exists(name):
                os.remove(name)
        
        delete_if_exists(f"{fpath}.png")
        delete_if_exists(f"{fpath}_mask.png")
        delete_if_exists(f"{fpath}_inpaint.png")

    """The callback function used for updating the progress bar doesn't accept other parameters other than the ones provided in the documentation.
        In order to work around this to pass the total steps in the image as a parameter, a closure can be used that takes in the total steps parameter
        and returns a function that follows the specification of a pipeline callback but still has information regarding the total steps used in the inpainting generation.
    """
    def progress_bar_closure(total_steps):
        def progress_bar_callback(pipe, step_index, timestep, callback_kwargs):
            Gimp.progress_update(float(step_index)/total_steps)
            return callback_kwargs
        
        return progress_bar_callback

    """The function where the second-most brunt work is done. This performs the actual AI inpainting.
        Arguments are given as kwargs to improve the readability of the function signature and also to make
        adding extra parameters easier in the future. Currently, the supported kwargs are:
        1. CPU Offloading
        2. Prompt
        3. Negative Prompt
        4. Strength
        5. CFG Scale
        6. Steps
    """
    def inpaint(self, image, mask, **args):
        getter = lambda param, default: default if args[param] == "" else args[param]

        pipeline = diffusers.AutoPipelineForInpainting.from_pretrained("diffusers/stable-diffusion-xl-1.0-inpainting-0.1", torch_dtype=torch.float16, variant="fp16", safety_checker=None)
        
        # Check if GPU acceleration can be performed
        if torch.cuda.is_available(): # For NVIDIA GPUs
            pipeline = pipeline.to("cuda")
        elif torch.backends.mps.is_available(): # For Apple Silicon
            pipeline = pipeline.to("mps")

        if args["cpu_offload"]:
            pipeline.enable_sequential_cpu_offload()    
        
        # Resize image to 1024x1024 to fit the image size 
        old_size = image.size
        image = image.resize((1024, 1024))
        mask = mask.resize((1024, 1024))
        
        output_image = pipeline(
            prompt=getter("prompt", ""), 
            negative_prompt=getter("negative_prompt", ""), 
            image=image, 
            mask_image=mask, 
            strength=float(getter("strength", 0.5)), 
            guidance_scale=float(getter("cfg", 7.5)),
            num_inference_steps=int(getter("steps", 10)), 
            generator=torch.Generator(device="mps").manual_seed(int(getter("seed", 0))),
            callback_on_step_end=AiIntegration.progress_bar_closure(float(getter("steps", 10)) * float(getter("strength", 0.5)))).images[0]
            
        # Resize back for good proportions    
        output_image = output_image.resize(old_size)
        return output_image

    def run(self, procedure, run_mode, image, drawables, config, run_data):
        # Init UI
        GimpUi.init("ai-integration.py")
        dialog = GimpUi.Dialog(use_header_bar=True, title="AI Inpainting")
        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("_OK", Gtk.ResponseType.OK)

        # Load existing config if it's there
        if os.path.exists("config.json"):
            with open("config.json", "r") as config:
                parameters = json.load(config)
        else: # Otherwise init a config dictionary with default values
            parameters = {
                "prompt": "",
                "negative_prompt": "",
                "steps": "10",
                "cfg": "7.5",
                "strength": "0.5",
                "seed": f"{round(time.time())}",
                "cpu": False,
                "transparency": True
            }

        # Add input for inpaint prompt
        text_input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        text_input_box.set_border_width(10)
        prompt_label = Gtk.Label(label="Prompt:")
        prompt_entry = Gtk.Entry()
        prompt_entry.set_placeholder_text("Enter prompt...")
        prompt_entry.set_text(parameters["prompt"])

        text_input_box.pack_start(prompt_label, False, False, 0)
        text_input_box.pack_start(prompt_entry, True, True, 0)

        # Add input for negative inpaint prompt
        negative_input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        negative_input_box.set_border_width(10)
        negative_prompt_label = Gtk.Label(label="Negative Prompt:")
        negative_prompt_entry = Gtk.Entry()
        negative_prompt_entry.set_placeholder_text("Enter negative prompt...")
        negative_prompt_entry.set_text(parameters["negative_prompt"])

        negative_input_box.pack_start(negative_prompt_label, False, False, 0)
        negative_input_box.pack_start(negative_prompt_entry, True, True, 0)

        # Add input for steps, CFG, strength
        parameter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        parameter_box.set_border_width(10)

        steps_label = Gtk.Label(label="Steps:")
        steps_entry = Gtk.Entry()
        steps_entry.set_input_purpose(Gtk.InputPurpose.DIGITS)
        steps_entry.set_width_chars(5)
        steps_entry.set_text(parameters["steps"])

        cfg_label = Gtk.Label(label="CFG:")
        cfg_entry = Gtk.Entry()
        cfg_entry.set_input_purpose(Gtk.InputPurpose.NUMBER)
        cfg_entry.set_width_chars(5)
        cfg_entry.set_text(parameters["cfg"])

        strength_label = Gtk.Label(label="Strength:")
        strength_entry = Gtk.Entry()
        strength_entry.set_input_purpose(Gtk.InputPurpose.NUMBER)
        strength_entry.set_width_chars(5)
        strength_entry.set_text(parameters["strength"])

        seed_label = Gtk.Label(label="Seed:")
        seed_entry = Gtk.Entry()
        seed_entry.set_input_purpose(Gtk.InputPurpose.DIGITS)
        seed_entry.set_text(parameters["seed"])

        parameter_box.pack_start(steps_label, False, False, 0)
        parameter_box.pack_start(steps_entry, False, False, 0)

        parameter_box.pack_start(cfg_label, False, False, 0)
        parameter_box.pack_start(cfg_entry, False, False, 0)

        parameter_box.pack_start(strength_label, False, False, 0)
        parameter_box.pack_start(strength_entry, False, False, 0)

        parameter_box.pack_start(seed_label, False, False, 0)
        parameter_box.pack_start(seed_entry, True, True, 0)

        # Add checkbox for CPU usage for optimization and for preserving transparency
        performance_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        performance_box.set_border_width(10)

        cpu_checkbox = Gtk.CheckButton.new_with_label("CPU Offloading")
        cpu_checkbox.set_active(parameters["cpu"])

        config_checkbox = Gtk.CheckButton.new_with_label("Save configuration:")
        config_checkbox.set_active(os.path.exists("config.json"))

        transparency_checkbox = Gtk.CheckButton.new_with_label("Preserve Transparency")
        transparency_checkbox.set_active(parameters["transparency"])

        performance_box.pack_start(cpu_checkbox, False, False, 0)
        performance_box.pack_start(config_checkbox, False, False, 0)
        performance_box.pack_start(transparency_checkbox, False, False, 0)

        dialog.get_content_area().add(text_input_box)
        dialog.get_content_area().add(negative_input_box)
        dialog.get_content_area().add(parameter_box)
        dialog.get_content_area().add(performance_box)
        dialog.show_all()

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            if config_checkbox.get_active():
                write_dict = {
                    "prompt": prompt_entry.get_text(),
                    "negative_prompt": negative_prompt_entry.get_text(),
                    "steps": steps_entry.get_text(),
                    "cfg": cfg_entry.get_text(),
                    "strength": strength_entry.get_text(),
                    "seed": seed_entry.get_text(),
                    "cpu": cpu_checkbox.get_active(),
                    "transparency": transparency_checkbox.get_active()
                }

                json_to_write = json.dumps(write_dict, indent=4)
                with open("config.json", "w") as config:
                    config.write(json_to_write)
            elif os.path.exists("config.json"): # Delete config if the settings aren't set to save the config file
                os.remove("config.json")

            # No selection :(
            if Gimp.Selection.is_empty(image):
                dialog.destroy()
                Gimp.message("No selection found!")

                return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, GLib.Error(message="No Selection Found!"))
            # Yay selection :)
            else:
                Gimp.Image.undo_group_start(image) # This is useless at the moment but in case GIMP unuselesses it then this will be good
                fname = time.time() # time.time() would give a unique name for a PNG
                # Create layer for mask and insert at top
                layer = Gimp.Layer.new_from_visible(image, image, f"{fname}")
                Gimp.Image.insert_layer(image, layer, None, 0)
                drawable = image.get_layers()[0]
                Gimp.Drawable.edit_fill(drawable, Gimp.FillType.WHITE)
                Gimp.Selection.invert(image)
                Gimp.Drawable.edit_fill(drawable, Gimp.FillType.WHITE)
                Gimp.Drawable.invert(drawable, False)
                
                save_path = os.path.join(os.path.expanduser("~/Documents"), f"{fname}") # Save to Documents for now

                if not Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path(f"{save_path}_mask.png"), None):
                    self.cleanup(save_path)
                    dialog.destroy()
                    return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error(message="Unable to save image mask!"))
                
                # Undo all actions taken manually because undo groups aren't what I think they are
                Gimp.Image.remove_layer(image, layer)
                Gimp.Selection.invert(image)
                Gimp.Image.undo_group_end(image)

                # Hidden layers cause an alpha channel to be added to an image even if its not transparent
                mask = Image.open(f"{save_path}_mask.png")
                mask = mask.convert("RGB")

                Gimp.Image.undo_group_start(image)
                # Track already hidden layers
                invisibles = []
                # Set all nonselected layers to hidden
                for layer in Gimp.Image.get_layers(image):
                    if not Gimp.Item.get_visible(layer):
                        invisibles.append(layer)
                    else:
                        Gimp.Item.set_visible(layer, False)

                # Save image with only the selected layers
                Gimp.Item.set_visible(drawables[0], True) # The earlier for loop sets the selected layer invisible, so I uninvisible it
                if not Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path(f"{save_path}.png"), None):
                    self.cleanup(save_path)
                    dialog.destroy()
                    return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error(message="Unable to save image!"))
                
                # Reset back to original state
                for layer in Gimp.Image.get_layers(image):
                    if layer not in invisibles:
                        Gimp.Item.set_visible(layer, True)
                Gimp.Image.undo_group_end(image)

                img = Image.open(f"{save_path}.png")
                img = img.convert("RGBA") # Convert to RGBA to make things compatible with the color replacement code

                reference_coords = None
                try:
                    if img.getextrema()[3][0] < 255: # Check if there is an alpha value that isn't fully opaque before color replacing
                        reference_coords = self.get_transparent_coords(img)
                        background_color = self.find_color_not_in_image(img) # Blow up computer with this atrocity
                        background_image = Image.new("RGBA", img.size, background_color)
                        img = Image.alpha_composite(background_image, img)
                except Exception as e:
                    self.cleanup(save_path)
                    dialog.destroy()

                    return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, GLib.Error(message=f"Exception occurred when correcting for transparency: {repr(e)}"))

                img = img.convert("RGB") # Remove alpha channel

                # Init progress bar and begin inpainting process
                Gimp.progress_init("Generating inpainting...")
                inpaint = None
                try:
                    inpaint = self.inpaint(
                        image=img, 
                        mask=mask, 
                        prompt=prompt_entry.get_text(), 
                        negative_prompt=negative_prompt_entry.get_text(),
                        steps=steps_entry.get_text(),
                        cfg=cfg_entry.get_text(),
                        seed=seed_entry.get_text(),
                        strength=strength_entry.get_text(),
                        cpu_offload=cpu_checkbox.get_active())
                except Exception as e:
                    self.cleanup(save_path)
                    dialog.destroy()
                    return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error(message=f"Exception occurred when inpainting image: {repr(e)}"))
                    
                # Revert transparency of inpainted image
                inpaint = inpaint.convert("RGBA")
                if reference_coords is not None and transparency_checkbox.get_active():
                    for coord in reference_coords:
                        if mask.getpixel(coord[0]) != (255, 255, 255):
                            inpaint.putpixel(coord[0], coord[1])

                # Save and insert the inpainted image above the selected layer
                inpaint.save(f"{save_path}_inpaint.png")
                inpaint_layer = Gimp.file_load_layer(Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path(f"{save_path}_inpaint.png"))
                Gimp.Item.set_name(inpaint_layer, f"{Gimp.Item.get_name(drawables[0])}_inpaint")
                Gimp.Image.insert_layer(image, inpaint_layer, None, Gimp.Image.get_layers(image).index(drawables[0]))
                Gimp.progress_end()
                
                Gimp.Selection.none(image)

                # Delete all images used for inpainting process
                self.cleanup(save_path)
                dialog.destroy()
                return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

        else:
            dialog.destroy()
            Gimp.message("CANCEL Pressed!")

            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())


Gimp.main(AiIntegration.__gtype__, sys.argv)