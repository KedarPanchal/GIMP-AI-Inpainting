Set-Location -Path "C:\Users\$([Environment]::UserName)\AppData\Local\Programs\GIMP 3\bin"

curl -sSL https://bootstrap.pypa.io/get-pip.py -o get-pip.py
& "$(Get-Location)\pythonw.exe" get-pip.py
Remove-Item get-pip.py

curl -sSL https://raw.githubusercontent.com/KedarPanchal/GIMP-AI-Inpainting/refs/heads/main/requirements.txt -o requirements.txt
& "$(Get-Location)\pythonw.exe" -m pip install -r requirements.txt
Remove-Item requirements.txt

Set-Location -Path "C:\Users\$([Environment]::UserName)\AppData\Local\Programs\GIMP 3\lib\gimp\3.0\plug-ins"
curl -sSL https://raw.githubusercontent.com/KedarPanchal/GIMP-AI-Inpainting/refs/heads/main/ai-integration.py -o ai-integration.py
New-Item -Path $pwd.Path -Name "ai-integration" -ItemType Directory