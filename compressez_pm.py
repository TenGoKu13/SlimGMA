#!/usr/bin/env python3
# Requires Python 3.9+ (Windows 64-bit compatible)
"""
Compressez PM GMod
Outil de compression d'addons Playermodel pour Garry's Mod
"""
from __future__ import annotations

import os
import sys
import struct
import json
import shutil
import zipfile
import threading
import time
import re
import binascii
import subprocess
import tempfile
from pathlib import Path
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, scrolledtext, messagebox
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

# ─── Dépendances optionnelles ────────────────────────────────────────────────

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import vtflib
    VTFLIB_AVAILABLE = True
except ImportError:
    VTFLIB_AVAILABLE = False

def _check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, timeout=5)
        return True
    except Exception:
        return False

FFMPEG_AVAILABLE = _check_ffmpeg()

# ─── Constantes ──────────────────────────────────────────────────────────────

VERSION = "1.0.0"

# Patterns de fichiers C-Hands (bras à la première personne)
CHAND_PATTERNS = [
    r"models/weapons/c_.*",
    r"materials/models/weapons/c_.*",
    r"models/weapons/cstrike/c_.*",
    r"materials/models/weapons/cstrike/c_.*",
    r"models/weapons/v_.*_c\..*",
]

# Extensions de fichiers inutiles (documentation, sources PSD, etc.)
USELESS_EXTENSIONS = {
    '.txt', '.md', '.pdf', '.doc', '.docx', '.nfo', '.log',
    '.bat', '.sh', '.psd', '.xcf', '.ai', '.eps',
}

# Extensions de textures supportées
TEXTURE_EXTENSIONS = {'.vtf', '.png', '.jpg', '.jpeg', '.tga', '.bmp'}

# Extensions de sons supportées
SOUND_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.flac', '.aif', '.aiff'}

# Formats d'image VTF : id -> (nom, octets/pixel ou octets/bloc 4x4, bloc compressé ?)
VTF_FORMAT_SIZES = {
    0:  ('RGBA8888', 4, False),
    1:  ('ABGR8888', 4, False),
    2:  ('RGB888', 3, False),
    3:  ('BGR888', 3, False),
    4:  ('RGB565', 2, False),
    5:  ('I8', 1, False),
    6:  ('IA88', 2, False),
    7:  ('P8', 1, False),
    8:  ('A8', 1, False),
    9:  ('RGB888_BLUESCREEN', 3, False),
    10: ('BGR888_BLUESCREEN', 3, False),
    11: ('ARGB8888', 4, False),
    12: ('BGRA8888', 4, False),
    13: ('DXT1', 8, True),
    14: ('DXT3', 16, True),
    15: ('DXT5', 16, True),
    16: ('BGRX8888', 4, False),
    17: ('BGR565', 2, False),
    18: ('BGRX5551', 2, False),
    19: ('BGRA4444', 2, False),
    20: ('DXT1_ONEBITALPHA', 8, True),
    21: ('BGRA5551', 2, False),
    22: ('UV88', 2, False),
    23: ('UVWQ8888', 4, False),
    24: ('RGBA16161616F', 8, False),
    25: ('RGBA16161616', 8, False),
    26: ('UVLX8888', 4, False),
    27: ('R32F', 4, False),
    28: ('RGB323232F', 12, False),
    29: ('RGBA32323232F', 16, False),
}


