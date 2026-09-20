import struct
import json
import time
import binascii


class GMAFile:
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
            f.read(8)
            f.read(8)

            if version > 1:
                while self._read_str(f):
                    pass

            self.name = self._read_str(f)
            raw_desc = self._read_str(f)
            try:
                desc_obj = json.loads(raw_desc)
                self.description = desc_obj.get('description', raw_desc)
            except (json.JSONDecodeError, TypeError):
                self.description = raw_desc
            self.author = self._read_str(f)
            f.read(4)

            file_index = []
            while True:
                num = struct.unpack('<I', f.read(4))[0]
                if num == 0:
                    break
                name = self._read_str(f)
                size = struct.unpack('<q', f.read(8))[0]
                f.read(4)
                file_index.append((name, size))

            for name, size in file_index:
                self.files[name] = f.read(size)

    def save(self, filepath: str) -> None:
        with open(filepath, 'wb') as f:
            f.write(self.MAGIC)
            f.write(struct.pack('B', 3))
            f.write(struct.pack('<Q', 0))
            f.write(struct.pack('<Q', int(time.time())))
            f.write(b'\x00')

            self._write_str(f, self.name)
            desc_json = json.dumps({
                "description": self.description,
                "type": "playermodel",
                "tags": [],
            })
            self._write_str(f, desc_json)
            self._write_str(f, self.author)
            f.write(struct.pack('<i', 1))

            file_list = sorted(
                (name.replace('\\', '/').lower(), data)
                for name, data in self.files.items()
                if name.replace('\\', '/').lower() != 'addon.json'
            )
            for i, (name, data) in enumerate(file_list, 1):
                f.write(struct.pack('<I', i))
                self._write_str(f, name)
                f.write(struct.pack('<q', len(data)))
                f.write(struct.pack('<I', binascii.crc32(data) & 0xFFFFFFFF))
            f.write(struct.pack('<I', 0))

            for _, data in file_list:
                f.write(data)

    @staticmethod
    def _read_str(f) -> str:
        buf = bytearray()
        while True:
            c = f.read(1)
            if c in (b'\x00', b''):
                break
            buf.extend(c)
        return buf.decode('utf-8', errors='replace')

    @staticmethod
    def _write_str(f, s: str) -> None:
        f.write(s.encode('utf-8') + b'\x00')
