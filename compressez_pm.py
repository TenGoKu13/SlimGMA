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

    def __init__(self, opts: dict, log_fn, progress_fn, status_fn):
        self.opts        = opts
        self.log         = log_fn
        self.set_progress = progress_fn
        self.set_status  = status_fn
        self.cancel_flag = threading.Event()

    def cancel(self):
        self.cancel_flag.set()

    def run(self):
        try:
            src = Path(self.opts['source'])

            self.set_status("Chargement des fichiers…")
            files = self._load_files(src)

            if not files:
                self.log("ERREUR : Aucun fichier trouvé dans la source.")
                return

            self.log(f"Fichiers chargés : {len(files)}")
            original_size = sum(len(v) for v in files.values())
            self.log(f"Taille originale : {self._fmt_size(original_size)}")
            self.log("")

            # ── Étape 1 : C-Hands ──────────────────────────────────────────
            if self.opts.get('remove_chands') and not self.cancel_flag.is_set():
                self.set_status("Suppression des C-Hands…")
                removed = self._remove_chands(files)
                self.log(f"C-Hands supprimés : {removed} fichier(s)")
            self.set_progress(20)

            # ── Étape 2 : Fichiers inutiles ────────────────────────────────
            if self.opts.get('remove_unused') and not self.cancel_flag.is_set():
                self.set_status("Suppression des fichiers inutiles…")
                removed = self._remove_unused(files)
                self.log(f"Fichiers inutiles supprimés : {removed}")
            self.set_progress(35)

            # ── Étape 3 : Textures ─────────────────────────────────────────
            if self.opts.get('compress_textures') and not self.cancel_flag.is_set():
                self.set_status("Optimisation des textures…")
                self._optimize_textures(files)
            self.set_progress(65)

            # ── Étape 4 : Sons ─────────────────────────────────────────────
            if self.opts.get('compress_sounds') and FFMPEG_AVAILABLE and not self.cancel_flag.is_set():
                self.set_status("Compression des sons…")
                self._compress_sounds(files)
            self.set_progress(80)

            # ── Étape 5 : Lua PM ───────────────────────────────────────────
            if self.opts.get('gen_lua') and not self.cancel_flag.is_set():
                self.set_status("Génération du fichier Lua…")
                self._generate_lua(files, Path(self.opts['source']).stem)
            self.set_progress(90)

            # ── Étape 6 : Écriture ─────────────────────────────────────────
            if not self.cancel_flag.is_set():
                self.set_status("Écriture de la sortie…")
                self._write_output(files, src)
            self.set_progress(100)

            if not self.cancel_flag.is_set():
                final_size = sum(len(v) for v in files.values())
                reduction  = (1 - final_size / original_size) * 100 if original_size > 0 else 0
                self.log("")
                self.log(f"Taille finale  : {self._fmt_size(final_size)}")
                self.log(f"Réduction      : {reduction:.1f}%")
                self.log("Compression terminée avec succès !")
                self.set_status("Terminé !")
            else:
                self.log("\nCompression annulée.")
                self.set_status("Annulé")

        except Exception as e:
            import traceback
            self.log(f"\nERREUR : {e}")
            self.log(traceback.format_exc())
            self.set_status("Erreur !")

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
                    self.log(f"  Supprimé C-Hand : {path}")
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
                self.log(f"  Supprimé inutile : {path}")
        for p in to_remove:
            del files[p]
        return len(to_remove)

    # ── Textures ──────────────────────────────────────────────────────────────

    def _optimize_textures(self, files: dict) -> None:
        max_res_str = self.opts.get('max_resolution', '1024')
        quality     = self.opts.get('texture_quality', 85)
        max_res     = None if max_res_str == 'Aucune limite' else int(max_res_str)

        tex_files = {k: v for k, v in files.items()
                     if Path(k).suffix.lower() in TEXTURE_EXTENSIONS and k != '__meta__'}

        if not tex_files:
            self.log("  Aucune texture trouvée.")
            return

        self.log(f"  {len(tex_files)} texture(s) trouvée(s)…")
        total = len(tex_files)

        for i, (path, data) in enumerate(tex_files.items()):
            if self.cancel_flag.is_set():
                break

            ext = Path(path).suffix.lower()
            new_data = None

            if ext == '.vtf':
                new_data = self._process_vtf(path, data, max_res, quality)
            elif PIL_AVAILABLE and ext in {'.png', '.jpg', '.jpeg', '.tga', '.bmp'}:
                new_data = self._process_image_pil(path, data, ext, max_res, quality)

            if new_data and len(new_data) < len(data):
                savings = len(data) - len(new_data)
                self.log(f"  {path} : -{self._fmt_size(savings)}")
                files[path] = new_data

            self.set_progress(35 + (i / total) * 30)

    def _process_vtf(self, path: str, data: bytes, max_res, quality: int) -> bytes:
        if VTFLIB_AVAILABLE:
            return self._process_vtf_vtflib(data, max_res, quality)
        # Sans VTFLib on ne peut pas re-encoder le DXT ; on retourne intact
        return data

    def _process_vtf_vtflib(self, data: bytes, max_res, quality: int) -> bytes:
        try:
            lib = vtflib.VTFLib()
            lib.image_load_lump(data)
            w, h = lib.width(), lib.height()
            if max_res and (w > max_res or h > max_res):
                new_w = min(w, max_res)
                new_h = min(h, max_res)
                lib.image_resize(new_w, new_h)
            return bytes(lib.image_save_lump())
        except Exception:
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
            self.log("  Aucun son trouvé.")
            return

        self.log(f"  {len(snd_files)} son(s) trouvé(s)…")

        for path, data in snd_files.items():
            if self.cancel_flag.is_set():
                break
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
                        self.log(f"  {path} → {new_key} : -{self._fmt_size(savings)}")
            except Exception as e:
                self.log(f"  Erreur son {path}: {e}")
            finally:
                for tmp in (tmp_in, tmp_out):
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass

    # ── Génération Lua ────────────────────────────────────────────────────────

    def _generate_lua(self, files: dict, addon_stem: str) -> None:
        """Génère ou met à jour le fichier Lua d'enregistrement du playermodel."""

        # 1. Trouver tous les .mdl dans models/player/ (hors LOD)
        pm_models = sorted(
            p for p in files
            if p.startswith('models/player/') and p.endswith('.mdl')
            and not re.search(r'_lod\d+\.mdl$', p)
        )

        if not pm_models:
            self.log("  Lua : aucun .mdl dans models/player/ – ignoré")
            return

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
            self.log(f"  Lua mis à jour : {existing_path}")
        else:
            new_path = f'lua/autorun/sh_{safe_stem}_pm.lua'
            files[new_path] = lua_bytes
            self.log(f"  Lua créé : {new_path}")

    # ── Écriture ─────────────────────────────────────────────────────────────

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

        if fmt == 'folder':
            output.mkdir(parents=True, exist_ok=True)
            for path, data in out_files.items():
                dest = output / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
            self.log(f"  Dossier : {output}/")

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
            out_path = output if output.suffix == '.gma' else output.with_suffix('.gma')
            out_path.parent.mkdir(parents=True, exist_ok=True)
            gma.save(str(out_path))
            self.log(f"  GMA : {out_path}")

        elif fmt == 'zip':
            out_path = output if output.suffix == '.zip' else output.with_suffix('.zip')
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(str(out_path), 'w',
                                 zipfile.ZIP_DEFLATED,
                                 compresslevel=zip_lvl) as zf:
                for path, data in out_files.items():
                    zf.writestr(path, data)
            self.log(f"  ZIP : {out_path}")

    # ── Utilitaires ──────────────────────────────────────────────────────────

    @staticmethod
    def _fmt_size(n: int) -> str:
        for unit in ['o', 'Ko', 'Mo', 'Go']:
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} To"


