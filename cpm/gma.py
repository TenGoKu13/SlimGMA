"""Lecteur / écrivain du format d'addon Garry's Mod (.gma)."""
import struct
import json
import time
import binascii


class GMAFile:
    """Gestion du format d'addon Garry's Mod (.gma)"""

    MAGIC = b'GMAD'

    def __init__(self):
        self.name = ""
        self.description = ""
        self.author = ""
        self.files: dict[str, bytes] = {}

    def load(self, filepath: str) -> None:
        with open(filepath, 'rb') as f:
            if f.read(4) != self.MAGIC:
                raise ValueError("Fichier GMA invalide (magic bytes incorrects)")

            version = struct.unpack('B', f.read(1))[0]
            f.read(8)   # steamid (ignoré)
            f.read(8)   # timestamp (ignoré)

            if version > 1:
                while self._read_str(f):
                    pass  # required content, obsolète

            self.name = self._read_str(f)
            raw_desc = self._read_str(f)
            try:
                desc_obj = json.loads(raw_desc)
                self.description = desc_obj.get('description', raw_desc)
            except (json.JSONDecodeError, TypeError):
                self.description = raw_desc
            self.author = self._read_str(f)
            f.read(4)   # addon version int

            # Index des fichiers
            file_index = []
            while True:
                num = struct.unpack('<I', f.read(4))[0]
                if num == 0:
                    break
                name = self._read_str(f)
