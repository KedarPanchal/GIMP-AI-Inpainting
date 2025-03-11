$gimpPath = Read-Host -Prompt "GIMP 3.0 Python Path"
$gimpPath.Trim()
Set-Location -Path $gimpPath

curl -sSL https://bootstrap.pypa.io/get-pip.py -o get-pip.py
& $gimpPath\python.exe get-pip.py
Remove-Item get-pip.py

curl -sSL https://raw.githubusercontent.com/KedarPanchal/GIMP-AI-Inpainting/refs/heads/main/requirements.txt -o requirements.txt
& $gimpPath\python.exe -m pip install -r requirements.txt
Remove-Item requirements.txt

$plugIns = Read-Host -Prompt "Enter GIMP Plug-Ins folder"
$plugIns.Trim()
Set-Location -Path $plugIns
curl -sSL https://raw.githubusercontent.com/KedarPanchal/GIMP-AI-Inpainting/refs/heads/main/ai-integration.py -o ai-integration.py
New-Item -Path $pwd.Path -Name "ai-integration" -ItemType Directory