#!/bin/bash

read -p "GIMP 3.0 Python Path: " gimp_path
gimp_path=$(echo "$gimp_path" | xargs)
python_path="${gimp_path}/python"
cd "$gimp_path"

sudo curl -sSL https://bootstrap.pypa.io/get-pip.py -o get-pip.py
$(echo "${python_path} get-pip.py")
sudo rm -rf "get-pip.py"

sudo curl -sSL https://raw.githubusercontent.com/KedarPanchal/GIMP-AI-Inpainting/refs/heads/main/requirements.txt -o requirements.txt
$(echo "sudo ${python_path} -m pip install -r requirements.txt")
sudo rm -rf "requirements.txt"

read -p "Enter GIMP Plug-Ins folder: " plug_in_folder
plug_in_folder=$(echo "$plug_in_folder" | xargs)
cd "$plug_in_folder"
sudo curl -sSL https://raw.githubusercontent.com/KedarPanchal/GIMP-AI-Inpainting/refs/heads/main/ai-integration.py -o ai-integration.py
mkdir ai-integration
mv ai-integration.py ai-integration
sudo chmod +x ai-integration/ai-integration.py