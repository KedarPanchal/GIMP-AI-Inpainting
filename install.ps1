Set-Location -Path "C:\Users\$([Environment]::UserName)\AppData\Local\Programs\GIMP 3\bin"

Invoke-WebRequest -Uri https://bootstrap.pypa.io/get-pip.py -OutFile get-pip.py
& "$(Get-Location)\python.exe" --break-system-packages get-pip.py
Remove-Item get-pip.py

Invoke-WebRequest -Uri https://raw.githubusercontent.com/KedarPanchal/GIMP-AI-Inpainting/refs/heads/main/requirements.txt -OutFile requirements.txt
& "$(Get-Location)\python.exe" -m pip install --break-system-packages cat -r requirements.txt
Remove-Item requirements.txt

Set-Location -Path "C:\Users\$([Environment]::UserName)\AppData\Local\Programs\GIMP 3\lib\gimp\3.0\plug-ins"
Invoke-WebRequest -Uri https://raw.githubusercontent.com/KedarPanchal/GIMP-AI-Inpainting/refs/heads/main/ai-integration.py -OutFile ai-integration.py
New-Item -Path $pwd.Path -Name "ai-integration" -ItemType Directory