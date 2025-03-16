#!/bin/bash
# This does not work on current Linux installations as flatpak and AppImage (the available versions of the GIMP 3.0 RCS) have read-only environments for their python instances (so pip won't work)
# Note: Do NOT run as sudo (causes whoami to break)!
cd "/Applications/GIMP.app/Contents/MacOS"
python_path="/Applications/GIMP.app/Contents/MacOS/python"

# Install pip on GIMP Python
sudo curl -sSL https://bootstrap.pypa.io/get-pip.py -o get-pip.py
$(echo "sudo ${python_path} get-pip.py")
sudo rm -f "get-pip.py"

# Install required packages
sudo curl -sSL https://raw.githubusercontent.com/KedarPanchal/GIMP-AI-Inpainting/refs/heads/main/requirements.txt -o requirements.txt
$(echo "sudo ${python_path} -m pip install --root-user-action=ignore --break-system-packages -r requirements.txt")
sudo rm -f "requirements.txt"

# Download plugin to GIMP
me=$(whoami)
cd "/Users/${me}/Library/Application Support/Gimp/3.0/plug-ins"
mkdir ai-integration && cd $_
sudo curl -sSL https://raw.githubusercontent.com/KedarPanchal/GIMP-AI-Inpainting/refs/heads/main/ai-integration.py -o ai-integration.py
sudo chmod +x ai-integration.py