# ─── Interface graphique ──────────────────────────────────────────────────────

class App:

    # Palette Catppuccin Mocha
    BG      = '#1e1e2e'
    FG      = '#cdd6f4'
    ACCENT  = '#89b4fa'
    SUB     = '#6c7086'
    SURFACE = '#313244'
    GREEN   = '#a6e3a1'
    RED     = '#f38ba8'
    YELLOW  = '#f9e2af'

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"Compressez PM GMod  v{VERSION}")
        self.root.geometry("740x700")
        self.root.configure(bg=self.BG)
        self.root.resizable(True, True)
        self.root.minsize(620, 580)

        self._compressor: Compressor | None = None
        self._thread: threading.Thread | None = None

        self._setup_styles()
        self._build_ui()
        self._log_header()

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

        s.map('Accent.TButton',  background=[('active', '#74c7ec')])
        s.map('TButton',         background=[('active', '#45475a')])
        s.map('TCheckbutton',    background=[('active', self.BG)])
        s.map('TRadiobutton',    background=[('active', self.BG)])
        s.map('TCombobox',       fieldbackground=[('readonly', self.SURFACE)])

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

        # Corps principal avec scroll
        main = ttk.Frame(self.root, padding=(10, 8, 10, 10))
        main.pack(fill='both', expand=True)

        self._build_io_section(main)
        self._build_options_section(main)
        self._build_progress_section(main)
        self._build_log_section(main)
        self._build_buttons(main)

    def _build_io_section(self, parent):
        frm = ttk.LabelFrame(parent, text=" Entrée / Sortie ", padding=8)
        frm.pack(fill='x', pady=(0, 6))

        # Source
        r = ttk.Frame(frm)
        r.pack(fill='x', pady=2)
        ttk.Label(r, text="Source :", width=9).pack(side='left')
        self.source_var = tk.StringVar()
        ttk.Entry(r, textvariable=self.source_var).pack(side='left', fill='x', expand=True, padx=(0, 4))
        ttk.Button(r, text="Parcourir", command=self._browse_source, width=10).pack(side='right')

        # Output
        r2 = ttk.Frame(frm)
        r2.pack(fill='x', pady=2)
        ttk.Label(r2, text="Sortie :", width=9).pack(side='left')
        self.output_var = tk.StringVar()
        ttk.Entry(r2, textvariable=self.output_var).pack(side='left', fill='x', expand=True, padx=(0, 4))
        ttk.Button(r2, text="Parcourir", command=self._browse_output, width=10).pack(side='right')

        # Types
        types_row = ttk.Frame(frm)
        types_row.pack(fill='x', pady=(5, 0))

        ttk.Label(types_row, text="Type source :").pack(side='left')
        self.src_type = tk.StringVar(value='folder')
        ttk.Radiobutton(types_row, text="Dossier",      variable=self.src_type, value='folder').pack(side='left', padx=(4, 10))
        ttk.Radiobutton(types_row, text="Fichier .gma", variable=self.src_type, value='gma').pack(side='left', padx=(0, 20))

        ttk.Label(types_row, text="Format sortie :").pack(side='left')
        self.out_fmt = tk.StringVar(value='folder')
        ttk.Radiobutton(types_row, text="Dossier", variable=self.out_fmt, value='folder').pack(side='left', padx=(4, 8))
        ttk.Radiobutton(types_row, text=".gma",    variable=self.out_fmt, value='gma').pack(side='left', padx=(0, 8))
        ttk.Radiobutton(types_row, text=".zip",    variable=self.out_fmt, value='zip').pack(side='left')

    def _build_options_section(self, parent):
        frm = ttk.LabelFrame(parent, text=" Options ", padding=8)
        frm.pack(fill='x', pady=(0, 6))

        left  = ttk.Frame(frm)
        left.pack(side='left', fill='both', expand=True)
        right = ttk.Frame(frm)
        right.pack(side='left', fill='both', expand=True, padx=(12, 0))

        # ── Colonne gauche ────────────────────────────────────────────────

        # C-Hands
        self.rem_chands = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text="Supprimer les C-Hands",
                        variable=self.rem_chands).pack(anchor='w')
        ttk.Label(left, text="  Retire les bras à la 1ʳᵉ personne (c_arms, c_*)",
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        # Fichiers inutiles
        self.rem_unused = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text="Supprimer les fichiers inutiles",
                        variable=self.rem_unused).pack(anchor='w')
        ttk.Label(left, text="  .txt, .md, .pdf, .psd, .log…",
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        # Textures
        self.comp_tex = tk.BooleanVar(value=PIL_AVAILABLE or VTFLIB_AVAILABLE)
        ttk.Checkbutton(left, text="Optimiser les textures",
                        variable=self.comp_tex,
                        command=self._toggle_tex).pack(anchor='w')

        self.tex_sub = ttk.Frame(left)
        self.tex_sub.pack(anchor='w', padx=(16, 0), pady=(2, 0))

        r1 = ttk.Frame(self.tex_sub)
        r1.pack(anchor='w', pady=1)
        ttk.Label(r1, text="Résolution max :").pack(side='left')
        self.max_res = tk.StringVar(value='1024')
        ttk.Combobox(r1, textvariable=self.max_res, width=14,
                     values=['256', '512', '1024', '2048', 'Aucune limite'],
                     state='readonly').pack(side='left', padx=4)

        r2 = ttk.Frame(self.tex_sub)
        r2.pack(anchor='w', pady=1)
        ttk.Label(r2, text="Qualité :").pack(side='left')
        self.tex_qual = tk.IntVar(value=85)
        ttk.Scale(r2, from_=10, to=100, variable=self.tex_qual,
                  orient='h', length=110).pack(side='left', padx=4)
        self.qual_lbl = ttk.Label(r2, text="85%", width=5)
        self.qual_lbl.pack(side='left')
        self.tex_qual.trace_add('write', lambda *_: self.qual_lbl.config(
            text=f"{self.tex_qual.get()}%"))

        if not PIL_AVAILABLE and not VTFLIB_AVAILABLE:
            ttk.Label(self.tex_sub,
                      text="⚠  pip install Pillow  pour les images non-VTF",
                      foreground=self.YELLOW, font=('Segoe UI', 8)).pack(anchor='w', pady=(2, 0))

        # ── Colonne droite ────────────────────────────────────────────────

        # Sons
        self.comp_snd = tk.BooleanVar(value=False)
        ttk.Checkbutton(right, text="Compresser les sons",
                        variable=self.comp_snd,
                        command=self._toggle_snd).pack(anchor='w')
        snd_status = ("✓ ffmpeg détecté" if FFMPEG_AVAILABLE
                      else "⚠  ffmpeg introuvable dans le PATH")
        snd_color = self.GREEN if FFMPEG_AVAILABLE else self.YELLOW
        ttk.Label(right, text=f"  {snd_status}",
                  foreground=snd_color, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        self.snd_sub = ttk.Frame(right)
        self.snd_sub.pack(anchor='w', padx=(16, 0))

        rs = ttk.Frame(self.snd_sub)
        rs.pack(anchor='w')
        ttk.Label(rs, text="Bitrate :").pack(side='left')
        self.snd_qual = tk.StringVar(value='128k')
        ttk.Combobox(rs, textvariable=self.snd_qual, width=8,
                     values=['64k', '96k', '128k', '192k', '320k'],
                     state='readonly').pack(side='left', padx=4)

        # Niveau ZIP
        ttk.Label(right, text="Niveau de compression ZIP :",
                  foreground=self.FG).pack(anchor='w', pady=(12, 2))
        zr = ttk.Frame(right)
        zr.pack(anchor='w')
        ttk.Label(zr, text="Rapide").pack(side='left')
        self.zip_lvl = tk.IntVar(value=6)
        ttk.Scale(zr, from_=1, to=9, variable=self.zip_lvl,
                  orient='h', length=100).pack(side='left', padx=4)
        ttk.Label(zr, text="Max").pack(side='left')

        # ── Séparateur ────────────────────────────────────────────────────
        ttk.Separator(right, orient='horizontal').pack(fill='x', pady=(10, 4))

        # Génération Lua
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

        self._toggle_tex()
        self._toggle_snd()
        self._toggle_lua()

    def _build_progress_section(self, parent):
        frm = ttk.LabelFrame(parent, text=" Progression ", padding=8)
        frm.pack(fill='x', pady=(0, 6))

        self.prog_var = tk.DoubleVar(value=0)
        ttk.Progressbar(frm, variable=self.prog_var, maximum=100).pack(fill='x')

        self.status_var = tk.StringVar(value="Prêt")
        ttk.Label(frm, textvariable=self.status_var,
                  foreground=self.SUB).pack(anchor='w', pady=(3, 0))

    def _build_log_section(self, parent):
        frm = ttk.LabelFrame(parent, text=" Journal ", padding=8)
        frm.pack(fill='both', expand=True, pady=(0, 8))

        self.log_box = scrolledtext.ScrolledText(
            frm, height=9,
            bg='#11111b', fg=self.FG,
            insertbackground=self.FG,
            font=('Consolas', 9),
            state='disabled',
            relief='flat', borderwidth=0,
            selectbackground=self.ACCENT,
            selectforeground=self.BG,
        )
        self.log_box.pack(fill='both', expand=True)

    def _build_buttons(self, parent):
        row = ttk.Frame(parent)
        row.pack(fill='x')

        ttk.Button(row, text="Effacer journal",
                   command=self._clear_log).pack(side='left')

        self.stop_btn = ttk.Button(row, text="Annuler",
                                   command=self._cancel, state='disabled')
        self.stop_btn.pack(side='right', padx=(4, 0))

        self.run_btn = ttk.Button(row, text="  Compresser  ",
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

    def _browse_source(self):
        if self.src_type.get() == 'gma':
            path = filedialog.askopenfilename(
                title="Sélectionner un fichier GMA",
                filetypes=[("Fichiers GMA", "*.gma"), ("Tous les fichiers", "*.*")],
            )
        else:
            path = filedialog.askdirectory(title="Sélectionner le dossier de l'addon")
        if path:
            self.source_var.set(path)
            if not self.output_var.get():
                p = Path(path)
                self.output_var.set(str(p.parent / (p.stem + '_compressed')))

    def _browse_output(self):
        fmt = self.out_fmt.get()
        if fmt == 'folder':
            path = filedialog.askdirectory(title="Dossier de sortie")
        elif fmt == 'gma':
            path = filedialog.asksaveasfilename(
                title="Enregistrer le GMA",
                defaultextension='.gma',
                filetypes=[("Fichiers GMA", "*.gma")],
            )
        else:
            path = filedialog.asksaveasfilename(
                title="Enregistrer l'archive ZIP",
                defaultextension='.zip',
                filetypes=[("Archives ZIP", "*.zip")],
            )
        if path:
            self.output_var.set(path)

    def _start(self):
        src = self.source_var.get().strip()
        out = self.output_var.get().strip()

        if not src:
            messagebox.showwarning("Source manquante",
                                   "Veuillez sélectionner un dossier ou fichier source.")
            return
        if not out:
            messagebox.showwarning("Sortie manquante",
                                   "Veuillez indiquer un chemin de sortie.")
            return
        if not Path(src).exists():
            messagebox.showerror("Source introuvable", f"Le chemin n'existe pas :\n{src}")
            return

        opts = {
            'source':            src,
            'output':            out,
            'source_type':       self.src_type.get(),
            'output_format':     self.out_fmt.get(),
            'remove_chands':     self.rem_chands.get(),
            'remove_unused':     self.rem_unused.get(),
            'compress_textures': self.comp_tex.get() and (PIL_AVAILABLE or VTFLIB_AVAILABLE),
            'max_resolution':    self.max_res.get(),
            'texture_quality':   self.tex_qual.get(),
            'compress_sounds':   self.comp_snd.get() and FFMPEG_AVAILABLE,
            'sound_quality':     self.snd_qual.get(),
            'zip_level':         int(self.zip_lvl.get()),
            'gen_lua':           self.gen_lua.get(),
            'lua_chands':        self.lua_chands.get(),
        }

        self.run_btn.configure(state='disabled')
        self.stop_btn.configure(state='normal')
        self.prog_var.set(0)

        self._compressor = Compressor(
            opts,
            log_fn=self._log,
            progress_fn=self._set_prog,
            status_fn=self._set_status,
        )
        self._thread = threading.Thread(target=self._run_compressor, daemon=True)
        self._thread.start()

    def _run_compressor(self):
        self._compressor.run()
        self.root.after(0, self._on_done)

    def _on_done(self):
        self.run_btn.configure(state='normal')
        self.stop_btn.configure(state='disabled')

    def _cancel(self):
        if self._compressor:
            self._compressor.cancel()

    def _log(self, msg: str):
        def _do():
            self.log_box.configure(state='normal')
            self.log_box.insert('end', msg + '\n')
            self.log_box.see('end')
            self.log_box.configure(state='disabled')
        self.root.after(0, _do)

    def _set_prog(self, val: float):
        self.root.after(0, lambda: self.prog_var.set(val))

    def _set_status(self, msg: str):
        self.root.after(0, lambda: self.status_var.set(msg))

    def _clear_log(self):
        self.log_box.configure(state='normal')
        self.log_box.delete('1.0', 'end')
        self.log_box.configure(state='disabled')

    def _log_header(self):
        self._log(f"Compressez PM GMod  v{VERSION}")
        libs = (
            f"PIL : {'✓' if PIL_AVAILABLE else '✗'}  |  "
            f"VTFLib : {'✓' if VTFLIB_AVAILABLE else '✗'}  |  "
            f"ffmpeg : {'✓' if FFMPEG_AVAILABLE else '✗'}"
        )
        self._log(libs)
        if not PIL_AVAILABLE:
            self._log("→ pip install Pillow   (optimisation .png/.jpg/.tga)")
        if not VTFLIB_AVAILABLE:
            self._log("→ pip install vtflib   (optimisation .vtf native)")
        self._log("")

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
    }

    print(f"Compressez PM GMod v{VERSION} – mode CLI\n")
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
