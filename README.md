# GIMP AI Integration
---
This AI Integration plug-in brings inpainting capabilities to GIMP 3.0, allowing users to leverage powerful AI tools like [Stable Diffusion XL](https://huggingface.co/diffusers/stable-diffusion-xl-1.0-inpainting-0.1) to upgrade their image-editing workflow.

<img src="resources/images/beforeandafter.png" alt="A before and after image, with the before image being that of a man in a suit and the after image being the same, but the man is now wearing sunglasses that were added in using AI inpainting.">

## Table of Contents
---
* [Installation](#installation)
    * [MacOS](#macos)
    * [A note on Linux installation](#a-note-on-linux-installation)
* Usage
* Development Specifications
* LICENSE

## Installation
---
> This plug-in is only available for GIMP 3.0 and later (this includes the RC releases). In the future I may look for a method of making this compatible with GIMP 2.

### MacOS
```bash
$ curl -sSL https://raw.githubusercontent.com/KedarPanchal/GIMP-AI-Inpainting/main/install.sh -o install.sh
$ bash ./install.sh
```
Do not run the `install.sh` script with elevated privileges (i.e. as `sudo`), as this may break where the script attempts to install the plug-in.

### A note on Linux installation
Linux's distribution of GIMP 3.0—at the time of writing—comes in either AppImage or Flatpak form. Both of these formats run in a read-only sandbox environment, meaning the required dependencies for the plug-in cannot be installed. However, I do intend on seeking alternative solutions in which Python interpreters external to GIMP can be used to circumvent this issue.
