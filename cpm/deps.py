"""Dépendances optionnelles et détection d'environnement."""
import subprocess


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


def _check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, timeout=5)
        return True
    except Exception:
        return False


FFMPEG_AVAILABLE = _check_ffmpeg()
