#!/usr/bin/env python3
import sys
import gi
import time
import os
import random

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

    """This is a horrible, godawful way of fixing the issue of Stable Diffusion not liking transparent images.
       This bug has given me a lot of grief, which is why I'm typing up a comment to explain its madness.
       To fix the issue I use brute force to find a color that's not present in the image.
       I then create an image that's just this color, and superimpose the transparent image atop that background.
       This creates a composite image with no transparency and a color I can easily just blanket remove from the image.
       This is really inefficient. If by some stroke of genius I find a better solution, implement it ASAP.
    """
    def find_color_not_in_image(self, image):
        colors = {color[1] for color in image.getcolors(maxcolors=image.size[0] * image.size[1])}
        while True:
            new_color = (
                random.randint(0,255),
                random.randint(0, 255),
                random.randint(0,255)
            )
            if new_color not in colors:
                return new_color

    """This function replaces a color in Pillow Image by turning it into a numpy array. By transposing the array,
        each color can be extracted in its own 2-D array and a filter applied to set all target color values to a fully transparent
        black.
    """
    def replace_color(self, image, color):
        colors = np.array(image)
        r, g, b, a = colors.T
        to_replace = (r == color[0]) & (g == color[1]) & (b == color[2]) 
        colors[...][to_replace.T] = (0, 0, 0, 0)

        return Image.fromarray(colors)
    
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
        pipeline = diffusers.AutoPipelineForInpainting.from_pretrained("diffusers/stable-diffusion-xl-1.0-inpainting-0.1", torch_dtype=torch.float16, variant="fp16", safety_checker=None)
        
        # Check if GPU acceleration can be performed
        if torch.cuda.is_available(): # For NVIDIA GPUs
            pipeline = pipeline.to("cuda")
        elif torch.backends.mps.is_available(): # For Apple Silicon
            pipeline = pipeline.to("mps")

        if args["cpu_offload"]:
            pipeline.enable_sequential_cpu_offload()    
        
        # Resize image to 1024x1024 to fit the image size 
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
            generator=torch.Generator(device="mps").manual_seed(0),
            callback_on_step_end=AiIntegration.progress_bar_closure(float(args.get("steps", 10)) * float(args.get("strength", 0.5)))).images[0]
            
        # Resize back for good proportions    
        output_image = output_image.resize(old_size)
        return output_image

    def run(self, procedure, run_mode, image, drawables, config, run_data):
        # Init UI
        GimpUi.init("ai-integration.py")
        dialog = GimpUi.Dialog(use_header_bar=True, title="AI Inpainting")
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

        # Add checkbox for CPU usage for optimization
        performance_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        performance_box.set_border_width(10)

        cpu_checkbox = Gtk.CheckButton.new_with_label("CPU Offloading")
        performance_box.pack_start(cpu_checkbox, False, False, 0)

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

                Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path(f"{save_path}_mask.png"), None)
                # Undo all actions taken manually because undo groups aren't what I think they are
                Gimp.Image.remove_layer(image, layer)
                Gimp.Selection.invert(image)
                Gimp.Image.undo_group_end(image)

                # Hidden layers cause an alpha channel to be added to an image even if its not transparent
                mask = Image.open(f"{save_path}_mask.png")
                mask = mask.convert("RGB")
                mask.save(f"{save_path}_mask.png")

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
                Gimp.Item.set_visible(drawables[0], True) # The earlier for loop sets the selected layer invisible, so we uninvisible it
                Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path(f"{save_path}.png"), None)
                # Reset back to original state
                for layer in Gimp.Image.get_layers(image):
                    if layer not in invisibles:
                        Gimp.Item.set_visible(layer, True)
                Gimp.Image.undo_group_end(image)

                img = Image.open(f"{save_path}.png")
                img = img.convert("RGBA") # Convert to RGBA to make things compatible with the color replacement code

                if img.getextrema()[3][0] < 255: # Check if there is an alpha value that isn't fully opaque before color replacing
                    background_color = self.find_color_not_in_image(img) # Blow up computer with this atrocity
                    background_image = Image.new("RGBA", img.size, background_color)
                    img = Image.alpha_composite(background_image, img)

                img = img.convert("RGB") # Remove alpha channel
                img.save(f"{save_path}.png")

                # Init progress bar and begin inpainting process
                Gimp.progress_init("Generating inpainting...")
                inpaint = self.inpaint(
                    image=f"{save_path}.png", 
                    mask=f"{save_path}_mask.png", 
                    prompt=prompt_entry.get_text(), 
                    negative_prompt=negative_prompt_entry.get_text(),
                    steps=steps_entry.get_text(),
                    cfg=cfg_entry.get_text(),
                    strength=strength_entry.get_text(),
                    cpu_offload=cpu_checkbox.get_active())
                
                # Lazy way of checking whether to replace a background color or not.
                # The background color variable wouldn't exist if there was no replacement needed.
                # So the try-except statement just catches and drops the NameError from a nonexistent variable because nothing needs to be done.
                try:
                    self.replace_color(inpaint, background_color)
                except NameError:
                    pass

                # Save and insert inpainted image above the selected one
                inpaint.save(f"{save_path}_inpaint.png")
                inpaint_layer = Gimp.file_load_layer(Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path(f"{save_path}_inpaint.png"))
                Gimp.Item.set_name(inpaint_layer, f"{Gimp.Item.get_name(drawables[0])}_inpaint")
                Gimp.Image.insert_layer(image, inpaint_layer, None, Gimp.Image.get_layers(image).index(drawables[0]))
                Gimp.progress_end()

                # Delete all images used for inpainting process
                os.remove(f"{save_path}.png")
                os.remove(f"{save_path}_mask.png")
                os.remove(f"{save_path}_inpaint.png")
                dialog.destroy()
                return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

        else:
            dialog.destroy()
            Gimp.message("CANCEL Pressed!")

            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())


Gimp.main(AiIntegration.__gtype__, sys.argv)
