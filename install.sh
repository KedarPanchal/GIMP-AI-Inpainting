#!/bin/bash

# Note: Do NOT run as sudo (causes whoami to break)!
if [[ "$OSTYPE" == "darwin"* ]]; then
    cd "/Applications/GIMP.app/Contents/MacOS"
    python_path="/Applications/GIMP.app/Contents/MacOS/python"
else
    # Read and change directories to where GIMP's Python version is
    read -p "GIMP 3.0 Python Path: " gimp_path
    gimp_path=$(echo "$gimp_path" | xargs)
    python_path="${gimp_path}/python"
    cd "$gimp_path"
fi

# Install pip on GIMP Python
sudo curl -sSL https://bootstrap.pypa.io/get-pip.py -o get-pip.py
$(echo "${python_path} get-pip.py")
sudo rm -rf "get-pip.py"

# Install required packages
sudo curl -sSL https://raw.githubusercontent.com/KedarPanchal/GIMP-AI-Inpainting/refs/heads/main/requirements.txt -o requirements.txt
$(echo "sudo ${python_path} -m pip install --root-user-action=ignore -r requirements.txt")
sudo rm -rf "requirements.txt"

# Download plugin to GIMP
if [[ $OSTYPE == "darwin"* ]]; then
    me=$(whoami)
    plug_in_folder="/Users/${me}/Library/Application Support/Gimp/3.0/plug-ins"
else
    read -p "Enter GIMP Plug-Ins folder: " plug_in_folder
    plug_in_folder=$(echo "$plug_in_folder" | xargs)
fi
cd "$plug_in_folder"
mkdir ai-integration && cd $_
sudo curl -sSL https://raw.githubusercontent.com/KedarPanchal/GIMP-AI-Inpainting/refs/heads/main/ai-integration.py -o ai-integration.py
sudo chmod +x ai-integration.py