def _vtf_format_size(fmt: int, w: int, h: int) -> int | None:
    info = VTF_FORMAT_SIZES.get(fmt)
    if info is None:
        return None
    _, unit, is_block = info
    if is_block:
        bw = max(1, (w + 3) // 4)
        bh = max(1, (h + 3) // 4)
        return bw * bh * unit
    return w * h * unit



# ─── Lecteur/Écrivain GMA ────────────────────────────────────────────────────

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
                size = struct.unpack('<q', f.read(8))[0]
                crc  = struct.unpack('<I', f.read(4))[0]
                file_index.append((name, size, crc))

            # Lecture des données binaires
            for name, size, _ in file_index:
                self.files[name] = f.read(size)

    def save(self, filepath: str) -> None:
        with open(filepath, 'wb') as f:
            f.write(self.MAGIC)
            f.write(struct.pack('B', 3))                    # version GMA 3
            f.write(struct.pack('<Q', 0))                   # steamid
            f.write(struct.pack('<Q', int(time.time())))    # timestamp
            f.write(b'\x00')                                # required content vide

            self._write_str(f, self.name)
            desc_json = json.dumps({
                "description": self.description,
                "type": "playermodel",
                "tags": [],
            })
            self._write_str(f, desc_json)
            self._write_str(f, self.author)
            f.write(struct.pack('<i', 1))  # addon version

            file_list = list(self.files.items())
            for i, (name, data) in enumerate(file_list, 1):
                f.write(struct.pack('<I', i))
                self._write_str(f, name)
                f.write(struct.pack('<q', len(data)))
                f.write(struct.pack('<I', binascii.crc32(data) & 0xFFFFFFFF))
            f.write(struct.pack('<I', 0))  # fin de l'index

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


# ─── Compresseur ─────────────────────────────────────────────────────────────

class Compressor:
    """Logique de compression principale"""

    def __init__(self, opts: dict, log_fn, progress_fn, status_fn, current_file_fn=None):
        self.opts        = opts
        self.log         = log_fn
        self.set_progress = progress_fn
        self.set_status  = status_fn
        self.set_current_file = current_file_fn or (lambda *_: None)
        self.cancel_flag = threading.Event()
        self.final_size: int | None = None
        self.reduction: float | None = None

    def cancel(self):
        self.cancel_flag.set()

    def run(self):
        if self.opts.get('batch'):
            self._run_batch()
            return

        try:
            src = Path(self.opts['source'])
            T = self.TOTAL_STEPS

            self.set_status(self.t('loading_files'))
            files = self._load_files(src)

            if not files:
                self.log("✗ ERREUR : Aucun fichier trouvé dans la source.")
                return

            self.log(f"▶ {len(files)} fichier(s) chargé(s)")
            original_size = sum(len(v) for v in files.values())
            self.log(f"  Taille originale : {self._fmt_size(original_size)}")
            self.log("")

            if self.opts.get('dry_run'):
                self.log(self.t('dry_run_active'))
                self.log("")

            # ── Étape 1 : C-Hands ──────────────────────────────────────────
            self.log("▶ Étape 1/6 — C-Hands")
            if self.opts.get('remove_chands') and not self.cancel_flag.is_set():
                self.set_status(self.t('status_chands'))
                removed = self._remove_chands(files)
                self.log(f"  ✓ {removed} fichier(s) supprimé(s)")
            else:
                self.log("  (désactivé)")
            self.set_progress(20)

            # ── Étape 2 : Fichiers inutiles ────────────────────────────────
            self.log("▶ Étape 2/6 — Fichiers inutiles")
            if self.opts.get('remove_unused') and not self.cancel_flag.is_set():
                self.set_status(self.t('status_unused'))
                removed = self._remove_unused(files)
                self.log(f"  ✓ {removed} fichier(s) supprimé(s)")
            else:
                self.log("  (désactivé)")
            self.set_progress(35)

            # ── Étape 3 : Textures ─────────────────────────────────────────
            self.log("▶ Étape 3/6 — Textures")
            if self.opts.get('compress_textures') and not self.cancel_flag.is_set():
                self.set_status("Optimisation des textures…")
                self._optimize_textures(files)
            else:
                self.log("  (désactivé)")
            self.set_progress(65)

            # ── Étape 4 : Sons ─────────────────────────────────────────────
            self.log("▶ Étape 4/6 — Sons")
            if self.opts.get('compress_sounds') and not self.cancel_flag.is_set():
                if FFMPEG_AVAILABLE:
                    self.set_status("Compression des sons…")
                    self._compress_sounds(files)
                else:
                    self.log("  ⚠ ffmpeg introuvable dans le PATH, étape ignorée")
            else:
                self.log("  (désactivé)")
            self.set_progress(80)

            # ── Étape 5 : Lua PM ───────────────────────────────────────────
            self.log("▶ Étape 5/6 — Fichier Lua PM")
            if self.opts.get('gen_lua') and not self.cancel_flag.is_set():
                self.set_status(self.t('status_lua'))
                self._generate_lua(files, Path(self.opts['source']).stem)
            else:
                self.log("  (désactivé)")
            self.set_progress(90)

            # ── Étape 6 : Écriture ─────────────────────────────────────────
            self.log("▶ Étape 6/6 — Écriture de la sortie")
            if not self.cancel_flag.is_set():
                self.set_status(self.t('status_write'))
                self._write_output(files, src)
            self.set_progress(100)
            self.set_current_file("")

            if not self.cancel_flag.is_set():
                final_size = sum(len(v) for v in files.values())
                reduction  = (1 - final_size / original_size) * 100 if original_size > 0 else 0
                self.final_size = final_size
                self.reduction  = reduction
                self.log("")
                self.log(f"✓ Taille finale  : {self._fmt_size(final_size)}")
                self.log(f"✓ Réduction      : {reduction:.1f}%")
                self.log("✓ Compression terminée avec succès !")
                self.set_status("Terminé !")
            else:
                self.log("\n⚠ Compression annulée.")
                self.set_status("Annulé")

        except Exception as e:
            import traceback
            self.log(f"\n✗ ERREUR : {e}")
            self.log(traceback.format_exc())
            self.set_status(self.t('status_error'))

    # ── Chargement ───────────────────────────────────────────────────────────

    def _load_files(self, src: Path) -> dict:
        files = {}
        if self.opts.get('source_type') == 'gma':
            gma = GMAFile()
            gma.load(str(src))
            files['__meta__'] = json.dumps({
                'name': gma.name,
                'description': gma.description,
                'author': gma.author,
            }).encode()
            for name, data in gma.files.items():
                files[name.replace('\\', '/').lower()] = data
        else:
            for fp in src.rglob('*'):
                if fp.is_file():
                    key = str(fp.relative_to(src)).replace('\\', '/').lower()
                    files[key] = fp.read_bytes()
        return files

    # ── Filtres ───────────────────────────────────────────────────────────────

    def _remove_chands(self, files: dict) -> int:
        to_remove = []
        for path in list(files.keys()):
            if path == '__meta__':
                continue
            for pattern in CHAND_PATTERNS:
                if re.match(pattern, path, re.IGNORECASE):
                    to_remove.append(path)
                    self.log(self.t('removed_chand', path=path))
                    break
        for p in to_remove:
            del files[p]
        return len(to_remove)

    def _remove_unused(self, files: dict) -> int:
        to_remove = []
        for path in list(files.keys()):
            if path == '__meta__':
                continue
            if Path(path).suffix.lower() in USELESS_EXTENSIONS:
                to_remove.append(path)
                self.log(self.t('removed_unused_file', path=path))
        for p in to_remove:
            del files[p]
        return len(to_remove)

    # ── Vérification des matériaux ───────────────────────────────────────────

    @staticmethod
    def _resolve_vtf_path(ref: str) -> str:
        ref = ref.strip().strip('"\'').replace('\\', '/').lower().lstrip('/')
        if not ref:
            return ''
        if not ref.endswith('.vtf'):
            ref += '.vtf'
        if not ref.startswith('materials/'):
            ref = 'materials/' + ref
        return ref

    def _check_missing_textures(self, files: dict) -> None:
        vmt_files = {k: v for k, v in files.items() if k.endswith('.vmt')}
        if not vmt_files:
            self.log(self.t('no_vmt'))
            return

        existing = set(files.keys())
        pattern = re.compile(r'\$(\w+)"?\s+"([^"]*)"', re.IGNORECASE)
        missing_total = 0
        checked = 0

        for vmt_path, data in vmt_files.items():
            if self.cancel_flag.is_set():
                break
            try:
                text = data.decode('utf-8', errors='replace')
            except Exception:
                continue
            checked += 1
            seen_refs = set()
            for m in pattern.finditer(text):
                key = m.group(1).lower()
                if key not in VMT_TEXTURE_KEYS:
                    continue
                ref = m.group(2).strip()
                if not ref or ref.lower() == 'env_cubemap':
                    continue
                tex_path = self._resolve_vtf_path(ref)
                if not tex_path or tex_path in seen_refs:
                    continue
                seen_refs.add(tex_path)
                if tex_path not in existing:
                    self.log(self.t('missing_texture', texture=tex_path, vmt=vmt_path))
                    missing_total += 1

        if missing_total == 0:
            self.log(self.t('missing_textures_none', n=checked))
        else:
            self.log(self.t('missing_textures_found', n=missing_total))

    # ── Textures ──────────────────────────────────────────────────────────────

    def _optimize_textures(self, files: dict, max_res, quality: int, quiet: bool = False) -> None:
        tex_files = {k: v for k, v in files.items()
                     if Path(k).suffix.lower() in TEXTURE_EXTENSIONS and k != '__meta__'}

        if not tex_files:
            if not quiet:
                self.log(self.t('no_textures'))
            return

        self.log(f"  {len(tex_files)} texture(s) trouvée(s)…")
        if max_res is None:
            self.log("  Résolution max : aucune limite (les .vtf seront copiés tels quels)")
        elif not VTFLIB_AVAILABLE:
            self.log(f"  vtflib non installé : réduction des .vtf par troncature de "
                     f"mipmaps (résolution max {max_res}px)")

        total = len(tex_files)
        reduced = 0
        unchanged_vtf = 0

        for i, (path, data) in enumerate(tex_files.items()):
            if self.cancel_flag.is_set():
                break

            self.set_current_file(path)
            ext = Path(path).suffix.lower()
            new_data = None

            if ext == '.vtf':
                new_data = self._process_vtf(path, data, max_res, quality)
            elif PIL_AVAILABLE and ext in {'.png', '.jpg', '.jpeg', '.tga', '.bmp'}:
                new_data = self._process_image_pil(path, data, ext, max_res, quality)

            if new_data and len(new_data) < len(data):
                savings = len(data) - len(new_data)
                if not quiet:
                    self.log(self.t('texture_saving', path=path, size=self._fmt_size(savings)))
                files[path] = new_data
                reduced += 1
            elif ext == '.vtf':
                unchanged_vtf += 1

            if not quiet:
                self.set_progress(30 + (i / total) * 30)

        if not quiet:
            self.log(self.t('textures_reduced', reduced=reduced, total=total))
            if unchanged_vtf:
                self.log(self.t('vtf_unchanged', n=unchanged_vtf))

    # ── Mode taille cible ────────────────────────────────────────────────────

    def _target_size_steps(self) -> list[tuple[int | None, int]]:
        max_res_str = self.opts.get('max_resolution', '1024')
        quality     = int(self.opts.get('texture_quality', 85))
        base_res    = int(max_res_str) if str(max_res_str).isdigit() else None

        all_res = [2048, 1024, 512, 256, 128]
        res_list = [r for r in all_res if base_res is None or r <= base_res]
        if base_res is not None and base_res not in res_list:
            res_list.insert(0, base_res)
        if not res_list:
            res_list = [128]

        qual_list = sorted({q for q in (quality, 75, 60, 45, 30) if 10 <= q <= 100}, reverse=True)

        steps: list[tuple[int | None, int]] = []
        for res in res_list:
            for q in qual_list:
                if (res, q) not in steps:
                    steps.append((res, q))
        return steps

    def _run_target_size_mode(self, files: dict, original_files: dict) -> None:
        target_bytes = int(self.opts['target_size_mb'] * 1024 * 1024)
        self.log(self.t('step_target_size', size=self._fmt_size(target_bytes)))

        steps = self._target_size_steps()
        chosen = steps[-1]
        chosen_size = None

        for i, (res, quality) in enumerate(steps, 1):
            if self.cancel_flag.is_set():
                return
            trial = dict(original_files)
            self._optimize_textures(trial, res, quality, quiet=True)
            size = sum(len(v) for v in trial.values())
            res_label = f"{res}px" if res else self.t('no_limit')
            self.log(self.t('target_attempt', n=i, res=res_label, q=quality, size=self._fmt_size(size)))
            chosen, chosen_size = (res, quality), size
            if size <= target_bytes:
                break

        files.clear()
        files.update(original_files)
        self._optimize_textures(files, chosen[0], chosen[1])

        if chosen_size is not None and chosen_size <= target_bytes:
            self.log(self.t('target_reached', size=self._fmt_size(chosen_size), target=self._fmt_size(target_bytes)))
        else:
            self.log(self.t('target_not_reached', size=self._fmt_size(chosen_size or 0), target=self._fmt_size(target_bytes)))

        self.log(f"  Textures réduites : {reduced}/{total}")
        if unchanged_vtf:
            self.log(f"  .vtf inchangés : {unchanged_vtf} "
                     f"(déjà sous la résolution max, ou format/structure non pris en charge)")

    def _process_vtf(self, path: str, data: bytes, max_res, quality: int) -> bytes:
        if VTFLIB_AVAILABLE:
            try:
                return self._process_vtf_vtflib(data, max_res, quality)
            except Exception:
                pass
        # Sans VTFLib : réduction de résolution par troncature des mipmaps
        return self._process_vtf_mipstrip(data, max_res)

    def _process_vtf_vtflib(self, data: bytes, max_res, quality: int) -> bytes:
        lib = vtflib.VTFLib()
        lib.image_load_lump(data)
        w, h = lib.width(), lib.height()
        if max_res and (w > max_res or h > max_res):
            new_w = min(w, max_res)
            new_h = min(h, max_res)
            lib.image_resize(new_w, new_h)
        return bytes(lib.image_save_lump())

    def _process_vtf_mipstrip(self, data: bytes, max_res) -> bytes:
        """Réduit la résolution d'un VTF en supprimant les mipmaps les plus
        grands, sans dépendance externe. Ne touche pas aux fichiers dont la
        structure n'est pas reconnue (cubemaps, multi-frames, etc.)."""
        if max_res is None:
            return data
        try:
            if data[:4] != b'VTF\x00' or len(data) < 80:
                return data

            ver_maj, ver_min, header_size = struct.unpack_from('<III', data, 4)
            if ver_maj != 7:
                return data

            width, height = struct.unpack_from('<HH', data, 16)
            flags = struct.unpack_from('<I', data, 20)[0]
            frames = struct.unpack_from('<H', data, 24)[0]
            high_fmt = struct.unpack_from('<i', data, 52)[0]
            mipmap_count = data[56]
            low_fmt = struct.unpack_from('<i', data, 57)[0]
            low_w, low_h = data[61], data[62]

            TEXTUREFLAGS_ENVMAP = 0x4000
            if frames != 1 or (flags & TEXTUREFLAGS_ENVMAP):
                return data  # cubemaps / multi-frames : trop risqué
            if width == 0 or height == 0 or mipmap_count <= 1:
                return data
            if max(width, height) <= max_res:
                return data  # déjà sous la limite
            if high_fmt not in VTF_FORMAT_SIZES:
                return data

            depth = 1
            if (ver_maj, ver_min) >= (7, 2) and len(data) >= 65:
                depth = struct.unpack_from('<H', data, 63)[0] or 1
            if depth != 1:
                return data

            # Localiser le début des données haute résolution
            if (ver_maj, ver_min) >= (7, 3):
                if len(data) < 72:
                    return data
                num_res = struct.unpack_from('<I', data, 68)[0]
                high_res_offset = None
                for i in range(num_res):
                    off = 72 + i * 8
                    if off + 8 > len(data):
                        return data
                    tag = data[off:off + 3]
                    if tag == b'\x30\x00\x00':
                        high_res_offset = struct.unpack_from('<I', data, off + 4)[0]
                if high_res_offset is None:
                    return data
            else:
                low_size = 0
                if low_fmt != -1 and low_w and low_h:
                    low_size = _vtf_format_size(low_fmt, low_w, low_h) or 0
                high_res_offset = header_size + low_size

            if high_res_offset >= len(data):
                return data

            # Taille de chaque mip, du plus petit au plus grand (ordre de stockage)
            mip_sizes = []
            for m in range(mipmap_count - 1, -1, -1):
                mw = max(1, width >> m)
                mh = max(1, height >> m)
                sz = _vtf_format_size(high_fmt, mw, mh)
                if sz is None:
                    return data
                mip_sizes.append((m, mw, mh, sz))

            total_high_res = len(data) - high_res_offset
            if sum(s for _, _, _, s in mip_sizes) != total_high_res:
                return data  # structure inattendue : on ne touche pas au fichier

            # Trouver le plus grand mip qui respecte max_res
            keep = 0
            target = None
            for m, mw, mh, sz in mip_sizes:
                if max(mw, mh) > max_res:
                    break
                keep += sz
                target = (m, mw, mh, keep)

            if target is None or target[0] == 0:
                return data  # pas de réduction utile

            new_mip_level, new_w, new_h, new_high_res_size = target
            new_mipmap_count = mipmap_count - new_mip_level

            out = bytearray(data[:high_res_offset + new_high_res_size])
            struct.pack_into('<HH', out, 16, new_w, new_h)
            out[56] = new_mipmap_count
            return bytes(out)

        except (struct.error, IndexError):
            return data

    def _process_image_pil(self, path: str, data: bytes, ext: str,
                            max_res, quality: int) -> bytes:
        try:
            import io
            img = Image.open(io.BytesIO(data))
            if max_res and (img.width > max_res or img.height > max_res):
                img.thumbnail((max_res, max_res), Image.LANCZOS)
            buf = io.BytesIO()
            if ext in ('.jpg', '.jpeg'):
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')
                img.save(buf, format='JPEG', quality=quality, optimize=True)
            elif ext == '.png':
                compress_level = max(0, min(9, int((100 - quality) / 11)))
                img.save(buf, format='PNG', compress_level=compress_level, optimize=True)
            else:
                img.save(buf, format='PNG', optimize=True)
            return buf.getvalue()
        except Exception:
            return data

    # ── Sons ─────────────────────────────────────────────────────────────────

    def _compress_sounds(self, files: dict) -> None:
        bitrate = self.opts.get('sound_quality', '128k')
        snd_files = {k: v for k, v in files.items()
                     if Path(k).suffix.lower() in SOUND_EXTENSIONS and k != '__meta__'}

        if not snd_files:
            self.log(self.t('no_sounds'))
            return

        self.log(self.t('sounds_found', n=len(snd_files)))

        for path, data in snd_files.items():
            if self.cancel_flag.is_set():
                break
            self.set_current_file(path)
            ext = Path(path).suffix.lower()
            # Toujours convertir en .mp3 avec le bitrate choisi
            out_ext = '.mp3'
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tf:
                tf.write(data)
                tmp_in = tf.name
            tmp_out = tmp_in + out_ext
            try:
                result = subprocess.run(
                    ['ffmpeg', '-y', '-i', tmp_in, '-b:a', bitrate,
                     '-map_metadata', '-1', tmp_out],
                    capture_output=True, timeout=60,
                )
                if result.returncode == 0:
                    new_data = Path(tmp_out).read_bytes()
                    if len(new_data) < len(data):
                        new_key = path.rsplit('.', 1)[0] + out_ext
                        del files[path]
                        files[new_key] = new_data
                        savings = len(data) - len(new_data)
                        self.log(self.t('sound_saving', path=path, new_path=new_key, size=self._fmt_size(savings)))
            except Exception as e:
                self.log(self.t('sound_error', path=path, e=e))
            finally:
                for tmp in (tmp_in, tmp_out):
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass

    # ── Génération Lua ────────────────────────────────────────────────────────

    def _generate_lua(self, files: dict, addon_stem: str) -> None:
        """Génère ou met à jour le fichier Lua d'enregistrement du playermodel."""

        # 1. Trouver les .mdl candidats (hors armes et LOD), de préférence
        #    dans models/player/ ; sinon n'importe où ailleurs dans models/
        def is_mdl(p):
            return (p.startswith('models/') and p.endswith('.mdl')
                    and not p.startswith('models/weapons/')
                    and not re.search(r'_lod\d+\.mdl$', p))

        all_mdls = sorted(p for p in files if is_mdl(p))
        pm_models = [p for p in all_mdls if p.startswith('models/player/')]

        if not pm_models and all_mdls:
            self.log("  Lua : aucun .mdl dans models/player/, "
                     "utilisation des modèles trouvés ailleurs dans models/")
            pm_models = all_mdls

        if not pm_models:
            self.log("  Lua : aucun .mdl trouvé dans models/ – ignoré")
            return

        for p in pm_models:
            self.log(f"  Lua : modèle détecté → {p}")

        self.log(f"  Lua : {len(pm_models)} modèle(s) trouvé(s)")

        # 2. Trouver les c_hands encore présents dans les fichiers
        chand_mdls = [
            p for p in files
            if re.match(r'models/weapons/c_.*\.mdl', p, re.IGNORECASE)
        ]
        include_chands = self.opts.get('lua_chands', True) and bool(chand_mdls)

        # 3. Vérifier s'il existe déjà un fichier Lua avec AddValidModel
        existing_path: str | None = None
        for path, data in files.items():
            if not path.endswith('.lua'):
                continue
            try:
                if b'AddValidModel' in data or b'player_manager' in data:
                    existing_path = path
                    break
            except Exception:
                pass

        # 4. Construire le contenu Lua
        safe_stem = re.sub(r'[^a-z0-9]', '_', addon_stem.lower()).strip('_') or 'pm'
        lines: list[str] = [
            '-- Généré automatiquement par Compressez PM GMod',
            f'-- Addon : {addon_stem}',
            '',
        ]

        for mdl in pm_models:
            display = Path(mdl).stem.replace('_', ' ').replace('-', ' ').title()
            var      = re.sub(r'[^A-Z0-9]', '_', Path(mdl).stem.upper()).strip('_')
            lines += [
                f'local MDL_{var} = "{mdl}"',
                f'player_manager.AddValidModel("{display}", MDL_{var})',
            ]

            if include_chands:
                # Chercher le c_hands le plus proche par nom
                stem = Path(mdl).stem.lower()
                match = next(
                    (c for c in chand_mdls
                     if stem in c or c.replace('models/weapons/c_arms_', '').split('.')[0] in stem),
                    chand_mdls[0] if chand_mdls else None,
                )
                if match:
                    lines += [
                        '',
                        'if CLIENT then',
                        f'    hook.Add("PlayerSetHandsModel", "chands_{var}", function(ply, ent)',
                        f'        if ply:GetModel() == MDL_{var} then',
                        f'            ent:SetModel("{match}")',
                        f'            ent:SetSkin(ply:GetSkin())',
                        f'            ent:SetBodyGroups(ply:GetBodygroupsString())',
                        f'        end',
                        f'    end)',
                        'end',
                    ]

            lines.append('')

        lua_bytes = '\n'.join(lines).encode('utf-8')

        if existing_path:
            files[existing_path] = lua_bytes
            self.log(self.t('lua_updated', path=existing_path))
        else:
            new_path = f'lua/autorun/sh_{safe_stem}_pm.lua'
            files[new_path] = lua_bytes
            self.log(self.t('lua_created', path=new_path))

    # ── Écriture ─────────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_output_path(output: Path, fmt: str) -> Path:
        if fmt == 'gma':
            return output if output.suffix == '.gma' else output.with_suffix('.gma')
        if fmt == 'zip':
            return output if output.suffix == '.zip' else output.with_suffix('.zip')
        return output

    def _backup_existing(self, output: Path, fmt: str) -> None:
        target = self._resolve_output_path(output, fmt)
        if not target.exists():
            return

        timestamp = time.strftime('%Y%m%d_%H%M%S')
        try:
            if target.is_dir():
                backup_path = target.parent / f"{target.name}_backup_{timestamp}"
                shutil.copytree(target, backup_path)
            else:
                backup_path = target.with_name(f"{target.stem}_backup_{timestamp}{target.suffix}")
                shutil.copy2(target, backup_path)
            self.log(self.t('backup_created', path=backup_path))
        except Exception as e:
            self.log(self.t('backup_failed', e=e))

    def _write_output(self, files: dict, src: Path) -> None:
        output  = Path(self.opts['output'])
        fmt     = self.opts.get('output_format', 'folder')
        zip_lvl = self.opts.get('zip_level', 6)

        meta = None
        if '__meta__' in files:
            try:
                meta = json.loads(files['__meta__'].decode())
            except Exception:
                pass
        out_files = {k: v for k, v in files.items() if k != '__meta__'}

        if self.opts.get('dry_run'):
            if fmt == 'folder':
                self.log(self.t('dry_run_would_write_folder', path=output, n=len(out_files)))
            elif fmt == 'gma':
                self.log(self.t('dry_run_would_write_gma', path=self._resolve_output_path(output, fmt)))
            elif fmt == 'zip':
                self.log(self.t('dry_run_would_write_zip', path=self._resolve_output_path(output, fmt)))
            return

        if self.opts.get('backup_original'):
            self._backup_existing(output, fmt)

        if fmt == 'folder':
            output.mkdir(parents=True, exist_ok=True)
            for path, data in out_files.items():
                dest = output / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
            self.log(self.t('write_folder', path=output))

        elif fmt == 'gma':
            gma = GMAFile()
            if meta:
                gma.name        = meta.get('name', src.stem)
                gma.description = meta.get('description', '')
                gma.author      = meta.get('author', '')
            else:
                gma.name = src.stem
                if 'addon.json' in out_files:
                    try:
                        info = json.loads(out_files['addon.json'].decode())
                        gma.name        = info.get('title', src.stem)
                        gma.description = info.get('description', '')
                    except Exception:
                        pass
            # Le format GMA utilise des forward slashes même sur Windows
            gma.files = out_files
            out_path = self._resolve_output_path(output, fmt)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            gma.save(str(out_path))
            self.log(self.t('write_gma', path=out_path))

        elif fmt == 'zip':
            out_path = self._resolve_output_path(output, fmt)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(str(out_path), 'w',
                                 zipfile.ZIP_DEFLATED,
                                 compresslevel=zip_lvl) as zf:
                for path, data in out_files.items():
                    zf.writestr(path, data)
            self.log(self.t('write_zip', path=out_path))

    # ── Mode batch ───────────────────────────────────────────────────────────

    def _run_batch(self) -> None:
        src = Path(self.opts['source'])

        addons: list[tuple[str, Path]] = []
        if src.is_dir():
            for item in sorted(src.iterdir()):
                if item.is_dir():
                    addons.append(('folder', item))
                elif item.suffix.lower() == '.gma':
                    addons.append(('gma', item))

        if not addons:
            self.log(self.t('batch_none'))
            return

        self.log(self.t('batch_found', n=len(addons), path=src))
        self.log("")

        output_root = Path(self.opts['output'])
        fmt = self.opts.get('output_format', 'folder')
        n = len(addons)
        results: list[tuple[str, int, float]] = []

        for i, (stype, path) in enumerate(addons, 1):
            if self.cancel_flag.is_set():
                break

            name = path.stem
            self.log(self.t('batch_processing', i=i, n=n, name=name))

            sub_opts = dict(self.opts)
            sub_opts['source'] = str(path)
            sub_opts['source_type'] = stype
            sub_opts['batch'] = False
            if fmt == 'folder':
                sub_opts['output'] = str(output_root / name)
            else:
                ext = '.gma' if fmt == 'gma' else '.zip'
                sub_opts['output'] = str(output_root / (name + ext))

            def progress_wrap(v, i=i):
                self.set_progress((i - 1 + v / 100) / n * 100)

            sub = Compressor(
                sub_opts,
                log_fn=self.log,
                progress_fn=progress_wrap,
                status_fn=self.set_status,
                current_file_fn=self.set_current_file,
            )
            sub.run()
            if sub.final_size is not None:
                results.append((name, sub.final_size, sub.reduction or 0.0))
            self.log("")

        self.set_progress(100)
        self.set_current_file("")

        if results:
            self.log(self.t('batch_summary_header'))
            for name, size, reduction in results:
                self.log(self.t('batch_summary_line', name=name,
                                 size=self._fmt_size(size), pct=f"{reduction:.1f}"))
            self.log("")

        self.log(self.t('batch_done', n=len(results)))
        self.set_status(self.t('status_done'))

    # ── Utilitaires ──────────────────────────────────────────────────────────

    @staticmethod
    def _fmt_size(n: int) -> str:
        for unit in ['o', 'Ko', 'Mo', 'Go']:
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} To"


# ─── Interface graphique ──────────────────────────────────────────────────────

# Palettes de thème : Catppuccin Mocha (sombre) / Catppuccin Latte (clair)
THEMES = {
    'dark': {
        'BG': '#1e1e2e', 'FG': '#cdd6f4', 'ACCENT': '#89b4fa', 'SUB': '#6c7086',
        'SURFACE': '#313244', 'GREEN': '#a6e3a1', 'RED': '#f38ba8', 'YELLOW': '#f9e2af',
        'LOG_BG': '#11111b', 'ACCENT_ACTIVE': '#74c7ec', 'BTN_ACTIVE': '#45475a',
    },
    'light': {
        'BG': '#eff1f5', 'FG': '#4c4f69', 'ACCENT': '#1e66f5', 'SUB': '#8c8fa1',
        'SURFACE': '#ccd0da', 'GREEN': '#40a02b', 'RED': '#d20f39', 'YELLOW': '#df8e1d',
        'LOG_BG': '#e6e9ef', 'ACCENT_ACTIVE': '#7287fd', 'BTN_ACTIVE': '#bcc0cc',
    },
}


class App:

    # Profils rapides : ajustent automatiquement les options ci-dessous
    PRESETS: dict[str, dict | None] = {
        'custom': None,
        'balanced': {
            'remove_chands': True, 'remove_unused': True, 'compress_textures': True,
            'max_res': '1024', 'quality': 85, 'compress_sounds': False,
            'sound_quality': '128k', 'zip_level': 6,
        },
        'quality': {
            'remove_chands': True, 'remove_unused': True, 'compress_textures': True,
            'max_res': 'none', 'quality': 100, 'compress_sounds': False,
            'sound_quality': '320k', 'zip_level': 4,
        },
        'minimal': {
            'remove_chands': True, 'remove_unused': True, 'compress_textures': True,
            'max_res': '512', 'quality': 60, 'compress_sounds': True,
            'sound_quality': '96k', 'zip_level': 9,
        },
        'share': {
            'remove_chands': True, 'remove_unused': True, 'compress_textures': True,
            'max_res': '256', 'quality': 50, 'compress_sounds': True,
            'sound_quality': '64k', 'zip_level': 9,
        },
    }

    # Profils rapides : ajustent automatiquement les options ci-dessous
    PRESETS: dict[str, dict | None] = {
        "Personnalisé": None,
        "Équilibré (recommandé)": {
            'remove_chands': True, 'remove_unused': True, 'compress_textures': True,
            'max_res': '1024', 'quality': 85, 'compress_sounds': False,
            'sound_quality': '128k', 'zip_level': 6,
        },
        "Qualité maximale": {
            'remove_chands': True, 'remove_unused': True, 'compress_textures': True,
            'max_res': 'Aucune limite', 'quality': 100, 'compress_sounds': False,
            'sound_quality': '320k', 'zip_level': 4,
        },
        "Taille minimale": {
            'remove_chands': True, 'remove_unused': True, 'compress_textures': True,
            'max_res': '512', 'quality': 60, 'compress_sounds': True,
            'sound_quality': '96k', 'zip_level': 9,
        },
        "Partage rapide (Discord…)": {
            'remove_chands': True, 'remove_unused': True, 'compress_textures': True,
            'max_res': '256', 'quality': 50, 'compress_sounds': True,
            'sound_quality': '64k', 'zip_level': 9,
        },
    }

    def __init__(self):
        self.lang = 'fr'
        self.theme_name = 'dark'
        self._apply_palette()

        self.root = TkinterDnD.Tk() if DND_AVAILABLE else tk.Tk()
        self.root.title(f"Compressez PM GMod  v{VERSION}")
        self.root.geometry("820x780")
        self.root.configure(bg=self.BG)
        self.root.resizable(True, True)
        self.root.minsize(700, 640)

        self._compressor: Compressor | None = None
        self._thread: threading.Thread | None = None

        self._setup_styles()
        self._build_ui()
        self._log_header()

    # ── Internationalisation / thème ──────────────────────────────────────────

    def t(self, key: str, **kwargs) -> str:
        return t(key, self.lang, **kwargs)

    def _apply_palette(self):
        palette = THEMES[self.theme_name]
        for k, v in palette.items():
            setattr(self, k, v)

    def _profile_label(self, pid: str) -> str:
        return self.t(f'profile_{pid}')

    # ── Styles ───────────────────────────────────────────────────────────────

    def _setup_styles(self):
        s = ttk.Style()
        s.theme_use('clam')

        s.configure('.', background=self.BG, foreground=self.FG,
                    bordercolor=self.SURFACE, relief='flat')
        s.configure('TFrame',          background=self.BG)
        s.configure('TLabel',          background=self.BG, foreground=self.FG)
        s.configure('TLabelframe',     background=self.BG, bordercolor=self.SURFACE)
        s.configure('TLabelframe.Label', background=self.BG, foreground=self.ACCENT,
                    font=('Segoe UI', 9, 'bold'))
        s.configure('TCheckbutton',    background=self.BG, foreground=self.FG)
        s.configure('TRadiobutton',    background=self.BG, foreground=self.FG)
        s.configure('TEntry',          fieldbackground=self.SURFACE, foreground=self.FG,
                    bordercolor=self.SURFACE, insertcolor=self.FG)
        s.configure('TButton',         background=self.SURFACE, foreground=self.FG,
                    bordercolor=self.SURFACE, padding=(8, 4))
        s.configure('TCombobox',       fieldbackground=self.SURFACE, foreground=self.FG,
                    selectbackground=self.ACCENT, selectforeground=self.BG)
        s.configure('TScale',          background=self.BG, troughcolor=self.SURFACE)
        s.configure('TProgressbar',    background=self.ACCENT, troughcolor=self.SURFACE,
                    bordercolor=self.SURFACE)
        s.configure('Accent.TButton',  background=self.ACCENT, foreground=self.BG,
                    font=('Segoe UI', 9, 'bold'), padding=(14, 5))
        s.configure('TNotebook',       background=self.BG, bordercolor=self.SURFACE)
        s.configure('TNotebook.Tab',   background=self.SURFACE, foreground=self.FG,
                    padding=(12, 5), font=('Segoe UI', 9))

        s.map('Accent.TButton',  background=[('active', self.ACCENT_ACTIVE)])
        s.map('TButton',         background=[('active', self.BTN_ACTIVE)])
        s.map('TCheckbutton',    background=[('active', self.BG)])
        s.map('TRadiobutton',    background=[('active', self.BG)])
        s.map('TCombobox',       fieldbackground=[('readonly', self.SURFACE)])
        s.map('TNotebook.Tab',   background=[('selected', self.ACCENT)],
                                  foreground=[('selected', self.BG)])

    # ── Construction UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        # En-tête
        hdr = tk.Frame(self.root, bg=self.SURFACE, pady=8)
        hdr.pack(fill='x')
        tk.Label(hdr, text="Compressez PM GMod",
                 bg=self.SURFACE, fg=self.ACCENT,
                 font=('Segoe UI', 14, 'bold')).pack(side='left', padx=14)
        tk.Label(hdr, text=f"v{VERSION}",
                 bg=self.SURFACE, fg=self.SUB,
                 font=('Segoe UI', 9)).pack(side='left')

        theme_key = 'btn_theme_light' if self.theme_name == 'dark' else 'btn_theme_dark'
        ttk.Button(hdr, text=self.t(theme_key), command=self._toggle_theme,
                   width=14).pack(side='right', padx=(0, 14))
        lang_text = "English" if self.lang == 'fr' else "Français"
        ttk.Button(hdr, text=lang_text, command=self._toggle_language,
                   width=10).pack(side='right', padx=(0, 6))

        # Corps principal avec scroll
        main = ttk.Frame(self.root, padding=(10, 8, 10, 10))
        main.pack(fill='both', expand=True)

        self._build_io_section(main)
        self._build_options_section(main)
        self._build_progress_section(main)
        self._build_log_section(main)
        self._build_buttons(main)

    def _build_io_section(self, parent):
        frm = ttk.LabelFrame(parent, text=self.t('io_section'), padding=8)
        frm.pack(fill='x', pady=(0, 6))

        # Source
        r = ttk.Frame(frm)
        r.pack(fill='x', pady=2)
        ttk.Label(r, text=self.t('label_source'), width=9).pack(side='left')
        self.source_var = tk.StringVar()
        src_entry = ttk.Entry(r, textvariable=self.source_var)
        src_entry.pack(side='left', fill='x', expand=True, padx=(0, 4))
        ttk.Button(r, text=self.t('btn_browse'), command=self._browse_source, width=10).pack(side='right')

        if DND_AVAILABLE:
            src_entry.drop_target_register(DND_FILES)
            src_entry.dnd_bind('<<Drop>>', self._on_drop_source)

        # Output
        r2 = ttk.Frame(frm)
        r2.pack(fill='x', pady=2)
        ttk.Label(r2, text=self.t('label_output'), width=9).pack(side='left')
        self.output_var = tk.StringVar()
        ttk.Entry(r2, textvariable=self.output_var).pack(side='left', fill='x', expand=True, padx=(0, 4))
        ttk.Button(r2, text=self.t('btn_browse'), command=self._browse_output, width=10).pack(side='right')

        # Types
        types_row = ttk.Frame(frm)
        types_row.pack(fill='x', pady=(5, 0))

        ttk.Label(types_row, text=self.t('label_source_type')).pack(side='left')
        self.src_type = tk.StringVar(value='folder')
        ttk.Radiobutton(types_row, text=self.t('radio_folder'),   variable=self.src_type, value='folder').pack(side='left', padx=(4, 10))
        ttk.Radiobutton(types_row, text=self.t('radio_gma_file'), variable=self.src_type, value='gma').pack(side='left', padx=(0, 20))

        ttk.Label(types_row, text=self.t('label_output_format')).pack(side='left')
        self.out_fmt = tk.StringVar(value='folder')
        ttk.Radiobutton(types_row, text=self.t('radio_folder'), variable=self.out_fmt, value='folder').pack(side='left', padx=(4, 8))
        ttk.Radiobutton(types_row, text=".gma",                 variable=self.out_fmt, value='gma').pack(side='left', padx=(0, 8))
        ttk.Radiobutton(types_row, text=".zip",                 variable=self.out_fmt, value='zip').pack(side='left')

        # Statistiques de la source (mises à jour après sélection)
        self.stats_var = tk.StringVar(value="")
        ttk.Label(frm, textvariable=self.stats_var,
                  foreground=self.ACCENT, font=('Segoe UI', 8, 'bold')).pack(anchor='w', pady=(4, 0))

    def _build_options_section(self, parent):
        # ── Profil rapide ───────────────────────────────────────────────────
        profile_frm = ttk.Frame(parent)
        profile_frm.pack(fill='x', pady=(0, 6))
        ttk.Label(profile_frm, text="Profil rapide :").pack(side='left')
        self.profile_var = tk.StringVar(value=next(iter(self.PRESETS)))
        profile_combo = ttk.Combobox(profile_frm, textvariable=self.profile_var, width=26,
                                      values=list(self.PRESETS.keys()), state='readonly')
        profile_combo.pack(side='left', padx=4)
        profile_combo.bind('<<ComboboxSelected>>', self._apply_profile)
        ttk.Label(profile_frm, text="  Ajuste automatiquement les réglages ci-dessous",
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(side='left')

        # ── Onglets Général / Avancé ────────────────────────────────────────
        notebook = ttk.Notebook(parent)
        notebook.pack(fill='x', pady=(0, 6))

        general_tab  = ttk.Frame(notebook, padding=8)
        advanced_tab = ttk.Frame(notebook, padding=8)
        notebook.add(general_tab,  text=" Général ")
        notebook.add(advanced_tab, text=" Avancé ")

        # ════════════════════ Onglet Général ════════════════════
        left  = ttk.Frame(general_tab)
        left.pack(side='left', fill='both', expand=True)
        right = ttk.Frame(general_tab)
        right.pack(side='left', fill='both', expand=True, padx=(12, 0))

        # C-Hands
        self.rem_chands = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text=self.t('chk_chands'),
                        variable=self.rem_chands).pack(anchor='w')
        ttk.Label(left, text=self.t('desc_chands'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        # Fichiers inutiles
        self.rem_unused = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text=self.t('chk_unused'),
                        variable=self.rem_unused).pack(anchor='w')
        ttk.Label(left, text=self.t('desc_unused'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        # Vérification des matériaux
        self.check_materials = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text=self.t('chk_check_materials'),
                        variable=self.check_materials).pack(anchor='w', pady=(0, 5))

        # Textures
        self.comp_tex = tk.BooleanVar(value=True)
        ttk.Checkbutton(right, text="Optimiser les textures",
                        variable=self.comp_tex,
                        command=self._toggle_tex).pack(anchor='w')

        self.tex_sub = ttk.Frame(right)
        self.tex_sub.pack(anchor='w', padx=(16, 0), pady=(2, 0))

        r1 = ttk.Frame(self.tex_sub)
        r1.pack(anchor='w', pady=1)
        ttk.Label(r1, text=self.t('label_max_res')).pack(side='left')
        self.max_res = tk.StringVar(value='1024')
        ttk.Combobox(r1, textvariable=self.max_res, width=14,
                     values=['256', '512', '1024', '2048', self.t('no_limit')],
                     state='readonly').pack(side='left', padx=4)

        r2 = ttk.Frame(self.tex_sub)
        r2.pack(anchor='w', pady=1)
        ttk.Label(r2, text=self.t('label_quality')).pack(side='left')
        self.tex_qual = tk.IntVar(value=85)
        ttk.Scale(r2, from_=10, to=100, variable=self.tex_qual,
                  orient='h', length=110).pack(side='left', padx=4)
        self.qual_lbl = ttk.Label(r2, text="85%", width=5)
        self.qual_lbl.pack(side='left')
        self.tex_qual.trace_add('write', lambda *_: self.qual_lbl.config(
            text=f"{self.tex_qual.get()}%"))

        if not PIL_AVAILABLE and not VTFLIB_AVAILABLE:
            ttk.Label(self.tex_sub,
                      text=self.t('pillow_hint'),
                      foreground=self.YELLOW, font=('Segoe UI', 8)).pack(anchor='w', pady=(2, 0))

        # Génération Lua
        ttk.Separator(right, orient='horizontal').pack(fill='x', pady=(10, 4))

        self.gen_lua = tk.BooleanVar(value=True)
        ttk.Checkbutton(right, text="Générer le fichier Lua PM",
                        variable=self.gen_lua,
                        command=self._toggle_lua).pack(anchor='w')
        ttk.Label(right, text="  Crée/met à jour lua/autorun/sh_*_pm.lua",
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 3))

        self.lua_sub = ttk.Frame(right)
        self.lua_sub.pack(anchor='w', padx=(16, 0))

        self.lua_chands = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.lua_sub, text="Inclure les C-Hands dans le Lua",
                        variable=self.lua_chands).pack(anchor='w')
        ttk.Label(self.lua_sub,
                  text="  Ajoute le hook PlayerSetHandsModel si\n  les c_arms sont présents",
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w')

        # ════════════════════ Onglet Avancé ════════════════════
        aleft  = ttk.Frame(advanced_tab)
        aleft.pack(side='left', fill='both', expand=True)
        aright = ttk.Frame(advanced_tab)
        aright.pack(side='left', fill='both', expand=True, padx=(12, 0))

        # Sons
        self.comp_snd = tk.BooleanVar(value=False)
        ttk.Checkbutton(aleft, text="Compresser les sons",
                        variable=self.comp_snd,
                        command=self._toggle_snd).pack(anchor='w')
        snd_status = (self.t('ffmpeg_ok') if FFMPEG_AVAILABLE
                      else self.t('ffmpeg_missing_lbl'))
        snd_color = self.GREEN if FFMPEG_AVAILABLE else self.YELLOW
        ttk.Label(aleft, text=f"  {snd_status}",
                  foreground=snd_color, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        self.snd_sub = ttk.Frame(aleft)
        self.snd_sub.pack(anchor='w', padx=(16, 0))

        rs = ttk.Frame(self.snd_sub)
        rs.pack(anchor='w')
        ttk.Label(rs, text=self.t('label_bitrate')).pack(side='left')
        self.snd_qual = tk.StringVar(value='128k')
        ttk.Combobox(rs, textvariable=self.snd_qual, width=8,
                     values=['64k', '96k', '128k', '192k', '320k'],
                     state='readonly').pack(side='left', padx=4)

        # Niveau ZIP
        ttk.Label(aleft, text="Niveau de compression ZIP :",
                  foreground=self.FG).pack(anchor='w', pady=(12, 2))
        zr = ttk.Frame(aleft)
        zr.pack(anchor='w')
        ttk.Label(zr, text=self.t('zip_fast')).pack(side='left')
        self.zip_lvl = tk.IntVar(value=6)
        ttk.Scale(zr, from_=1, to=9, variable=self.zip_lvl,
                  orient='h', length=100).pack(side='left', padx=4)
        ttk.Label(zr, text="Max").pack(side='left')

        # Infos dépendances (côté droit de l'onglet avancé)
        ttk.Label(aright, text="Bibliothèques détectées :",
                  font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        for label, ok in (
            ("Pillow (.png/.jpg/.tga)", PIL_AVAILABLE),
            ("vtflib (.vtf natif)",     VTFLIB_AVAILABLE),
            ("ffmpeg (sons)",           FFMPEG_AVAILABLE),
        ):
            mark  = "✓" if ok else "✗"
            color = self.GREEN if ok else self.SUB
            ttk.Label(aright, text=f"  {mark}  {label}",
                      foreground=color, font=('Segoe UI', 8)).pack(anchor='w')
        ttk.Label(aright,
                  text="\nSans vtflib, les .vtf sont réduits par\n"
                       "troncature de mipmaps (résolution\n"
                       "max respectée, sans dépendance).",
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(6, 0))

        self._toggle_tex()
        self._toggle_snd()
        self._toggle_lua()
        self._toggle_target_size()

    def _build_progress_section(self, parent):
        frm = ttk.LabelFrame(parent, text=self.t('progress_section'), padding=8)
        frm.pack(fill='x', pady=(0, 6))

        self.prog_var = tk.DoubleVar(value=0)
        ttk.Progressbar(frm, variable=self.prog_var, maximum=100).pack(fill='x')

        status_row = ttk.Frame(frm)
        status_row.pack(fill='x', pady=(3, 0))

        self.status_var = tk.StringVar(value="Prêt")
        ttk.Label(status_row, textvariable=self.status_var,
                  foreground=self.SUB).pack(side='left')

        self.file_var = tk.StringVar(value="")
        ttk.Label(status_row, textvariable=self.file_var,
                  foreground=self.SUB, font=('Consolas', 8)).pack(side='right')

    def _build_log_section(self, parent):
        frm = ttk.LabelFrame(parent, text=self.t('log_section'), padding=8)
        frm.pack(fill='both', expand=True, pady=(0, 8))

        self.log_box = scrolledtext.ScrolledText(
            frm, height=9,
            bg=self.LOG_BG, fg=self.FG,
            insertbackground=self.FG,
            font=('Consolas', 9),
            state='disabled',
            relief='flat', borderwidth=0,
            selectbackground=self.ACCENT,
            selectforeground=self.BG,
        )
        self.log_box.pack(fill='both', expand=True)

        self.log_box.tag_configure('header',  foreground=self.ACCENT, font=('Consolas', 9, 'bold'))
        self.log_box.tag_configure('success', foreground=self.GREEN)
        self.log_box.tag_configure('warning', foreground=self.YELLOW)
        self.log_box.tag_configure('error',   foreground=self.RED)
        self.log_box.tag_configure('info',    foreground=self.FG)

    def _build_buttons(self, parent):
        row = ttk.Frame(parent)
        row.pack(fill='x')

        ttk.Button(row, text=self.t('btn_clear_log'),
                   command=self._clear_log).pack(side='left')

        self.open_btn = ttk.Button(row, text="Ouvrir le dossier de sortie",
                                   command=self._open_output, state='disabled')
        self.open_btn.pack(side='left', padx=(6, 0))

        self.stop_btn = ttk.Button(row, text="Annuler",
                                   command=self._cancel, state='disabled')
        self.stop_btn.pack(side='right', padx=(4, 0))

        self.run_btn = ttk.Button(row, text=self.t('btn_run'),
                                  command=self._start, style='Accent.TButton')
        self.run_btn.pack(side='right')

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _toggle_tex(self):
        self._set_sub_state(self.tex_sub, self.comp_tex.get())

    def _toggle_snd(self):
        self._set_sub_state(self.snd_sub, self.comp_snd.get())

    def _toggle_lua(self):
        self._set_sub_state(self.lua_sub, self.gen_lua.get())

    @staticmethod
    def _set_sub_state(frame, enabled: bool):
        state = 'normal' if enabled else 'disabled'
        for widget in frame.winfo_children():
            children = widget.winfo_children()
            targets = children if children else [widget]
            for w in targets:
                try:
                    w.configure(state=state)
                except tk.TclError:
                    pass

    def _apply_profile(self, _event=None):
        preset = self.PRESETS.get(self.profile_var.get())
        if preset is None:
            return
        self.rem_chands.set(preset['remove_chands'])
        self.rem_unused.set(preset['remove_unused'])
        self.comp_tex.set(preset['compress_textures'])
        self.max_res.set(preset['max_res'])
        self.tex_qual.set(preset['quality'])
        self.comp_snd.set(preset['compress_sounds'] and FFMPEG_AVAILABLE)
        self.snd_qual.set(preset['sound_quality'])
        self.zip_lvl.set(preset['zip_level'])
        self._toggle_tex()
        self._toggle_snd()
        self._toggle_lua()

    def _scan_source(self):
        src = self.source_var.get().strip()
        if not src or not Path(src).exists():
            self.stats_var.set("")
            return
        self.stats_var.set("Analyse de la source…")
        threading.Thread(target=self._scan_source_thread, args=(src,), daemon=True).start()

    def _scan_source_thread(self, src: str):
        try:
            p = Path(src)
            if p.is_file():
                text = f"Fichier source : {Compressor._fmt_size(p.stat().st_size)}"
            else:
                count = 0
                total = 0
                for fp in p.rglob('*'):
                    if fp.is_file():
                        count += 1
                        total += fp.stat().st_size
                text = f"Source : {count} fichier(s) — {Compressor._fmt_size(total)}"
        except OSError:
            text = ""
        self.root.after(0, lambda: self.stats_var.set(text))

    def _browse_source(self):
        if self.src_type.get() == 'gma':
            path = filedialog.askopenfilename(
                title=self.t('dialog_select_gma'),
                filetypes=[(self.t('filetype_gma'), "*.gma"), (self.t('filetype_all'), "*.*")],
            )
        else:
            path = filedialog.askdirectory(title=self.t('dialog_select_folder'))
        if path:
            self.source_var.set(path)
            if not self.output_var.get():
                p = Path(path)
                self.output_var.set(str(p.parent / (p.stem + '_compressed')))
            self._scan_source()

    def _browse_output(self):
        fmt = self.out_fmt.get()
        if fmt == 'folder':
            path = filedialog.askdirectory(title=self.t('dialog_output_folder'))
        elif fmt == 'gma':
            path = filedialog.asksaveasfilename(
                title=self.t('dialog_save_gma'),
                defaultextension='.gma',
                filetypes=[(self.t('filetype_gma'), "*.gma")],
            )
        else:
            path = filedialog.asksaveasfilename(
                title=self.t('dialog_save_zip'),
                defaultextension='.zip',
                filetypes=[(self.t('filetype_zip'), "*.zip")],
            )
        if path:
            self.output_var.set(path)

    def _start(self):
        src = self.source_var.get().strip()
        out = self.output_var.get().strip()

        if not src:
            messagebox.showwarning(self.t('msg_source_missing_title'),
                                   self.t('msg_source_missing_body'))
            return
        if not out:
            messagebox.showwarning(self.t('msg_output_missing_title'),
                                   self.t('msg_output_missing_body'))
            return
        if not Path(src).exists():
            messagebox.showerror(self.t('msg_source_not_found_title'),
                                 self.t('msg_source_not_found_body', src=src))
            return

        target_size_mb = None
        if self.target_size_enabled.get():
            try:
                target_size_mb = float(self.target_size_mb.get().replace(',', '.'))
            except ValueError:
                messagebox.showwarning(self.t('msg_invalid_target_size_title'),
                                       self.t('msg_invalid_target_size_body'))
                return

        opts = {
            'source':            src,
            'output':            out,
            'source_type':       self.src_type.get(),
            'output_format':     self.out_fmt.get(),
            'remove_chands':     self.rem_chands.get(),
            'remove_unused':     self.rem_unused.get(),
            'compress_textures': self.comp_tex.get(),
            'max_resolution':    self.max_res.get(),
            'texture_quality':   self.tex_qual.get(),
            'compress_sounds':   self.comp_snd.get() and FFMPEG_AVAILABLE,
            'sound_quality':     self.snd_qual.get(),
            'zip_level':         int(self.zip_lvl.get()),
            'gen_lua':           self.gen_lua.get(),
            'lua_chands':        self.lua_chands.get(),
            'check_materials':   self.check_materials.get(),
            'target_size_mb':    target_size_mb,
            'dry_run':           self.dry_run.get(),
            'backup_original':   self.backup.get(),
            'batch':             self.batch.get(),
            'lang':              self.lang,
        }

        self.run_btn.configure(state='disabled')
        self.stop_btn.configure(state='normal')
        self.open_btn.configure(state='disabled')
        self.prog_var.set(0)
        self.file_var.set("")

        self._compressor = Compressor(
            opts,
            log_fn=self._log,
            progress_fn=self._set_prog,
            status_fn=self._set_status,
            current_file_fn=self._set_current_file,
        )
        self._thread = threading.Thread(target=self._run_compressor, daemon=True)
        self._thread.start()

    def _run_compressor(self):
        self._compressor.run()
        self.root.after(0, self._on_done)

    def _on_done(self):
        self.run_btn.configure(state='normal')
        self.stop_btn.configure(state='disabled')
        self.file_var.set("")
        comp = self._compressor
        if comp and comp.final_size is not None:
            self.open_btn.configure(state='normal')
            size = Compressor._fmt_size(comp.final_size)
            self.stats_var.set(f"Terminé : {size}  (-{comp.reduction:.1f}%)")

    def _cancel(self):
        if self._compressor:
            self._compressor.cancel()

    def _open_output(self):
        out = Path(self.output_var.get().strip())
        target = out if out.is_dir() else out.parent
        try:
            if sys.platform == 'win32':
                os.startfile(str(target))
            elif sys.platform == 'darwin':
                subprocess.run(['open', str(target)])
            else:
                subprocess.run(['xdg-open', str(target)])
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'ouvrir le dossier :\n{e}")

    def _log(self, msg: str):
        tag = 'info'
        if msg.startswith('▶'):
            tag = 'header'
        elif '✗' in msg or 'ERREUR' in msg:
            tag = 'error'
        elif '⚠' in msg:
            tag = 'warning'
        elif '✓' in msg:
            tag = 'success'

        def _do():
            self.log_box.configure(state='normal')
            self.log_box.insert('end', msg + '\n', tag)
            self.log_box.see('end')
            self.log_box.configure(state='disabled')
        self.root.after(0, _do)

    def _set_prog(self, val: float):
        self.root.after(0, lambda: self.prog_var.set(val))

    def _set_status(self, msg: str):
        self.root.after(0, lambda: self.status_var.set(msg))

    def _set_current_file(self, name: str):
        display = f"→ {name}" if name else ""
        self.root.after(0, lambda: self.file_var.set(display))

    def _clear_log(self):
        self.log_box.configure(state='normal')
        self.log_box.delete('1.0', 'end')
        self.log_box.configure(state='disabled')

    def _log_header(self):
        self._log(self.t('log_app_version', version=VERSION))
        libs = (
            f"PIL : {'✓' if PIL_AVAILABLE else '✗'}  |  "
            f"VTFLib : {'✓' if VTFLIB_AVAILABLE else '✗'}  |  "
            f"ffmpeg : {'✓' if FFMPEG_AVAILABLE else '✗'}"
        )
        self._log(libs)
        if not PIL_AVAILABLE:
            self._log(self.t('log_install_pillow'))
        if not VTFLIB_AVAILABLE:
            self._log(self.t('log_install_vtflib'))
        self._log("")

    # ── Bascules thème / langue / taille cible ────────────────────────────────

    def _toggle_target_size(self):
        state = 'normal' if self.target_size_enabled.get() else 'disabled'
        self.target_size_entry.configure(state=state)

    def _toggle_theme(self):
        self.theme_name = 'light' if self.theme_name == 'dark' else 'dark'
        self._apply_palette()
        self._rebuild()

    def _toggle_language(self):
        self.lang = 'en' if self.lang == 'fr' else 'fr'
        self._rebuild()

    def _collect_state(self) -> dict:
        return {
            'source':              self.source_var.get(),
            'output':              self.output_var.get(),
            'src_type':            self.src_type.get(),
            'out_fmt':             self.out_fmt.get(),
            'profile_id':          self._profile_label_to_id.get(self.profile_var.get(), 'custom'),
            'rem_chands':          self.rem_chands.get(),
            'rem_unused':          self.rem_unused.get(),
            'check_materials':     self.check_materials.get(),
            'comp_tex':            self.comp_tex.get(),
            'max_res_no_limit':    not self.max_res.get().isdigit(),
            'max_res':             self.max_res.get(),
            'tex_qual':            self.tex_qual.get(),
            'gen_lua':             self.gen_lua.get(),
            'lua_chands':          self.lua_chands.get(),
            'comp_snd':            self.comp_snd.get(),
            'snd_qual':            self.snd_qual.get(),
            'zip_lvl':             self.zip_lvl.get(),
            'dry_run':             self.dry_run.get(),
            'backup':              self.backup.get(),
            'target_size_enabled': self.target_size_enabled.get(),
            'target_size_mb':      self.target_size_mb.get(),
            'batch':               self.batch.get(),
        }

    def _restore_state(self, state: dict):
        self.source_var.set(state['source'])
        self.output_var.set(state['output'])
        self.src_type.set(state['src_type'])
        self.out_fmt.set(state['out_fmt'])
        self.profile_var.set(self._profile_label(state['profile_id']))
        self.rem_chands.set(state['rem_chands'])
        self.rem_unused.set(state['rem_unused'])
        self.check_materials.set(state['check_materials'])
        self.comp_tex.set(state['comp_tex'])
        self.max_res.set(self.t('no_limit') if state['max_res_no_limit'] else state['max_res'])
        self.tex_qual.set(state['tex_qual'])
        self.gen_lua.set(state['gen_lua'])
        self.lua_chands.set(state['lua_chands'])
        self.comp_snd.set(state['comp_snd'])
        self.snd_qual.set(state['snd_qual'])
        self.zip_lvl.set(state['zip_lvl'])
        self.dry_run.set(state['dry_run'])
        self.backup.set(state['backup'])
        self.target_size_enabled.set(state['target_size_enabled'])
        self.target_size_mb.set(state['target_size_mb'])
        self.batch.set(state['batch'])

        self._toggle_tex()
        self._toggle_snd()
        self._toggle_lua()
        self._toggle_target_size()
        self._scan_source()

    def _rebuild(self):
        state = self._collect_state()
        log_content = self.log_box.get('1.0', 'end-1c')

        for child in self.root.winfo_children():
            child.destroy()

        self.root.configure(bg=self.BG)
        self._setup_styles()
        self._build_ui()
        self._restore_state(state)

        if log_content:
            for line in log_content.split('\n'):
                self._log(line)

    # ── Glisser-déposer ────────────────────────────────────────────────────────

    def _on_drop_source(self, event):
        raw = event.data.strip()
        if raw.startswith('{'):
            path = raw[1:raw.index('}')]
        else:
            path = raw.split()[0]
        path = path.strip()
        if not path:
            return
        p = Path(path)
        self.source_var.set(path)
        self.src_type.set('gma' if p.suffix.lower() == '.gma' else 'folder')
        if not self.output_var.get():
            self.output_var.set(str(p.parent / (p.stem + '_compressed')))
        self._scan_source()

    def run(self):
        self.root.mainloop()


# ─── Mode CLI ─────────────────────────────────────────────────────────────────

def cli_main():
    import argparse

    parser = argparse.ArgumentParser(
        prog='compressez_pm',
        description="Compressez PM GMod – Compresseur d'addons Playermodel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python compressez_pm.py mon_addon/              sortie/
  python compressez_pm.py mon_addon.gma           sortie.gma   --no-chands
  python compressez_pm.py mon_addon/              sortie.zip   --format zip --quality 70 --max-res 512
        """,
    )
    parser.add_argument('source',   help="Dossier ou fichier .gma source")
    parser.add_argument('output',   help="Chemin de sortie")
    parser.add_argument('--format', choices=['folder', 'gma', 'zip'], default='folder',
                        dest='output_format', help="Format de sortie (défaut : folder)")
    parser.add_argument('--no-chands',   action='store_true', help="Supprimer les C-Hands")
    parser.add_argument('--no-unused',   action='store_true', help="Supprimer les fichiers inutiles")
    parser.add_argument('--no-textures', action='store_true', help="Ne pas optimiser les textures")
    parser.add_argument('--quality',   type=int, default=85, metavar='10-100',
                        help="Qualité des textures (défaut : 85)")
    parser.add_argument('--max-res',   type=str, default='1024',
                        metavar='256|512|1024|2048|Aucune limite',
                        help="Résolution max des textures (défaut : 1024)")
    parser.add_argument('--compress-sounds', action='store_true',
                        help="Compresser les sons (nécessite ffmpeg)")
    parser.add_argument('--sound-quality', default='128k',
                        choices=['64k', '96k', '128k', '192k', '320k'],
                        help="Bitrate audio (défaut : 128k)")
    parser.add_argument('--zip-level', type=int, default=6,
                        choices=range(1, 10), metavar='1-9',
                        help="Niveau de compression ZIP (défaut : 6)")
    parser.add_argument('--gen-lua', action='store_true', default=True,
                        help="Générer/mettre à jour le fichier Lua PM (défaut : activé)")
    parser.add_argument('--no-lua', action='store_true',
                        help="Ne pas générer de fichier Lua")
    parser.add_argument('--no-lua-chands', action='store_true',
                        help="Ne pas inclure les C-Hands dans le Lua généré")
    parser.add_argument('--no-check-materials', action='store_true',
                        help="Ne pas vérifier les matériaux/textures manquants")
    parser.add_argument('--target-size', type=float, default=None, metavar='MO',
                        help="Taille cible en Mo : ajuste automatiquement "
                             "résolution/qualité des textures pour l'atteindre")
    parser.add_argument('--dry-run', action='store_true',
                        help="Mode aperçu : analyse et affiche les changements "
                             "sans rien écrire sur le disque")
    parser.add_argument('--backup', action='store_true',
                        help="Sauvegarder la sortie existante avant écrasement")
    parser.add_argument('--batch', action='store_true',
                        help="Mode batch : traite chaque sous-dossier/.gma de "
                             "la source comme un addon distinct")
    parser.add_argument('--lang', choices=['fr', 'en'], default='fr',
                        help="Langue des messages (défaut : fr)")

    args = parser.parse_args()

    opts = {
        'source':            args.source,
        'output':            args.output,
        'source_type':       'gma' if args.source.endswith('.gma') else 'folder',
        'output_format':     args.output_format,
        'remove_chands':     args.no_chands,
        'remove_unused':     args.no_unused,
        'compress_textures': not args.no_textures,
        'max_resolution':    args.max_res,
        'texture_quality':   args.quality,
        'compress_sounds':   args.compress_sounds,
        'sound_quality':     args.sound_quality,
        'zip_level':         args.zip_level,
        'gen_lua':           not args.no_lua,
        'lua_chands':        not args.no_lua_chands,
        'check_materials':   not args.no_check_materials,
        'target_size_mb':    args.target_size,
        'dry_run':           args.dry_run,
        'backup_original':   args.backup,
        'batch':             args.batch,
        'lang':              args.lang,
    }

    print(t('cli_header', args.lang, version=VERSION))
    Compressor(opts,
               log_fn=print,
               progress_fn=lambda v: None,
               status_fn=lambda s: print(f"[{s}]")).run()


# ─── Point d'entrée ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    if len(sys.argv) > 1:
        cli_main()
    elif TK_AVAILABLE:
        App().run()
    else:
        print("tkinter non disponible. Utilisez le mode CLI :")
        print("  python compressez_pm.py --help")
        sys.exit(1)
