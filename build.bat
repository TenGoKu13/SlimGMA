@echo off
echo ============================================
echo   Slimgma - Build du .exe portable
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR : Python introuvable.
    echo Telecharge Python 3.10+ sur https://www.python.org
    pause
    exit /b 1
)

echo [1/3] Installation des dependances...
python -m pip install pyinstaller -r requirements.txt --quiet
if errorlevel 1 (
    echo ERREUR lors de l'installation des dependances.
    pause
    exit /b 1
)

echo [2/3] Construction de l'executable...
python -m PyInstaller --noconfirm --onefile --windowed --name "Slimgma" --icon assets\slimgma.ico --add-data "assets\slimgma.ico;assets" --collect-all tkinterdnd2 --collect-all srctools slimgma.py
if errorlevel 1 (
    echo ERREUR lors de la construction.
    pause
    exit /b 1
)

echo [3/3] Nettoyage...
rmdir /s /q build 2>nul
del /q "Slimgma.spec" 2>nul

echo.
echo ============================================
echo   OK ! Executable portable cree :
echo   dist\Slimgma.exe
echo.
echo   Pour un vrai programme d'installation :
echo   packaging\build_installer.bat
echo ============================================
echo.
pause
