@echo off
chcp 65001 >nul
echo ============================================
echo   Compressez PM GMod - Build .exe
echo ============================================
echo.

:: Vérifier que Python est installé
python --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR : Python introuvable.
    echo Télécharge Python 3.9+ sur https://www.python.org
    pause
    exit /b 1
)

echo [1/3] Installation des dépendances...
python -m pip install pyinstaller pillow --quiet
if errorlevel 1 (
    echo ERREUR lors de l'installation des dépendances.
    pause
    exit /b 1
)

echo [2/3] Construction de l'executable...
python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "Compressez-PM-GMod" ^
    --add-data "compressez_pm.py;." ^
    compressez_pm.py

if errorlevel 1 (
    echo ERREUR lors de la construction.
    pause
    exit /b 1
)

echo [3/3] Nettoyage...
rmdir /s /q build 2>nul
del /q "Compressez-PM-GMod.spec" 2>nul

echo.
echo ============================================
echo   OK ! Executable cree :
echo   dist\Compressez-PM-GMod.exe
echo ============================================
echo.
pause
