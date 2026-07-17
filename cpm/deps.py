"""Dépendances optionnelles et détection d'environnement."""
import subprocess
import sys


try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    Image = None
    PIL_AVAILABLE = False

try:
    import vtflib
    VTFLIB_AVAILABLE = True
except ImportError:
    vtflib = None
    VTFLIB_AVAILABLE = False


# Sous Windows, un exécutable PyInstaller « windowed » fait clignoter une
# console à chaque subprocess sans ce flag.
SUBPROCESS_FLAGS = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if sys.platform == 'win32' else 0


def run_hidden(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """subprocess.run sans fenêtre console sous Windows."""
    return subprocess.run(cmd, creationflags=SUBPROCESS_FLAGS, **kwargs)


def _check_ffmpeg():
    try:
        run_hidden(['ffmpeg', '-version'], capture_output=True, check=True, timeout=5)
        return True
    except Exception:
        return False


FFMPEG_AVAILABLE = _check_ffmpeg()
