"""Interface graphique (tkinter)."""
import os
import sys
import json
import threading
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

from .deps import PIL_AVAILABLE, VTFLIB_AVAILABLE, FFMPEG_AVAILABLE
from .constants import VERSION, CONFIG_PATH
from .i18n import t, STRINGS
from .compressor import Compressor


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

    def __init__(self):
        saved = self._load_config()
        self.lang = saved.get('lang', 'fr') if saved else 'fr'
        self.theme_name = saved.get('theme_name', 'dark') if saved else 'dark'
        self._apply_palette()

        self.root = TkinterDnD.Tk() if DND_AVAILABLE else tk.Tk()
        self.root.title(f"Compressez PM GMod  v{VERSION}")
        self.root.geometry("820x950")
        self.root.configure(bg=self.BG)
        self.root.resizable(True, True)
        self.root.minsize(700, 760)
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

        self._compressor: Compressor | None = None
        self._thread: threading.Thread | None = None

        self._setup_styles()
        self._build_ui()
        if saved:
            self._restore_state(saved)
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
                    bordercolor=self.SURFACE, thickness=12)
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
        hdr = tk.Frame(self.root, bg=self.SURFACE, pady=10)
        hdr.pack(fill='x')

        title_box = tk.Frame(hdr, bg=self.SURFACE)
        title_box.pack(side='left', padx=14)

        title_row = tk.Frame(title_box, bg=self.SURFACE)
        title_row.pack(anchor='w')
        tk.Label(title_row, text="🗜️", bg=self.SURFACE, fg=self.ACCENT,
                 font=('Segoe UI', 16)).pack(side='left', padx=(0, 6))
        tk.Label(title_row, text="Compressez PM GMod",
                 bg=self.SURFACE, fg=self.ACCENT,
                 font=('Segoe UI', 14, 'bold')).pack(side='left')
        tk.Label(title_row, text=f"  v{VERSION}",
                 bg=self.SURFACE, fg=self.SUB,
                 font=('Segoe UI', 9)).pack(side='left')

        tk.Label(title_box, text=self.t('app_tagline'),
                 bg=self.SURFACE, fg=self.SUB,
                 font=('Segoe UI', 8)).pack(anchor='w')

        theme_key = 'btn_theme_light' if self.theme_name == 'dark' else 'btn_theme_dark'
        ttk.Button(hdr, text=self.t(theme_key), command=self._toggle_theme,
                   width=14).pack(side='right', padx=(0, 14))
        lang_text = "English" if self.lang == 'fr' else "Français"
        ttk.Button(hdr, text=lang_text, command=self._toggle_language,
                   width=10).pack(side='right', padx=(0, 6))
        ttk.Button(hdr, text=self.t('btn_about'), command=self._show_about,
                   width=11).pack(side='right', padx=(0, 6))

        tk.Frame(self.root, bg=self.ACCENT, height=2).pack(fill='x')

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

        if DND_AVAILABLE:
            ttk.Label(frm, text=self.t('drop_hint'),
                      foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w')

        # Statistiques de la source (mises à jour après sélection)
        self.stats_var = tk.StringVar(value="")
        ttk.Label(frm, textvariable=self.stats_var,
                  foreground=self.ACCENT, font=('Segoe UI', 8, 'bold')).pack(anchor='w', pady=(4, 0))

    def _build_options_section(self, parent):
        # ── Profil rapide ───────────────────────────────────────────────────
        profile_frm = ttk.Frame(parent)
        profile_frm.pack(fill='x', pady=(0, 6))
        ttk.Label(profile_frm, text=self.t('label_profile')).pack(side='left')
        self._profile_label_to_id = {self._profile_label(pid): pid for pid in self.PRESETS}
        self.profile_var = tk.StringVar(value=self._profile_label('custom'))
        profile_combo = ttk.Combobox(profile_frm, textvariable=self.profile_var, width=26,
                                      values=list(self._profile_label_to_id.keys()), state='readonly')
        profile_combo.pack(side='left', padx=4)
        profile_combo.bind('<<ComboboxSelected>>', self._apply_profile)
        ttk.Label(profile_frm, text=self.t('profile_hint'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(side='left')

        # ── Onglets Général / Avancé ────────────────────────────────────────
        notebook = ttk.Notebook(parent)
        notebook.pack(fill='x', pady=(0, 6))

        general_tab  = ttk.Frame(notebook, padding=8)
        advanced_tab = ttk.Frame(notebook, padding=8)
        notebook.add(general_tab,  text=self.t('tab_general'))
        notebook.add(advanced_tab, text=self.t('tab_advanced'))

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

        # Suppression des textures inutilisées
        self.rem_unused_tex = tk.BooleanVar(value=False)
        ttk.Checkbutton(left, text=self.t('chk_remove_unused_tex'),
                        variable=self.rem_unused_tex).pack(anchor='w')
        ttk.Label(left, text=self.t('desc_remove_unused_tex'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        # Textures
        self.comp_tex = tk.BooleanVar(value=True)
        ttk.Checkbutton(right, text=self.t('chk_textures'),
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
        ttk.Checkbutton(right, text=self.t('chk_lua'),
                        variable=self.gen_lua,
                        command=self._toggle_lua).pack(anchor='w')
        ttk.Label(right, text=self.t('desc_lua'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 3))

        self.lua_sub = ttk.Frame(right)
        self.lua_sub.pack(anchor='w', padx=(16, 0))

        self.lua_chands = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.lua_sub, text=self.t('chk_lua_chands'),
                        variable=self.lua_chands).pack(anchor='w')
        ttk.Label(self.lua_sub,
                  text=self.t('desc_lua_chands'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w')

        # ════════════════════ Onglet Avancé ════════════════════
        row1 = ttk.Frame(advanced_tab)
        row1.pack(fill='x')
        aleft  = ttk.Frame(row1)
        aleft.pack(side='left', fill='both', expand=True)
        aright = ttk.Frame(row1)
        aright.pack(side='left', fill='both', expand=True, padx=(12, 0))

        # Sons
        self.comp_snd = tk.BooleanVar(value=False)
        ttk.Checkbutton(aleft, text=self.t('chk_sounds'),
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
        ttk.Label(aleft, text=self.t('label_zip_level'),
                  foreground=self.FG).pack(anchor='w', pady=(12, 2))
        zr = ttk.Frame(aleft)
        zr.pack(anchor='w')
        ttk.Label(zr, text=self.t('zip_fast')).pack(side='left')
        self.zip_lvl = tk.IntVar(value=6)
        ttk.Scale(zr, from_=1, to=9, variable=self.zip_lvl,
                  orient='h', length=100).pack(side='left', padx=4)
        ttk.Label(zr, text=self.t('zip_max')).pack(side='left')

        # Infos dépendances (côté droit de l'onglet avancé)
        ttk.Label(aright, text=self.t('libs_detected'),
                  font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        for label, ok in (
            (self.t('lib_pillow'), PIL_AVAILABLE),
            (self.t('lib_vtflib'), VTFLIB_AVAILABLE),
            (self.t('lib_ffmpeg'), FFMPEG_AVAILABLE),
        ):
            mark  = "✓" if ok else "✗"
            color = self.GREEN if ok else self.SUB
            ttk.Label(aright, text=f"  {mark}  {label}",
                      foreground=color, font=('Segoe UI', 8)).pack(anchor='w')
        ttk.Label(aright,
                  text=self.t('vtf_note'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(6, 0))

        # ── Sécurité / modes spéciaux ────────────────────────────────────────
        ttk.Separator(advanced_tab, orient='horizontal').pack(fill='x', pady=8)

        row2 = ttk.Frame(advanced_tab)
        row2.pack(fill='x')
        a2left  = ttk.Frame(row2)
        a2left.pack(side='left', fill='both', expand=True)
        a2right = ttk.Frame(row2)
        a2right.pack(side='left', fill='both', expand=True, padx=(12, 0))

        # Mode aperçu (dry-run)
        self.dry_run = tk.BooleanVar(value=False)
        ttk.Checkbutton(a2left, text=self.t('chk_dry_run'),
                        variable=self.dry_run).pack(anchor='w')
        ttk.Label(a2left, text=self.t('desc_dry_run'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        # Sauvegarde de l'original
        self.backup = tk.BooleanVar(value=False)
        ttk.Checkbutton(a2left, text=self.t('chk_backup'),
                        variable=self.backup).pack(anchor='w')
        ttk.Label(a2left, text=self.t('desc_backup'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        # Recompression DXT des textures non compressées
        self.convert_uncompressed = tk.BooleanVar(value=True)
        ttk.Checkbutton(a2left, text=self.t('chk_convert'),
                        variable=self.convert_uncompressed).pack(anchor='w')
        ttk.Label(a2left, text=self.t('desc_convert'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        # Rapport HTML d'analyse
        self.gen_report = tk.BooleanVar(value=True)
        ttk.Checkbutton(a2left, text=self.t('chk_report'),
                        variable=self.gen_report).pack(anchor='w')
        ttk.Label(a2left, text=self.t('desc_report'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        # Taille cible
        self.target_size_enabled = tk.BooleanVar(value=False)
        ts_row = ttk.Frame(a2right)
        ts_row.pack(anchor='w')
        ttk.Checkbutton(ts_row, text=self.t('chk_target_size'),
                        variable=self.target_size_enabled,
                        command=self._toggle_target_size).pack(side='left')
        self.target_size_mb = tk.StringVar(value='10')
        self.target_size_entry = ttk.Entry(ts_row, textvariable=self.target_size_mb, width=6)
        self.target_size_entry.pack(side='left', padx=4)
        ttk.Label(ts_row, text=self.t('label_mb')).pack(side='left')
        ttk.Label(a2right, text=self.t('desc_target_size'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        # Mode batch
        self.batch = tk.BooleanVar(value=False)
        ttk.Checkbutton(a2right, text=self.t('chk_batch'),
                        variable=self.batch).pack(anchor='w')
        ttk.Label(a2right, text=self.t('desc_batch'),
                  foreground=self.SUB, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 5))

        self._toggle_tex()
        self._toggle_snd()
        self._toggle_lua()
        self._toggle_target_size()

    def _build_progress_section(self, parent):
        frm = ttk.LabelFrame(parent, text=self.t('progress_section'), padding=8)
        frm.pack(fill='x', pady=(0, 6))

        bar_row = ttk.Frame(frm)
        bar_row.pack(fill='x')

        self.prog_var = tk.DoubleVar(value=0)
        ttk.Progressbar(bar_row, variable=self.prog_var, maximum=100).pack(side='left', fill='x', expand=True)

        self.prog_pct_var = tk.StringVar(value="0%")
        ttk.Label(bar_row, textvariable=self.prog_pct_var, width=5, anchor='e',
                  foreground=self.ACCENT, font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(8, 0))

        status_row = ttk.Frame(frm)
        status_row.pack(fill='x', pady=(3, 0))

        self.status_dot_lbl = tk.Label(status_row, text="●", bg=self.BG, fg=self.SUB,
                                        font=('Segoe UI', 10))
        self.status_dot_lbl.pack(side='left', padx=(0, 4))

        self.status_var = tk.StringVar(value=self.t('status_ready'))
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

        self.open_btn = ttk.Button(row, text=self.t('btn_open_output'),
                                   command=self._open_output, state='disabled')
        self.open_btn.pack(side='left', padx=(6, 0))

        self.stop_btn = ttk.Button(row, text=self.t('btn_cancel'),
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
        pid = self._profile_label_to_id.get(self.profile_var.get())
        preset = self.PRESETS.get(pid)
        if preset is None:
            return
        self.rem_chands.set(preset['remove_chands'])
        self.rem_unused.set(preset['remove_unused'])
        self.comp_tex.set(preset['compress_textures'])
        max_res = preset['max_res']
        self.max_res.set(self.t('no_limit') if max_res == 'none' else max_res)
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
        self.stats_var.set(self.t('stats_analyzing'))
        threading.Thread(target=self._scan_source_thread, args=(src,), daemon=True).start()

    def _scan_source_thread(self, src: str):
        try:
            p = Path(src)
            if p.is_file():
                text = self.t('stats_source_file', size=Compressor._fmt_size(p.stat().st_size))
            else:
                count = 0
                total = 0
                for fp in p.rglob('*'):
                    if fp.is_file():
                        count += 1
                        total += fp.stat().st_size
                text = self.t('stats_source', count=count, size=Compressor._fmt_size(total))
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
            'remove_unused_textures': self.rem_unused_tex.get(),
            'convert_uncompressed': self.convert_uncompressed.get(),
            'gen_report':        self.gen_report.get(),
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
        self.prog_pct_var.set("0%")
        self.file_var.set("")
        self.status_dot_lbl.configure(fg=self.ACCENT)

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
            before = Compressor._fmt_size(comp.original_size)
            after = Compressor._fmt_size(comp.final_size)
            self.stats_var.set(self.t('stats_done', before=before, after=after, pct=f"{comp.reduction:.1f}"))
            self.status_dot_lbl.configure(fg=self.GREEN)
            self._show_summary(comp, before, after)
        elif comp and comp.cancel_flag.is_set():
            self.status_dot_lbl.configure(fg=self.YELLOW)
        else:
            self.status_dot_lbl.configure(fg=self.RED)

    def _show_summary(self, comp: 'Compressor', before: str, after: str):
        """Affiche un récapitulatif convivial à la fin d'une compression réussie."""
        saved = Compressor._fmt_size(max(0, (comp.original_size or 0) - (comp.final_size or 0)))
        pct = f"{comp.reduction:.1f}"
        body = self.t('summary_body', before=before, after=after, saved=saved, pct=pct)
        if comp.opts.get('dry_run'):
            messagebox.showinfo(self.t('summary_title'), body + "\n\n" + self.t('summary_dry_run'))
            return

        report_path = getattr(comp, 'report_path', None)

        win = tk.Toplevel(self.root)
        win.title(self.t('summary_title'))
        win.configure(bg=self.BG)
        win.transient(self.root)
        win.resizable(False, False)

        wrap = tk.Frame(win, bg=self.BG, padx=24, pady=20)
        wrap.pack(fill='both', expand=True)

        tk.Label(wrap, text=self.t('summary_title'), bg=self.BG, fg=self.ACCENT,
                 font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        tk.Label(wrap, text=body, bg=self.BG, fg=self.FG, justify='left',
                 font=('Segoe UI', 10)).pack(anchor='w', pady=(10, 16))

        btn_row = tk.Frame(wrap, bg=self.BG)
        btn_row.pack(fill='x')
        ttk.Button(btn_row, text=self.t('summary_open_folder'),
                   style='Accent.TButton',
                   command=lambda: (win.destroy(), self._open_output())
                   ).pack(side='left')
        if report_path and Path(report_path).exists():
            ttk.Button(btn_row, text=self.t('report_open'),
                       command=lambda: self._open_path(report_path)
                       ).pack(side='left', padx=(8, 0))
        ttk.Button(btn_row, text=self.t('summary_close'),
                   command=win.destroy).pack(side='right')

        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{max(0, x)}+{max(0, y)}")
        win.grab_set()

    def _cancel(self):
        if self._compressor:
            self._compressor.cancel()

    def _open_output(self):
        out = Path(self.output_var.get().strip())
        target = out if out.is_dir() else out.parent
        self._open_path(target)

    def _open_path(self, target):
        """Ouvre un fichier ou un dossier avec l'application par défaut de l'OS."""
        target = str(target)
        try:
            if sys.platform == 'win32':
                os.startfile(target)
            elif sys.platform == 'darwin':
                subprocess.run(['open', target])
            else:
                subprocess.run(['xdg-open', target])
        except Exception as e:
            messagebox.showerror(self.t('msg_error_title'), self.t('msg_open_folder_error', e=e))

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
        def _do():
            self.prog_var.set(val)
            self.prog_pct_var.set(f"{val:.0f}%")
        self.root.after(0, _do)

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

    def _show_about(self):
        lib_status = [
            (self.t('lib_pillow'), PIL_AVAILABLE),
            (self.t('lib_vtflib'), VTFLIB_AVAILABLE),
            (self.t('lib_ffmpeg'), FFMPEG_AVAILABLE),
        ]
        libs = "\n".join(
            self.t('about_lib_yes' if ok else 'about_lib_no', lib=name)
            for name, ok in lib_status
        )
        messagebox.showinfo(
            self.t('about_title'),
            self.t('about_body', version=VERSION, libs=libs),
        )

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
            'rem_unused_tex':      self.rem_unused_tex.get(),
            'convert_uncompressed': self.convert_uncompressed.get(),
            'gen_report':          self.gen_report.get(),
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
        self.source_var.set(state.get('source', ''))
        self.output_var.set(state.get('output', ''))
        self.src_type.set(state.get('src_type', 'folder'))
        self.out_fmt.set(state.get('out_fmt', 'folder'))
        self.profile_var.set(self._profile_label(state.get('profile_id', 'custom')))
        self.rem_chands.set(state.get('rem_chands', True))
        self.rem_unused.set(state.get('rem_unused', True))
        self.check_materials.set(state.get('check_materials', True))
        self.rem_unused_tex.set(state.get('rem_unused_tex', False))
        self.convert_uncompressed.set(state.get('convert_uncompressed', True))
        self.gen_report.set(state.get('gen_report', True))
        self.comp_tex.set(state.get('comp_tex', True))
        self.max_res.set(self.t('no_limit') if state.get('max_res_no_limit', False) else state.get('max_res', '1024'))
        self.tex_qual.set(state.get('tex_qual', 85))
        self.gen_lua.set(state.get('gen_lua', True))
        self.lua_chands.set(state.get('lua_chands', True))
        self.comp_snd.set(state.get('comp_snd', False))
        self.snd_qual.set(state.get('snd_qual', '128k'))
        self.zip_lvl.set(state.get('zip_lvl', 6))
        self.dry_run.set(state.get('dry_run', False))
        self.backup.set(state.get('backup', False))
        self.target_size_enabled.set(state.get('target_size_enabled', False))
        self.target_size_mb.set(state.get('target_size_mb', '10'))
        self.batch.set(state.get('batch', False))

        self._toggle_tex()
        self._toggle_snd()
        self._toggle_lua()
        self._toggle_target_size()
        self._scan_source()

    # ── Préférences persistantes ──────────────────────────────────────────────

    @staticmethod
    def _load_config() -> dict | None:
        try:
            return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None

    def _save_config(self):
        try:
            state = self._collect_state()
            state['lang'] = self.lang
            state['theme_name'] = self.theme_name
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(json.dumps(state, indent=2), encoding='utf-8')
        except OSError:
            pass

    def _on_close(self):
        self._save_config()
        self.root.destroy()

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
