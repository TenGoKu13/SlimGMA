$ErrorActionPreference = 'Stop'

$version = (python -c "from cpm.constants import VERSION; print(VERSION)").Trim()
if (-not $version) { throw "Version illisible dans cpm/constants.py" }
Write-Host "Version : $version"

python -m PyInstaller --noconfirm --onedir --windowed `
  --name "Slimgma" --icon assets/slimgma.ico `
  --add-data "assets/slimgma.ico;assets" `
  --collect-all tkinterdnd2 --collect-all srctools slimgma.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller a échoué" }

if (-not (Test-Path 'dist/Slimgma/Slimgma.exe')) {
  throw "dist/Slimgma/Slimgma.exe est absent — PyInstaller n'a rien produit"
}

Copy-Item LICENSE packaging/LICENSE.txt -Force

$iscc = Get-ChildItem -Path @(
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
) -ErrorAction SilentlyContinue | Select-Object -First 1

if (-not $iscc) {
  Write-Host "Inno Setup absent, installation via Chocolatey..."
  choco install innosetup -y --no-progress
  if ($LASTEXITCODE -ne 0) { throw "Installation d'Inno Setup impossible" }
  $iscc = Get-ChildItem -Path @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
  ) -ErrorAction SilentlyContinue | Select-Object -First 1
}
if (-not $iscc) { throw "ISCC.exe introuvable après installation" }
Write-Host "ISCC : $($iscc.FullName)"

& $iscc.FullName "/DAppVersion=$version" packaging/slimgma.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup a échoué" }

$setup = "dist/Slimgma-Setup-$version.exe"
if (-not (Test-Path $setup)) { throw "$setup est absent" }
$size = [math]::Round((Get-Item $setup).Length / 1MB, 1)
Write-Host "Installateur : $setup ($size Mo)"
