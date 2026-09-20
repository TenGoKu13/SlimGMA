@echo off
setlocal
cd /d "%~dp0\.."

echo ============================================
echo   Slimgma - Build du programme d'installation
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR : Python introuvable.
    echo Telecharge Python 3.10+ sur https://www.python.org
    pause
    exit /b 1
)

set ISCC=
for %%P in (
    "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles%\Inno Setup 6\ISCC.exe"
) do if exist %%P set ISCC=%%P
if not defined ISCC (
    where ISCC.exe >nul 2>&1 && for /f "delims=" %%P in ('where ISCC.exe') do set ISCC="%%P"
)
if not defined ISCC (
    echo ERREUR : Inno Setup introuvable.
    echo Installe-le depuis https://jrsoftware.org/isdl.php
    echo ou avec : winget install JRSoftware.InnoSetup
    pause
    exit /b 1
)

for /f "delims=" %%V in ('python -c "from cpm.constants import VERSION; print(VERSION)"') do set VERSION=%%V
if not defined VERSION (
    echo ERREUR : version illisible dans cpm\constants.py
    pause
    exit /b 1
)
echo Version : %VERSION%
echo.

echo [1/4] Installation des dependances...
python -m pip install pyinstaller -r requirements.txt --quiet
if errorlevel 1 goto fail

echo [2/4] Construction de l'application...
python -m PyInstaller --noconfirm --onedir --windowed --name "Slimgma" --icon assets\slimgma.ico --add-data "assets\slimgma.ico;assets" --collect-all tkinterdnd2 --collect-all srctools slimgma.py
if errorlevel 1 goto fail

echo [3/4] Preparation de la licence...
copy /y LICENSE packaging\LICENSE.txt >nul
if errorlevel 1 goto fail

echo [4/4] Construction de l'installateur...
%ISCC% /DAppVersion=%VERSION% packaging\slimgma.iss
if errorlevel 1 goto fail

echo.
echo ============================================
echo   OK ! Installateur cree :
echo   dist\Slimgma-Setup-%VERSION%.exe
echo ============================================
echo.
pause
exit /b 0

:fail
echo.
echo ECHEC de la construction.
pause
exit /b 1
