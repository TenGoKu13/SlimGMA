import os
import sys
import json
import queue
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

from .deps import PIL_AVAILABLE, SRCTOOLS_AVAILABLE, FFMPEG_AVAILABLE
from .constants import (
    VERSION, LICENSE_NAME, REPO_URL, CONFIG_PATH,
    TEXTURE_EXTENSIONS, SOUND_EXTENSIONS,
)
from .i18n import t
from .changelog import RELEASES, releases_since
from .compressor import Compressor


THEMES = {
    'dark': {
        'BG': '#12141c', 'CARD': '#1b1f2a', 'SIDEBAR': '#0c0e15',
        'BORDER': '#2a3040', 'FG': '#e6e9f0', 'SUB': '#8b93a7',
        'ACCENT': '#6d8cff', 'ACCENT_ACTIVE': '#8aa4ff', 'ON_ACCENT': '#0c0e15',
        'GREEN': '#3ddc97', 'RED': '#ff6b81', 'YELLOW': '#ffc857',
        'LOG_BG': '#0a0c12', 'HOVER': '#232838',
    },
    'light': {
        'BG': '#f5f7fb', 'CARD': '#ffffff', 'SIDEBAR': '#dde3ef',
        'BORDER': '#c9d1e2', 'FG': '#1b2130', 'SUB': '#5f6980',
        'ACCENT': '#3559e0', 'ACCENT_ACTIVE': '#5573e8', 'ON_ACCENT': '#ffffff',
        'GREEN': '#0f9d63', 'RED': '#d92d4b', 'YELLOW': '#a9700a',
        'LOG_BG': '#ffffff', 'HOVER': '#d7dde9',
    },
}

MAX_RECENT_SOURCES = 8
UI_PUMP_MS = 40
SIDEBAR_WIDTH = 186
PAGES = ('source', 'options', 'advanced', 'log', 'report')
PAGE_ICONS = {'source': '📦', 'options': '⚙', 'advanced': '🛠', 'log': '📜',
              'report': '📊'}
ENTRY_TONES = {'new': 'GREEN', 'fix': 'RED', 'change': 'ACCENT'}


class Tooltip:
    def __init__(self, widget, text_fn, bg: str, fg: str, border: str):
        self.widget = widget
        self.text_fn = text_fn
        self.tip = None
        self.after_id = None
        self.bg, self.fg, self.border = bg, fg, border
        widget.bind('<Enter>', self._schedule, add='+')
        widget.bind('<Leave>', self._hide, add='+')
        widget.bind('<ButtonPress>', self._hide, add='+')

    def _schedule(self, _event=None):
        self._cancel()
        self.after_id = self.widget.after(550, self._show)

    def _cancel(self):
        if self.after_id is not None:
            try:
                self.widget.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None

    def _show(self):
        if self.tip is not None:
            return
        text = self.text_fn() if callable(self.text_fn) else self.text_fn
        if not text:
            return
        try:
            x = self.widget.winfo_rootx() + 14
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
            self.tip = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f'+{x}+{y}')
            frame = tk.Frame(tw, bg=self.border, padx=1, pady=1)
            frame.pack()
            tk.Label(frame, text=text, bg=self.bg, fg=self.fg, justify='left',
                     padx=9, pady=6, font=('Segoe UI', 8),
                     wraplength=340).pack()
        except tk.TclError:
            self.tip = None

    def _hide(self, _event=None):
        self._cancel()
        if self.tip is not None:
            try:
                self.tip.destroy()
            except Exception:
                pass
            self.tip = None


class ScrollArea:
    def __init__(self, parent, bg: str):
        self.outer = tk.Frame(parent, bg=bg)
        self.canvas = tk.Canvas(self.outer, bg=bg, highlightthickness=0)
        self.vbar = ttk.Scrollbar(self.outer, orient='vertical',
                                  command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.window = self.canvas.create_window((0, 0), window=self.inner,
                                                anchor='nw')
        self.inner.bind('<Configure>', self._on_inner)
        self.canvas.bind('<Configure>', self._on_canvas)

    def _on_inner(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        self._sync_bar()

    def _on_canvas(self, event):
        self.canvas.itemconfigure(self.window, width=max(60, event.width - 6))
        self._sync_bar()

    def _sync_bar(self):
        try:
            overflow = self.inner.winfo_reqheight() > self.canvas.winfo_height()
        except tk.TclError:
            return
        if overflow and not self.vbar.winfo_ismapped():
            self.vbar.pack(side='right', fill='y')
        elif not overflow and self.vbar.winfo_ismapped():
            self.vbar.pack_forget()
            self.canvas.yview_moveto(0)

    def scroll(self, units: int):
        if self.inner.winfo_reqheight() > self.canvas.winfo_height():
            self.canvas.yview_scroll(units, 'units')


class App:
    PRESETS: dict[str, dict | None] = {
        'custom': None,
        'balanced': {
            'remove_chands': True, 'remove_unused': True, 'compress_textures': True,
            'max_res': '1024', 'quality': 85, 'compress_sounds': False,
            'sound_quality': '128k', 'zip_level': 6, 'dedup': True,
        },
        'quality': {
            'remove_chands': True, 'remove_unused': True, 'compress_textures': True,
            'max_res': 'none', 'quality': 100, 'compress_sounds': False,
            'sound_quality': '320k', 'zip_level': 4, 'dedup': True,
        },
        'minimal': {
            'remove_chands': True, 'remove_unused': True, 'compress_textures': True,
            'max_res': '512', 'quality': 60, 'compress_sounds': True,
            'sound_quality': '96k', 'zip_level': 9, 'dedup': True,
        },
        'share': {
            'remove_chands': True, 'remove_unused': True, 'compress_textures': True,
            'max_res': '256', 'quality': 50, 'compress_sounds': True,
            'sound_quality': '64k', 'zip_level': 9, 'dedup': True,
        },
    }

    STEP_COUNT = Compressor.TOTAL_STEPS

    def __init__(self):
        saved = self._load_config() or {}
        self.lang = saved.get('lang', 'fr')
        self.theme_name = saved.get('theme_name', 'dark')
        self._recent: list[str] = [p for p in saved.get('recent_sources', [])
                                   if isinstance(p, str)][:MAX_RECENT_SOURCES]
        self._apply_palette()

        self.root = TkinterDnD.Tk() if DND_AVAILABLE else tk.Tk()
        self.root.title(f"Compressez PM GMod  v{VERSION}")
        self.root.geometry("1000x760")
        self.root.configure(bg=self.BG)
        self.root.minsize(880, 620)
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

        self._seen_version = saved.get('seen_version',
                                       '0.0.0' if saved else VERSION)
        self._extra_scrolls: dict = {}
        self._ui_queue: queue.SimpleQueue = queue.SimpleQueue()
        self._pump_job = None
        self._compressor: Compressor | None = None
        self._thread: threading.Thread | None = None
        self._log_entries: list[tuple[str, str]] = []
        self._counts = {'warning': 0, 'error': 0}
        self._drop_stats_line = ""
        self._run_started: float | None = None
        self._timer_job = None
        self._page = saved.get('page', 'source')
        self._report_data: dict = {}
        self._log_filter = 'all'
        self._step_state = 0
        self._steps_done = False

        self._setup_styles()
        self._build_ui()
        if saved:
            self._restore_state(saved)
        self._log_header()
        self._bind_shortcuts()
        self._pump_ui()

    def t(self, key: str, **kwargs) -> str:
        return t(key, self.lang, **kwargs)

    def _apply_palette(self):
        for k, v in THEMES[self.theme_name].items():
            setattr(self, k, v)

    def _profile_label(self, pid: str) -> str:
        return self.t(f'profile_{pid}')

    def _ui(self, fn):
        self._ui_queue.put(fn)

    def _pump_ui(self):
        while True:
            try:
                fn = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except tk.TclError:
                pass
        try:
            self._pump_job = self.root.after(UI_PUMP_MS, self._pump_ui)
        except (RuntimeError, tk.TclError):
            self._pump_job = None

    def _stop_pump(self):
        if self._pump_job is not None:
            try:
                self.root.after_cancel(self._pump_job)
            except Exception:
                pass
            self._pump_job = None

    def _tooltip(self, widget, key: str):
        Tooltip(widget, lambda k=key: self.t(k), bg=self.CARD, fg=self.FG,
                border=self.BORDER)

    def _setup_styles(self):
        s = ttk.Style()
        s.theme_use('clam')

        s.configure('.', background=self.BG, foreground=self.FG,
                    bordercolor=self.BORDER, relief='flat', focuscolor=self.ACCENT)
        s.configure('TFrame', background=self.BG)
        s.configure('Card.TFrame', background=self.CARD)
        s.configure('TLabel', background=self.BG, foreground=self.FG)
        s.configure('Card.TLabel', background=self.CARD, foreground=self.FG)
        s.configure('CardSub.TLabel', background=self.CARD, foreground=self.SUB,
                    font=('Segoe UI', 8))
        s.configure('CardTitle.TLabel', background=self.CARD, foreground=self.FG,
                    font=('Segoe UI', 10, 'bold'))
        s.configure('PageTitle.TLabel', background=self.BG, foreground=self.FG,
                    font=('Segoe UI', 16, 'bold'))
        s.configure('PageSub.TLabel', background=self.BG, foreground=self.SUB,
                    font=('Segoe UI', 9))

        s.configure('TCheckbutton', background=self.CARD, foreground=self.FG,
                    indicatorcolor=self.BG, font=('Segoe UI', 9))
        s.map('TCheckbutton',
              background=[('active', self.CARD)],
              indicatorcolor=[('selected', self.ACCENT), ('active', self.HOVER)],
              foreground=[('disabled', self.SUB)])
        s.configure('TRadiobutton', background=self.CARD, foreground=self.FG,
                    indicatorcolor=self.BG, font=('Segoe UI', 9))
        s.map('TRadiobutton',
              background=[('active', self.CARD)],
              indicatorcolor=[('selected', self.ACCENT), ('active', self.HOVER)],
              foreground=[('disabled', self.SUB)])

        s.configure('TEntry', fieldbackground=self.BG, foreground=self.FG,
                    bordercolor=self.BORDER, insertcolor=self.FG,
                    lightcolor=self.BORDER, darkcolor=self.BORDER, padding=5)
        s.map('TEntry', bordercolor=[('focus', self.ACCENT)],
              fieldbackground=[('disabled', self.CARD)],
              foreground=[('disabled', self.SUB)])

        s.configure('TButton', background=self.CARD, foreground=self.FG,
                    bordercolor=self.BORDER, padding=(11, 6),
                    font=('Segoe UI', 9))
        s.map('TButton', background=[('active', self.HOVER),
                                     ('disabled', self.BG)],
              foreground=[('disabled', self.SUB)])
        s.configure('Ghost.TButton', background=self.BG, foreground=self.SUB,
                    bordercolor=self.BG, padding=(9, 5), font=('Segoe UI', 8))
        s.map('Ghost.TButton', background=[('active', self.HOVER)],
              foreground=[('active', self.FG), ('disabled', self.BORDER)])
        s.configure('Accent.TButton', background=self.ACCENT,
                    foreground=self.ON_ACCENT, bordercolor=self.ACCENT,
                    font=('Segoe UI', 10, 'bold'), padding=(22, 8))
        s.map('Accent.TButton',
              background=[('active', self.ACCENT_ACTIVE), ('disabled', self.BORDER)],
              foreground=[('disabled', self.SUB)],
              bordercolor=[('disabled', self.BORDER)])

        s.configure('TCombobox', fieldbackground=self.BG, background=self.BG,
                    foreground=self.FG, bordercolor=self.BORDER,
                    arrowcolor=self.SUB, selectbackground=self.BG,
                    selectforeground=self.FG, padding=4)
        s.map('TCombobox', fieldbackground=[('readonly', self.BG),
                                            ('disabled', self.CARD)],
              bordercolor=[('focus', self.ACCENT)],
              foreground=[('disabled', self.SUB)])

        s.configure('TScale', background=self.CARD, troughcolor=self.BG,
                    bordercolor=self.BORDER)
        s.configure('TProgressbar', background=self.ACCENT, troughcolor=self.BORDER,
                    bordercolor=self.BORDER, thickness=8, lightcolor=self.ACCENT,
                    darkcolor=self.ACCENT)
        s.configure('TSeparator', background=self.BORDER)
        s.configure('Vertical.TScrollbar', background=self.BORDER,
                    troughcolor=self.BG, bordercolor=self.BG,
                    arrowcolor=self.SUB, width=10)
        s.map('Vertical.TScrollbar', background=[('active', self.SUB)])

    def _build_ui(self):
        self._build_header()
        tk.Frame(self.root, bg=self.BORDER, height=1).pack(fill='x')

        body = tk.Frame(self.root, bg=self.BG)
        body.pack(fill='both', expand=True)

        self._build_sidebar(body)
        tk.Frame(body, bg=self.BORDER, width=1).pack(side='left', fill='y')

        self.page_host = tk.Frame(body, bg=self.BG)
        self.page_host.pack(side='left', fill='both', expand=True)

        self.pages: dict[str, tk.Frame] = {}
        self.scrolls: dict[str, ScrollArea] = {}
        self._build_page_source()
        self._build_page_options()
        self._build_page_advanced()
        self._build_page_log()
        self._build_page_report()

        self._build_action_bar()

        self._toggle_tex()
        self._toggle_snd()
        self._toggle_lua()
        self._toggle_target_size()
        self._show_page(self._page)

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=self.SIDEBAR, height=58)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)

        left = tk.Frame(hdr, bg=self.SIDEBAR)
        left.pack(side='left', padx=18)

        tk.Label(left, text="🗜", bg=self.SIDEBAR, fg=self.ACCENT,
                 font=('Segoe UI', 18)).pack(side='left', padx=(0, 10))

        titles = tk.Frame(left, bg=self.SIDEBAR)
        titles.pack(side='left')
        row = tk.Frame(titles, bg=self.SIDEBAR)
        row.pack(anchor='w')
        tk.Label(row, text="Compressez PM GMod", bg=self.SIDEBAR, fg=self.FG,
                 font=('Segoe UI', 13, 'bold')).pack(side='left')
        tk.Label(row, text=f"v{VERSION}", bg=self.SIDEBAR, fg=self.SUB,
                 font=('Segoe UI', 8)).pack(side='left', padx=(8, 0), pady=(4, 0))
        tk.Label(titles, text=self.t('app_tagline'), bg=self.SIDEBAR,
                 fg=self.SUB, font=('Segoe UI', 8)).pack(anchor='w')

        actions = tk.Frame(hdr, bg=self.SIDEBAR)
        actions.pack(side='right', padx=14)

        theme_key = 'btn_theme_light' if self.theme_name == 'dark' else 'btn_theme_dark'
        self.theme_btn = self._header_button(actions, self.t(theme_key),
                                             self._toggle_theme)
        self.lang_btn = self._header_button(
            actions, "EN" if self.lang == 'fr' else "FR", self._toggle_language)
        self._header_button(actions, self.t('btn_about'), self._show_about)
        self.changelog_btn = self._header_button(
            actions, self.t('btn_changelog'), self._show_changelog)
        self._paint_changelog_button()

    def _header_button(self, parent, text: str, command):
        btn = tk.Label(parent, text=text, bg=self.SIDEBAR, fg=self.SUB,
                       font=('Segoe UI', 9), padx=11, pady=5, cursor='hand2')
        btn.pack(side='right', padx=3)
        btn._enabled = True
        btn._idle_fg = self.SUB

        def on_click(_event=None):
            if btn._enabled:
                command()

        btn.bind('<Button-1>', on_click)
        btn.bind('<Enter>', lambda e: btn._enabled and btn.configure(
            bg=self.HOVER, fg=self.FG))
        btn.bind('<Leave>', lambda e: btn.configure(bg=self.SIDEBAR,
                                                    fg=btn._idle_fg))
        return btn

    @staticmethod
    def _set_header_enabled(btn, enabled: bool):
        btn._enabled = enabled
        btn.configure(cursor='hand2' if enabled else 'arrow')

    def _build_sidebar(self, parent):
        bar = tk.Frame(parent, bg=self.SIDEBAR, width=SIDEBAR_WIDTH)
        bar.pack(side='left', fill='y')
        bar.pack_propagate(False)

        tk.Frame(bar, bg=self.SIDEBAR, height=12).pack()

        self._nav: dict[str, tuple] = {}
        for key in PAGES:
            self._build_nav_item(bar, key)

        bottom = tk.Frame(bar, bg=self.SIDEBAR)
        bottom.pack(side='bottom', fill='x', pady=12, padx=14)

        tk.Label(bottom, text=self.t('sidebar_libs'), bg=self.SIDEBAR,
                 fg=self.SUB, font=('Segoe UI', 7, 'bold')).pack(anchor='w')
        for label, ok in (('Pillow', PIL_AVAILABLE), ('srctools', SRCTOOLS_AVAILABLE),
                          ('ffmpeg', FFMPEG_AVAILABLE)):
            row = tk.Frame(bottom, bg=self.SIDEBAR)
            row.pack(anchor='w', fill='x')
            tk.Label(row, text="●", bg=self.SIDEBAR,
                     fg=self.GREEN if ok else self.BORDER,
                     font=('Segoe UI', 7)).pack(side='left')
            tk.Label(row, text=label, bg=self.SIDEBAR, fg=self.SUB,
                     font=('Segoe UI', 8)).pack(side='left', padx=(5, 0))

        tk.Frame(bottom, bg=self.BORDER, height=1).pack(fill='x', pady=9)
        oss = tk.Label(bottom, text=self.t('sidebar_oss'), bg=self.SIDEBAR,
                       fg=self.SUB, font=('Segoe UI', 7), cursor='hand2')
        oss.pack(anchor='w')
        oss.bind('<Button-1>', lambda e: self._open_repo())

    def _build_nav_item(self, parent, key: str):
        row = tk.Frame(parent, bg=self.SIDEBAR, cursor='hand2')
        row.pack(fill='x', padx=9, pady=1)

        marker = tk.Frame(row, bg=self.SIDEBAR, width=3)
        marker.pack(side='left', fill='y')

        label = tk.Label(row, text=f"  {PAGE_ICONS[key]}   {self.t('nav_' + key)}",
                         bg=self.SIDEBAR, fg=self.SUB, font=('Segoe UI', 10),
                         anchor='w', padx=6, pady=8)
        label.pack(side='left', fill='x', expand=True)

        badge = tk.Label(row, text="", bg=self.SIDEBAR, fg=self.SUB,
                         font=('Segoe UI', 8, 'bold'), padx=8)
        badge.pack(side='right')

        for widget in (row, marker, label, badge):
            widget.bind('<Button-1>', lambda e, k=key: self._show_page(k))
            widget.bind('<Enter>', lambda e, k=key: self._nav_hover(k, True))
            widget.bind('<Leave>', lambda e, k=key: self._nav_hover(k, False))

        self._nav[key] = (row, marker, label, badge)

    def _nav_hover(self, key: str, entering: bool):
        if key == self._page:
            return
        row, marker, label, badge = self._nav[key]
        bg = self.HOVER if entering else self.SIDEBAR
        for widget in (row, marker, label, badge):
            widget.configure(bg=bg)
        label.configure(fg=self.FG if entering else self.SUB)

    def _paint_nav(self):
        for key in PAGES:
            row, marker, label, badge = self._nav[key]
            active = key == self._page
            bg = self.BG if active else self.SIDEBAR
            for widget in (row, label, badge):
                widget.configure(bg=bg)
            marker.configure(bg=self.ACCENT if active else bg)
            label.configure(fg=self.FG if active else self.SUB,
                            font=('Segoe UI', 10, 'bold' if active else 'normal'))

    def _show_page(self, key: str):
        if key not in self.pages:
            key = 'source'
        self._page = key
        for name, frame in self.pages.items():
            if name == key:
                frame.pack(fill='both', expand=True)
            else:
                frame.pack_forget()
        self._paint_nav()

    def _page_shell(self, key: str, scrollable: bool = True):
        frame = tk.Frame(self.page_host, bg=self.BG)
        self.pages[key] = frame

        head = tk.Frame(frame, bg=self.BG)
        head.pack(fill='x', padx=22, pady=(18, 2))
        tk.Label(head, text=self.t('nav_' + key), bg=self.BG, fg=self.FG,
                 font=('Segoe UI', 16, 'bold')).pack(anchor='w')
        tk.Label(head, text=self.t('page_' + key + '_sub'), bg=self.BG,
                 fg=self.SUB, font=('Segoe UI', 9)).pack(anchor='w', pady=(1, 0))

        if not scrollable:
            host = tk.Frame(frame, bg=self.BG)
            host.pack(fill='both', expand=True, padx=22, pady=(12, 8))
            return host

        area = ScrollArea(frame, self.BG)
        area.outer.pack(fill='both', expand=True, padx=(22, 8), pady=(12, 8))
        self.scrolls[key] = area
        return area.inner

    def _card(self, parent, title: str, side=None, **pack_kw):
        shell = tk.Frame(parent, bg=self.BORDER, padx=1, pady=1)
        if side:
            shell.pack(side=side, **pack_kw)
        else:
            shell.pack(**pack_kw)
        inner = tk.Frame(shell, bg=self.CARD, padx=16, pady=13)
        inner.pack(fill='both', expand=True)
        if title:
            tk.Label(inner, text=title, bg=self.CARD, fg=self.FG,
                     font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(0, 9))
        return inner

    def _two_columns(self, parent, pady=0):
        cols = tk.Frame(parent, bg=self.BG)
        cols.pack(fill='both', expand=True, pady=pady)
        left = tk.Frame(cols, bg=self.BG)
        right = tk.Frame(cols, bg=self.BG)
        left.grid(row=0, column=0, sticky='new')
        right.grid(row=0, column=1, sticky='new', padx=(14, 0))
        cols.columnconfigure(0, weight=1, uniform='col')
        cols.columnconfigure(1, weight=1, uniform='col')
        return left, right

    def _check(self, parent, chk_key: str, variable, desc_key: str | None = None,
               tip_key: str | None = None, command=None, pady=(0, 8)):
        box = ttk.Checkbutton(parent, text=self.t(chk_key), variable=variable,
                              command=command)
        box.pack(anchor='w')
        if tip_key:
            self._tooltip(box, tip_key)
        if desc_key:
            tk.Label(parent, text=self.t(desc_key).strip(), bg=self.CARD,
                     fg=self.SUB, font=('Segoe UI', 8), justify='left',
                     anchor='w').pack(anchor='w', padx=(20, 0), pady=pady)
        elif pady:
            tk.Frame(parent, bg=self.CARD, height=pady[1]).pack()
        return box

    def _build_page_source(self):
        host = self._page_shell('source')

        card = self._card(host, self.t('card_source'), fill='x')

        self.drop_canvas = tk.Canvas(card, height=104, bg=self.CARD,
                                     highlightthickness=0, cursor='hand2')
        self.drop_canvas.pack(fill='x', pady=(0, 12))
        self.drop_canvas.bind('<Configure>', lambda e: self._draw_drop_zone())
        self.drop_canvas.bind('<Button-1>', lambda e: self._browse_source())
        if DND_AVAILABLE:
            for target in (self.drop_canvas, self.root):
                target.drop_target_register(DND_FILES)
                target.dnd_bind('<<Drop>>', self._on_drop_source)

        row = tk.Frame(card, bg=self.CARD)
        row.pack(fill='x')
        self.source_var = tk.StringVar()
        self.source_var.trace_add('write', lambda *_: self._draw_drop_zone())
        src_entry = ttk.Entry(row, textvariable=self.source_var)
        src_entry.pack(side='left', fill='x', expand=True)
        recent_btn = ttk.Button(row, text="🕘", width=3,
                                command=self._show_recent_menu)
        recent_btn.pack(side='right', padx=(6, 0))
        self._tooltip(recent_btn, 'tip_recent')
        ttk.Button(row, text=self.t('btn_browse'), command=self._browse_source,
                   width=13).pack(side='right', padx=(6, 0))
        if DND_AVAILABLE:
            src_entry.drop_target_register(DND_FILES)
            src_entry.dnd_bind('<<Drop>>', self._on_drop_source)

        types = tk.Frame(card, bg=self.CARD)
        types.pack(fill='x', pady=(11, 0))
        tk.Label(types, text=self.t('label_source_type'), bg=self.CARD,
                 fg=self.SUB, font=('Segoe UI', 8)).pack(side='left', padx=(0, 8))
        self.src_type = tk.StringVar(value='folder')
        ttk.Radiobutton(types, text=self.t('radio_folder'), variable=self.src_type,
                        value='folder').pack(side='left', padx=(0, 14))
        ttk.Radiobutton(types, text=self.t('radio_gma_file'), variable=self.src_type,
                        value='gma').pack(side='left')

        self.stats_var = tk.StringVar(value="")
        tk.Label(card, textvariable=self.stats_var, bg=self.CARD, fg=self.ACCENT,
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(11, 0))

        out_card = self._card(host, self.t('card_output'), fill='x', pady=(14, 0))

        row2 = tk.Frame(out_card, bg=self.CARD)
        row2.pack(fill='x')
        self.output_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.output_var).pack(
            side='left', fill='x', expand=True)
        ttk.Button(row2, text=self.t('btn_browse'), command=self._browse_output,
                   width=13).pack(side='right', padx=(6, 0))

        fmt = tk.Frame(out_card, bg=self.CARD)
        fmt.pack(fill='x', pady=(11, 0))
        tk.Label(fmt, text=self.t('label_output_format'), bg=self.CARD,
                 fg=self.SUB, font=('Segoe UI', 8)).pack(side='left', padx=(0, 8))
        self.out_fmt = tk.StringVar(value='folder')
        for text, value in ((self.t('radio_folder'), 'folder'),
                            (".gma", 'gma'), (".zip", 'zip')):
            ttk.Radiobutton(fmt, text=text, variable=self.out_fmt,
                            value=value).pack(side='left', padx=(0, 14))

    def _draw_drop_zone(self):
        canvas = getattr(self, 'drop_canvas', None)
        if canvas is None:
            return
        canvas.delete('all')
        width = max(canvas.winfo_width(), 80)
        height = 104
        canvas.create_rectangle(2, 2, width - 2, height - 2, dash=(6, 4),
                                outline=self.BORDER, width=1)
        source = self.source_var.get().strip()
        if source:
            name = Path(source).name or source
            canvas.create_text(width / 2, height / 2 - 18, text="📦",
                               fill=self.ACCENT, font=('Segoe UI', 19))
            canvas.create_text(width / 2, height / 2 + 8, text=name,
                               fill=self.FG, font=('Segoe UI', 11, 'bold'))
            canvas.create_text(width / 2, height / 2 + 28,
                               text=self._drop_stats_line or self.t('drop_change_hint'),
                               fill=self.SUB, font=('Segoe UI', 8))
        else:
            title = self.t('drop_title') if DND_AVAILABLE else self.t('drop_title_nodnd')
            canvas.create_text(width / 2, height / 2 - 16, text="⬇",
                               fill=self.SUB, font=('Segoe UI', 19))
            canvas.create_text(width / 2, height / 2 + 9, text=title,
                               fill=self.FG, font=('Segoe UI', 10, 'bold'))
            canvas.create_text(width / 2, height / 2 + 29, text=self.t('drop_or'),
                               fill=self.SUB, font=('Segoe UI', 8))

    def _build_page_options(self):
        host = self._page_shell('options')

        profile = self._card(host, self.t('card_profile'), fill='x')
        prow = tk.Frame(profile, bg=self.CARD)
        prow.pack(fill='x')
        self._profile_label_to_id = {self._profile_label(pid): pid
                                     for pid in self.PRESETS}
        self.profile_var = tk.StringVar(value=self._profile_label('custom'))
        combo = ttk.Combobox(prow, textvariable=self.profile_var, width=28,
                             values=list(self._profile_label_to_id.keys()),
                             state='readonly')
        combo.pack(side='left')
        combo.bind('<<ComboboxSelected>>', self._apply_profile)
        self._tooltip(combo, 'tip_profile')
        tk.Label(prow, text=self.t('profile_hint').strip(), bg=self.CARD,
                 fg=self.SUB, font=('Segoe UI', 8)).pack(side='left', padx=(12, 0))

        left, right = self._two_columns(host, pady=(14, 0))

        clean = self._card(left, self.t('card_cleanup'), fill='x')
        self.rem_chands = tk.BooleanVar(value=True)
        self._check(clean, 'chk_chands', self.rem_chands, 'desc_chands', 'tip_chands')
        self.rem_unused = tk.BooleanVar(value=True)
        self._check(clean, 'chk_unused', self.rem_unused, 'desc_unused', 'tip_unused')
        self.check_materials = tk.BooleanVar(value=True)
        self._check(clean, 'chk_check_materials', self.check_materials,
                    None, 'tip_check_materials')
        self.rem_unused_tex = tk.BooleanVar(value=False)
        self._check(clean, 'chk_remove_unused_tex', self.rem_unused_tex,
                    'desc_remove_unused_tex', 'tip_remove_unused_tex')
        self.dedup_tex = tk.BooleanVar(value=False)
        self._check(clean, 'chk_dedup', self.dedup_tex, 'desc_dedup', 'tip_dedup',
                    pady=(0, 0))

        tex = self._card(right, self.t('card_textures'), fill='x')
        self.comp_tex = tk.BooleanVar(value=True)
        self._check(tex, 'chk_textures', self.comp_tex, None, 'tip_textures',
                    command=self._toggle_tex, pady=(0, 4))

        self.tex_sub = tk.Frame(tex, bg=self.CARD)
        self.tex_sub.pack(fill='x', padx=(20, 0))

        res_row = tk.Frame(self.tex_sub, bg=self.CARD)
        res_row.pack(fill='x', pady=3)
        tk.Label(res_row, text=self.t('label_max_res'), bg=self.CARD, fg=self.FG,
                 font=('Segoe UI', 9), width=15, anchor='w').pack(side='left')
        self.max_res = tk.StringVar(value='1024')
        res_combo = ttk.Combobox(res_row, textvariable=self.max_res, width=14,
                                 values=['256', '512', '1024', '2048',
                                         self.t('no_limit')], state='readonly')
        res_combo.pack(side='left')
        self._tooltip(res_combo, 'tip_max_res')

        qual_row = tk.Frame(self.tex_sub, bg=self.CARD)
        qual_row.pack(fill='x', pady=3)
        tk.Label(qual_row, text=self.t('label_quality'), bg=self.CARD, fg=self.FG,
                 font=('Segoe UI', 9), width=15, anchor='w').pack(side='left')
        self.tex_qual = tk.IntVar(value=85)
        scale = ttk.Scale(qual_row, from_=10, to=100, variable=self.tex_qual,
                          orient='h', length=130)
        scale.pack(side='left')
        self._tooltip(scale, 'tip_quality')
        self.qual_lbl = tk.Label(qual_row, text="85%", bg=self.CARD,
                                 fg=self.ACCENT, font=('Segoe UI', 9, 'bold'),
                                 width=5)
        self.qual_lbl.pack(side='left', padx=(8, 0))
        self.tex_qual.trace_add('write', lambda *_: self.qual_lbl.config(
            text=f"{self.tex_qual.get()}%"))

        if not PIL_AVAILABLE and not SRCTOOLS_AVAILABLE:
            tk.Label(self.tex_sub, text=self.t('pillow_hint'), bg=self.CARD,
                     fg=self.YELLOW, font=('Segoe UI', 8)).pack(anchor='w',
                                                                pady=(5, 0))

        lua = self._card(right, self.t('card_lua'), fill='x', pady=(14, 0))
        self.gen_lua = tk.BooleanVar(value=True)
        self._check(lua, 'chk_lua', self.gen_lua, 'desc_lua', 'tip_lua',
                    command=self._toggle_lua, pady=(0, 6))
        self.lua_sub = tk.Frame(lua, bg=self.CARD)
        self.lua_sub.pack(fill='x', padx=(20, 0))
        self.lua_chands = tk.BooleanVar(value=True)
        box = ttk.Checkbutton(self.lua_sub, text=self.t('chk_lua_chands'),
                              variable=self.lua_chands)
        box.pack(anchor='w')
        self._tooltip(box, 'tip_lua_chands')
        tk.Label(self.lua_sub, text=self.t('desc_lua_chands').strip(),
                 bg=self.CARD, fg=self.SUB, font=('Segoe UI', 8),
                 justify='left').pack(anchor='w', padx=(20, 0))

    def _build_page_advanced(self):
        host = self._page_shell('advanced')

        left, right = self._two_columns(host)

        sound = self._card(left, self.t('card_sounds'), fill='x')
        self.comp_snd = tk.BooleanVar(value=False)
        self._check(sound, 'chk_sounds', self.comp_snd, None, 'tip_sounds',
                    command=self._toggle_snd, pady=(0, 2))
        tk.Label(sound,
                 text=self.t('ffmpeg_ok') if FFMPEG_AVAILABLE
                 else self.t('ffmpeg_missing_lbl'),
                 bg=self.CARD, fg=self.GREEN if FFMPEG_AVAILABLE else self.YELLOW,
                 font=('Segoe UI', 8)).pack(anchor='w', padx=(20, 0), pady=(0, 6))

        self.snd_sub = tk.Frame(sound, bg=self.CARD)
        self.snd_sub.pack(fill='x', padx=(20, 0))
        brow = tk.Frame(self.snd_sub, bg=self.CARD)
        brow.pack(fill='x')
        tk.Label(brow, text=self.t('label_bitrate'), bg=self.CARD, fg=self.FG,
                 font=('Segoe UI', 9), width=11, anchor='w').pack(side='left')
        self.snd_qual = tk.StringVar(value='128k')
        ttk.Combobox(brow, textvariable=self.snd_qual, width=9,
                     values=['64k', '96k', '128k', '192k', '320k'],
                     state='readonly').pack(side='left')

        tk.Frame(sound, bg=self.BORDER, height=1).pack(fill='x', pady=12)
        tk.Label(sound, text=self.t('label_zip_level'), bg=self.CARD, fg=self.FG,
                 font=('Segoe UI', 9)).pack(anchor='w', pady=(0, 5))
        zrow = tk.Frame(sound, bg=self.CARD)
        zrow.pack(fill='x')
        tk.Label(zrow, text=self.t('zip_fast'), bg=self.CARD, fg=self.SUB,
                 font=('Segoe UI', 8)).pack(side='left')
        self.zip_lvl = tk.IntVar(value=6)
        zscale = ttk.Scale(zrow, from_=1, to=9, variable=self.zip_lvl,
                           orient='h', length=120)
        zscale.pack(side='left', padx=8)
        self._tooltip(zscale, 'tip_zip')
        tk.Label(zrow, text=self.t('zip_max'), bg=self.CARD, fg=self.SUB,
                 font=('Segoe UI', 8)).pack(side='left')
        self.zip_lbl = tk.Label(zrow, text="6", bg=self.CARD, fg=self.ACCENT,
                                font=('Segoe UI', 9, 'bold'), width=3)
        self.zip_lbl.pack(side='left', padx=(8, 0))
        self.zip_lvl.trace_add('write', lambda *_: self.zip_lbl.config(
            text=str(int(self.zip_lvl.get()))))

        limits = self._card(left, self.t('card_limits'), fill='x', pady=(14, 0))
        self.target_size_enabled = tk.BooleanVar(value=False)
        trow = tk.Frame(limits, bg=self.CARD)
        trow.pack(anchor='w')
        box = ttk.Checkbutton(trow, text=self.t('chk_target_size'),
                              variable=self.target_size_enabled,
                              command=self._toggle_target_size)
        box.pack(side='left')
        self._tooltip(box, 'tip_target_size')
        self.target_size_mb = tk.StringVar(value='10')
        self.target_size_entry = ttk.Entry(trow, textvariable=self.target_size_mb,
                                           width=7)
        self.target_size_entry.pack(side='left', padx=6)
        tk.Label(trow, text=self.t('label_mb'), bg=self.CARD, fg=self.SUB,
                 font=('Segoe UI', 9)).pack(side='left')
        tk.Label(limits, text=self.t('desc_target_size').strip(), bg=self.CARD,
                 fg=self.SUB, font=('Segoe UI', 8), justify='left').pack(
            anchor='w', padx=(20, 0), pady=(0, 9))

        self.batch = tk.BooleanVar(value=False)
        self._check(limits, 'chk_batch', self.batch, 'desc_batch', 'tip_batch',
                    pady=(0, 0))

        safety = self._card(right, self.t('card_safety'), fill='x')
        self.dry_run = tk.BooleanVar(value=False)
        self._check(safety, 'chk_dry_run', self.dry_run, 'desc_dry_run',
                    'tip_dry_run')
        self.backup = tk.BooleanVar(value=False)
        self._check(safety, 'chk_backup', self.backup, 'desc_backup', 'tip_backup')
        self.convert_uncompressed = tk.BooleanVar(value=True)
        self._check(safety, 'chk_convert', self.convert_uncompressed,
                    'desc_convert', 'tip_convert', pady=(0, 0))

        gma = self._card(right, self.t('card_gma'), fill='x', pady=(14, 0))
        self.strip_whitelist = tk.BooleanVar(value=False)
        self._check(gma, 'chk_strip_whitelist', self.strip_whitelist,
                    'desc_strip_whitelist', 'tip_strip_whitelist', pady=(0, 0))

    def _build_page_log(self):
        host = self._page_shell('log', scrollable=False)

        toolbar = tk.Frame(host, bg=self.BG)
        toolbar.pack(fill='x', pady=(0, 10))

        self.log_filter_var = tk.StringVar(value=self._log_filter)
        self._filter_btns = {}
        segment = tk.Frame(toolbar, bg=self.BORDER, padx=1, pady=1)
        segment.pack(side='left')
        for value, key in (('all', 'log_filter_all'), ('warn', 'log_filter_warn'),
                           ('error', 'log_filter_err')):
            btn = tk.Label(segment, text=self.t(key), bg=self.CARD, fg=self.SUB,
                           font=('Segoe UI', 8), padx=13, pady=5, cursor='hand2')
            btn.pack(side='left')
            btn.bind('<Button-1>', lambda e, v=value: self._set_log_filter(v))
            self._filter_btns[value] = btn

        ttk.Button(toolbar, text=self.t('btn_clear_log'), style='Ghost.TButton',
                   command=self._clear_log).pack(side='right')
        ttk.Button(toolbar, text=self.t('btn_save_log'), style='Ghost.TButton',
                   command=self._save_log).pack(side='right', padx=(0, 6))
        ttk.Button(toolbar, text=self.t('btn_copy_log'), style='Ghost.TButton',
                   command=self._copy_log).pack(side='right', padx=(0, 6))

        shell = tk.Frame(host, bg=self.BORDER, padx=1, pady=1)
        shell.pack(fill='both', expand=True)
        inner = tk.Frame(shell, bg=self.LOG_BG)
        inner.pack(fill='both', expand=True)
        self.log_box = tk.Text(
            inner, bg=self.LOG_BG, fg=self.FG, insertbackground=self.FG,
            font=('Consolas', 9), state='disabled', relief='flat',
            borderwidth=0, highlightthickness=0, padx=12, pady=10, wrap='none',
            selectbackground=self.ACCENT, selectforeground=self.ON_ACCENT,
        )
        log_bar = ttk.Scrollbar(inner, orient='vertical',
                                command=self.log_box.yview)
        self.log_box.configure(yscrollcommand=log_bar.set)
        log_bar.pack(side='right', fill='y')
        self.log_box.pack(side='left', fill='both', expand=True)

        self.log_box.tag_configure('header', foreground=self.ACCENT,
                                   font=('Consolas', 9, 'bold'))
        self.log_box.tag_configure('success', foreground=self.GREEN)
        self.log_box.tag_configure('warning', foreground=self.YELLOW)
        self.log_box.tag_configure('error', foreground=self.RED)
        self.log_box.tag_configure('info', foreground=self.FG)
        self._paint_log_filter()

    def _build_page_report(self):
        host = self._page_shell('report')
        self.report_host = tk.Frame(host, bg=self.BG)
        self.report_host.pack(fill='both', expand=True)
        self._render_report(self._report_data)

    def _render_report(self, report: dict | None):
        self._report_data = report or {}
        host = getattr(self, 'report_host', None)
        if host is None:
            return
        for child in host.winfo_children():
            child.destroy()

        if not self._report_data:
            self._report_placeholder(host)
            return

        data = self._report_data
        card = self._card(host, self.t('report_for_addon',
                                       name=data.get('addon', '—')), fill='x')
        tiles = tk.Frame(card, bg=self.CARD)
        tiles.pack(fill='x')
        summary = data.get('summary', {})
        delta = summary.get('reduction', '—')
        delta_tone = self.GREEN if delta.startswith('-') else (
            self.YELLOW if delta.startswith('+') else self.FG)
        cells = (
            (self.t('report_sum_original'), summary.get('original', '—'), self.FG),
            (self.t('report_sum_final'), summary.get('final', '—'), self.FG),
            (self.t('report_sum_saved'), delta, delta_tone),
            (self.t('report_sum_files'), summary.get('files', '—'), self.FG),
        )
        for column, (label, value, tone) in enumerate(cells):
            cell = tk.Frame(tiles, bg=self.CARD)
            cell.grid(row=0, column=column, sticky='w')
            tiles.columnconfigure(column, weight=1, uniform='tile')
            tk.Label(cell, text=label.upper(), bg=self.CARD, fg=self.SUB,
                     font=('Segoe UI', 7, 'bold')).pack(anchor='w')
            tk.Label(cell, text=value, bg=self.CARD, fg=tone,
                     font=('Segoe UI', 15, 'bold')).pack(anchor='w')

        batch = data.get('batch', [])
        if batch:
            section = self._report_section(host, self.t('report_sec_batch'),
                                           len(batch))
            for entry in batch:
                row = tk.Frame(section, bg=self.CARD)
                row.pack(fill='x', pady=1)
                tk.Label(row, text=entry['name'], bg=self.CARD, fg=self.FG,
                         font=('Segoe UI', 9), anchor='w',
                         width=28).pack(side='left')
                tk.Label(row, text=entry['size'], bg=self.CARD, fg=self.SUB,
                         font=('Consolas', 8), anchor='w',
                         width=12).pack(side='left')
                delta = entry['delta']
                tk.Label(row, text=delta, bg=self.CARD,
                         fg=self.GREEN if delta.startswith('-') else self.YELLOW,
                         font=('Segoe UI', 9, 'bold'),
                         anchor='w').pack(side='left')

        roles = data.get('roles', [])
        if roles:
            section = self._report_section(host, self.t('report_sec_roles'),
                                           sum(len(i) for _, i in roles))
            for role, items in roles:
                self._report_group(section, self.t(role), items)

        orphans = data.get('orphans', [])
        if orphans:
            section = self._report_section(host, self.t('report_sec_orphans'),
                                           len(orphans))
            badge = (self.t('report_removed_badge') if data.get('removed')
                     else self.t('report_kept_badge'))
            tone = self.RED if data.get('removed') else self.YELLOW
            strip = tk.Frame(section, bg=self.CARD)
            strip.pack(anchor='w', pady=(0, 6))
            self._pill(strip, badge, tone)
            self._report_paths(section, orphans)

        duplicates = data.get('duplicates', [])
        if duplicates:
            section = self._report_section(host, self.t('report_sec_dups'),
                                           len(duplicates))
            for group in duplicates:
                self._report_group(
                    section, self.t('report_dup_group', n=len(group)), group)

        audit = data.get('audit', [])
        if audit:
            section = self._report_section(host, self.t('report_sec_audit'),
                                           len(audit))
            for issue in audit:
                row = tk.Frame(section, bg=self.CARD)
                row.pack(fill='x', pady=1)
                tk.Label(row, text=self._audit_label(issue['issue']),
                         bg=self.YELLOW,
                         fg=self.ON_ACCENT, font=('Segoe UI', 7, 'bold'),
                         padx=6, width=17).pack(side='left', anchor='n')
                tk.Label(row, text=issue['detail'], bg=self.CARD, fg=self.SUB,
                         font=('Consolas', 8), width=21,
                         anchor='w').pack(side='left', padx=(10, 6))
                tk.Label(row, text=issue['path'], bg=self.CARD, fg=self.FG,
                         font=('Consolas', 8), anchor='w').pack(side='left')

        if not (batch or roles or orphans or duplicates or audit):
            empty = self._card(host, "", fill='x', pady=(14, 0))
            tk.Label(empty, text=self.t('report_empty'), bg=self.CARD,
                     fg=self.SUB, font=('Segoe UI', 9)).pack(anchor='w')

        footer = tk.Frame(host, bg=self.BG)
        footer.pack(fill='x', pady=(14, 0))
        ttk.Button(footer, text=self.t('report_copy'), style='Ghost.TButton',
                   command=self._copy_report).pack(side='left')

    def _audit_label(self, issue: str) -> str:
        return self.t('report_' + issue)

    def _report_placeholder(self, host):
        card = self._card(host, "", fill='x')
        tk.Label(card, text="📊", bg=self.CARD, fg=self.BORDER,
                 font=('Segoe UI', 26)).pack(pady=(14, 6))
        tk.Label(card, text=self.t('report_waiting'), bg=self.CARD, fg=self.FG,
                 font=('Segoe UI', 11, 'bold')).pack()
        tk.Label(card, text=self.t('report_waiting_hint'), bg=self.CARD,
                 fg=self.SUB, font=('Segoe UI', 9), justify='center',
                 wraplength=420).pack(pady=(4, 4))
        if not self.check_materials.get():
            tk.Label(card, text=self.t('report_needs_check'), bg=self.CARD,
                     fg=self.YELLOW, font=('Segoe UI', 8), justify='center',
                     wraplength=420).pack(pady=(6, 14))
        else:
            tk.Frame(card, bg=self.CARD, height=14).pack()

    def _report_section(self, host, title: str, count: int):
        card = self._card(host, "", fill='x', pady=(14, 0))
        head = tk.Frame(card, bg=self.CARD)
        head.pack(fill='x', pady=(0, 8))
        tk.Label(head, text=title, bg=self.CARD, fg=self.FG,
                 font=('Segoe UI', 10, 'bold')).pack(side='left')
        tk.Label(head, text=str(count), bg=self.ACCENT, fg=self.ON_ACCENT,
                 font=('Segoe UI', 7, 'bold'), padx=7).pack(side='left',
                                                            padx=(8, 0))
        return card

    def _report_group(self, parent, title: str, items: list):
        holder = tk.Frame(parent, bg=self.CARD)
        holder.pack(fill='x', pady=1)

        head = tk.Frame(holder, bg=self.CARD, cursor='hand2')
        head.pack(fill='x')
        arrow = tk.Label(head, text="▸", bg=self.CARD, fg=self.SUB,
                         font=('Segoe UI', 8))
        arrow.pack(side='left')
        tk.Label(head, text=f"{title}  ({len(items)})", bg=self.CARD,
                 fg=self.FG, font=('Segoe UI', 9)).pack(side='left', padx=(5, 0))

        body = tk.Frame(holder, bg=self.CARD)

        def toggle(_event=None):
            if body.winfo_ismapped():
                body.pack_forget()
                arrow.configure(text="▸")
            else:
                body.pack(fill='x', padx=(16, 0), pady=(2, 4))
                arrow.configure(text="▾")

        for widget in (head, arrow) + tuple(head.winfo_children()):
            widget.bind('<Button-1>', toggle)

        self._report_paths(body, items)
        return holder

    def _report_paths(self, parent, items: list):
        for path in items:
            tk.Label(parent, text=path, bg=self.CARD, fg=self.SUB,
                     font=('Consolas', 8), anchor='w').pack(anchor='w')

    def _report_text(self) -> str:
        data = self._report_data
        if not data:
            return ""
        lines = [self.t('report_for_addon', name=data.get('addon', '—')), ""]
        summary = data.get('summary', {})
        for key, value in (('report_sum_original', summary.get('original')),
                           ('report_sum_final', summary.get('final')),
                           ('report_sum_saved', summary.get('reduction')),
                           ('report_sum_files', summary.get('files'))):
            lines.append(f"{self.t(key)} : {value}")

        for title, entries in ((self.t('report_sec_batch'),
                                [f"{e['name']} — {e['size']} ({e['delta']})"
                                 for e in data.get('batch', [])]),
                               (self.t('report_sec_roles'),
                                [f"{self.t(role)} ({len(items)})"
                                 for role, items in data.get('roles', [])]),
                               (self.t('report_sec_orphans'),
                                list(data.get('orphans', []))),
                               (self.t('report_sec_dups'),
                                [" | ".join(g) for g in data.get('duplicates', [])]),
                               (self.t('report_sec_audit'),
                                [f"{self._audit_label(i['issue'])} — "
                                 f"{i['detail']} — {i['path']}"
                                 for i in data.get('audit', [])])):
            if entries:
                lines += ["", f"── {title} ──"] + [f"  {e}" for e in entries]
        return "\n".join(lines)

    def _copy_report(self):
        text = self._report_text()
        if not text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._set_status(self.t('report_copied'))

    def _build_action_bar(self):
        tk.Frame(self.root, bg=self.BORDER, height=1).pack(side='bottom', fill='x')
        bar = tk.Frame(self.root, bg=self.SIDEBAR)
        bar.pack(side='bottom', fill='x')

        self.pipe_canvas = tk.Canvas(bar, height=52, bg=self.SIDEBAR,
                                     highlightthickness=0)
        self.pipe_canvas.pack(fill='x', padx=20, pady=(10, 0))
        self.pipe_canvas.bind('<Configure>', lambda e: self._draw_pipeline())

        status = tk.Frame(bar, bg=self.SIDEBAR)
        status.pack(fill='x', padx=20, pady=(2, 0))

        self.status_dot_lbl = tk.Label(status, text="●", bg=self.SIDEBAR,
                                       fg=self.SUB, font=('Segoe UI', 9))
        self.status_dot_lbl.pack(side='left', padx=(0, 6))
        self.status_var = tk.StringVar(value=self.t('status_ready'))
        tk.Label(status, textvariable=self.status_var, bg=self.SIDEBAR,
                 fg=self.FG, font=('Segoe UI', 9)).pack(side='left')
        self.elapsed_var = tk.StringVar(value="")
        tk.Label(status, textvariable=self.elapsed_var, bg=self.SIDEBAR,
                 fg=self.SUB, font=('Segoe UI', 8)).pack(side='left', padx=(12, 0))
        self.file_var = tk.StringVar(value="")
        tk.Label(status, textvariable=self.file_var, bg=self.SIDEBAR,
                 fg=self.SUB, font=('Consolas', 8)).pack(side='right')

        controls = tk.Frame(bar, bg=self.SIDEBAR)
        controls.pack(fill='x', padx=20, pady=(7, 14))

        self.prog_var = tk.DoubleVar(value=0)
        ttk.Progressbar(controls, variable=self.prog_var, maximum=100).pack(
            side='left', fill='x', expand=True, pady=(0, 1))
        self.prog_pct_var = tk.StringVar(value="0%")
        tk.Label(controls, textvariable=self.prog_pct_var, bg=self.SIDEBAR,
                 fg=self.ACCENT, font=('Segoe UI', 9, 'bold'), width=5,
                 anchor='e').pack(side='left', padx=(10, 18))

        self.run_btn = ttk.Button(controls, text=self.t('btn_run'),
                                  command=self._start, style='Accent.TButton')
        self.run_btn.pack(side='right')
        self.stop_btn = ttk.Button(controls, text=self.t('btn_cancel'),
                                   command=self._cancel, state='disabled')
        self.stop_btn.pack(side='right', padx=(0, 8))
        self.report_btn = ttk.Button(controls, text=self.t('report_show'),
                                     style='Ghost.TButton',
                                     command=lambda: self._show_page('report'),
                                     state='disabled')
        self.report_btn.pack(side='right', padx=(0, 8))
        self.open_btn = ttk.Button(controls, text=self.t('btn_open_output'),
                                   style='Ghost.TButton',
                                   command=self._open_output, state='disabled')
        self.open_btn.pack(side='right', padx=(0, 6))

        tk.Label(bar, text=self.t('shortcuts_hint'), bg=self.SIDEBAR, fg=self.SUB,
                 font=('Segoe UI', 7)).pack(side='bottom', anchor='w',
                                            padx=20, pady=(0, 6))

    def _draw_pipeline(self):
        canvas = getattr(self, 'pipe_canvas', None)
        if canvas is None:
            return
        canvas.delete('all')
        width = max(canvas.winfo_width(), 120)
        count = self.STEP_COUNT
        slot = width / count
        cy, radius = 14, 10

        for i in range(1, count + 1):
            cx = slot * (i - 0.5)
            done = self._steps_done or i < self._step_state
            current = not self._steps_done and i == self._step_state

            if i < count:
                canvas.create_line(cx + radius + 3, cy, cx + slot - radius - 3, cy,
                                   fill=self.GREEN if done else self.BORDER,
                                   width=2)

            if done:
                fill, outline, text, text_fill = (self.GREEN, self.GREEN, "✓",
                                                  self.ON_ACCENT)
            elif current:
                fill, outline, text, text_fill = (self.ACCENT, self.ACCENT, str(i),
                                                  self.ON_ACCENT)
            else:
                fill, outline, text, text_fill = (self.SIDEBAR, self.BORDER,
                                                  str(i), self.SUB)

            canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                               fill=fill, outline=outline, width=2)
            canvas.create_text(cx, cy, text=text, fill=text_fill,
                               font=('Segoe UI', 8, 'bold'))
            canvas.create_text(cx, cy + radius + 12,
                               text=self.t(f'step_chip_{i}'),
                               fill=self.FG if (done or current) else self.SUB,
                               font=('Segoe UI', 8,
                                     'bold' if current else 'normal'))

    def _reset_steps(self):
        self._step_state = 0
        self._steps_done = False
        self._draw_pipeline()

    def _set_step(self, n: int):
        def apply():
            self._step_state = n
            self._steps_done = False
            self._draw_pipeline()
        self._ui(apply)

    def _finish_steps(self, success: bool):
        if success:
            self._steps_done = True
            self._draw_pipeline()

    def _bind_shortcuts(self):
        self.root.bind('<Control-o>', lambda e: self._browse_source())
        self.root.bind('<Control-Return>', lambda e: self._start_if_idle())
        self.root.bind('<Escape>', lambda e: self._cancel_if_running())
        self.root.bind_all('<MouseWheel>', self._on_wheel)
        self.root.bind_all('<Button-4>', self._on_wheel)
        self.root.bind_all('<Button-5>', self._on_wheel)

    def _on_wheel(self, event):
        widget = getattr(event, 'widget', None)
        try:
            top = widget.winfo_toplevel() if widget else None
        except (AttributeError, tk.TclError):
            top = None
        if top is not None and top is not self.root:
            area = self._extra_scrolls.get(top)
        else:
            area = self.scrolls.get(self._page)
        if area is None:
            return
        num = getattr(event, 'num', None)
        if num == 4:
            units = -1
        elif num == 5:
            units = 1
        else:
            units = -1 if getattr(event, 'delta', 0) > 0 else 1
        area.scroll(units)

    def _start_if_idle(self):
        if str(self.run_btn['state']) != 'disabled':
            self._start()

    def _cancel_if_running(self):
        if str(self.stop_btn['state']) != 'disabled':
            self._cancel()

    def _toggle_tex(self):
        self._set_sub_state(self.tex_sub, self.comp_tex.get())

    def _toggle_snd(self):
        self._set_sub_state(self.snd_sub, self.comp_snd.get())

    def _toggle_lua(self):
        self._set_sub_state(self.lua_sub, self.gen_lua.get())

    def _toggle_target_size(self):
        self.target_size_entry.configure(
            state='normal' if self.target_size_enabled.get() else 'disabled')

    def _set_sub_state(self, frame, enabled: bool):
        state = 'normal' if enabled else 'disabled'
        color = self.FG if enabled else self.SUB

        def walk(widget):
            for child in widget.winfo_children():
                try:
                    if isinstance(child, tk.Label):
                        child.configure(fg=color)
                    else:
                        child.configure(state=state)
                except tk.TclError:
                    pass
                walk(child)

        walk(frame)

    def _apply_profile(self, _event=None):
        preset = self.PRESETS.get(
            self._profile_label_to_id.get(self.profile_var.get()))
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
        self.dedup_tex.set(preset.get('dedup', False))
        self._toggle_tex()
        self._toggle_snd()
        self._toggle_lua()

    def _scan_source(self):
        source = self.source_var.get().strip()
        if not source or not Path(source).exists():
            self.stats_var.set("")
            self._drop_stats_line = ""
            self._draw_drop_zone()
            return
        self.stats_var.set(self.t('stats_analyzing'))
        threading.Thread(target=self._scan_source_thread, args=(source,),
                         daemon=True).start()

    def _scan_source_thread(self, source: str):
        try:
            path = Path(source)
            if path.is_file():
                text = self.t('stats_source_file',
                              size=Compressor._fmt_size(path.stat().st_size))
                detail = ""
            else:
                count = total = tex = snd = mdl = 0
                for entry in path.rglob('*'):
                    if not entry.is_file():
                        continue
                    count += 1
                    total += entry.stat().st_size
                    ext = entry.suffix.lower()
                    if ext in TEXTURE_EXTENSIONS:
                        tex += 1
                    elif ext in SOUND_EXTENSIONS:
                        snd += 1
                    elif ext == '.mdl':
                        mdl += 1
                text = self.t('stats_source', count=count,
                              size=Compressor._fmt_size(total))
                detail = self.t('stats_breakdown', tex=tex, snd=snd, mdl=mdl)
        except OSError:
            text, detail = "", ""

        def apply():
            self.stats_var.set(text)
            self._drop_stats_line = detail
            self._draw_drop_zone()

        self._ui(apply)

    def _browse_source(self):
        if self.src_type.get() == 'gma':
            path = filedialog.askopenfilename(
                title=self.t('dialog_select_gma'),
                filetypes=[(self.t('filetype_gma'), "*.gma"),
                           (self.t('filetype_all'), "*.*")],
            )
        else:
            path = filedialog.askdirectory(title=self.t('dialog_select_folder'))
        if path:
            self._set_source(path)

    def _set_source(self, path: str):
        self.source_var.set(path)
        entry = Path(path)
        if entry.suffix.lower() == '.gma':
            self.src_type.set('gma')
        elif entry.is_dir():
            self.src_type.set('folder')
        if not self.output_var.get():
            self.output_var.set(str(entry.parent / (entry.stem + '_compressed')))
        self._push_recent(path)
        self._scan_source()

    def _push_recent(self, path: str):
        self._recent = ([path] + [p for p in self._recent if p != path])[
            :MAX_RECENT_SOURCES]

    def _show_recent_menu(self):
        menu = tk.Menu(self.root, tearoff=0, bg=self.CARD, fg=self.FG,
                       activebackground=self.ACCENT,
                       activeforeground=self.ON_ACCENT,
                       borderwidth=0, font=('Segoe UI', 9))
        if not self._recent:
            menu.add_command(label=self.t('no_recent'), state='disabled')
        else:
            for path in self._recent:
                label = path if len(path) <= 60 else '…' + path[-59:]
                menu.add_command(label=label,
                                 command=lambda p=path: self._set_source(p))
        try:
            menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
        finally:
            menu.grab_release()

    def _browse_output(self):
        fmt = self.out_fmt.get()
        if fmt == 'folder':
            path = filedialog.askdirectory(title=self.t('dialog_output_folder'))
        elif fmt == 'gma':
            path = filedialog.asksaveasfilename(
                title=self.t('dialog_save_gma'), defaultextension='.gma',
                filetypes=[(self.t('filetype_gma'), "*.gma")])
        else:
            path = filedialog.asksaveasfilename(
                title=self.t('dialog_save_zip'), defaultextension='.zip',
                filetypes=[(self.t('filetype_zip'), "*.zip")])
        if path:
            self.output_var.set(path)

    def _start(self):
        source = self.source_var.get().strip()
        output = self.output_var.get().strip()

        if not source:
            self._show_page('source')
            messagebox.showwarning(self.t('msg_source_missing_title'),
                                   self.t('msg_source_missing_body'))
            return
        if not output:
            self._show_page('source')
            messagebox.showwarning(self.t('msg_output_missing_title'),
                                   self.t('msg_output_missing_body'))
            return
        if not Path(source).exists():
            self._show_page('source')
            messagebox.showerror(self.t('msg_source_not_found_title'),
                                 self.t('msg_source_not_found_body', src=source))
            return

        target_size_mb = None
        if self.target_size_enabled.get():
            try:
                target_size_mb = float(self.target_size_mb.get().replace(',', '.'))
            except ValueError:
                self._show_page('advanced')
                messagebox.showwarning(self.t('msg_invalid_target_size_title'),
                                       self.t('msg_invalid_target_size_body'))
                return

        self._push_recent(source)

        opts = {
            'source':            source,
            'output':            output,
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
            'dedup_textures':    self.dedup_tex.get(),
            'strip_non_whitelisted': self.strip_whitelist.get(),
            'convert_uncompressed': self.convert_uncompressed.get(),
            'target_size_mb':    target_size_mb,
            'dry_run':           self.dry_run.get(),
            'backup_original':   self.backup.get(),
            'batch':             self.batch.get(),
            'lang':              self.lang,
        }

        self.run_btn.configure(state='disabled')
        self.stop_btn.configure(state='normal')
        self.open_btn.configure(state='disabled')
        self.report_btn.configure(state='disabled')
        self._set_header_enabled(self.theme_btn, False)
        self._set_header_enabled(self.lang_btn, False)
        self.prog_var.set(0)
        self.prog_pct_var.set("0%")
        self.file_var.set("")
        self.status_dot_lbl.configure(fg=self.ACCENT)
        self._counts = {'warning': 0, 'error': 0}
        self._paint_nav_badge()
        self._reset_steps()
        self._show_page('log')
        self._run_started = time.time()
        self._tick_elapsed()

        self._compressor = Compressor(
            opts,
            log_fn=self._log,
            progress_fn=self._set_prog,
            status_fn=self._set_status,
            current_file_fn=self._set_current_file,
            step_fn=self._set_step,
        )
        self._thread = threading.Thread(target=self._run_compressor, daemon=True)
        self._thread.start()

    def _run_compressor(self):
        self._compressor.run()
        self._ui(self._on_done)

    def _tick_elapsed(self):
        if self._run_started is None:
            return
        mins, secs = divmod(int(time.time() - self._run_started), 60)
        self.elapsed_var.set(f"⏱ {mins:02d}:{secs:02d}")
        self._timer_job = self.root.after(500, self._tick_elapsed)

    def _stop_timer(self):
        if self._timer_job is not None:
            try:
                self.root.after_cancel(self._timer_job)
            except Exception:
                pass
            self._timer_job = None

    def _elapsed_str(self) -> str:
        if self._run_started is None:
            return ""
        mins, secs = divmod(int(time.time() - self._run_started), 60)
        return f"{mins:02d}:{secs:02d}"

    def _on_done(self):
        elapsed = self._elapsed_str()
        self._stop_timer()
        self._run_started = None
        self.run_btn.configure(state='normal')
        self.stop_btn.configure(state='disabled')
        self._set_header_enabled(self.theme_btn, True)
        self._set_header_enabled(self.lang_btn, True)
        self.file_var.set("")
        comp = self._compressor
        if comp and comp.final_size is not None:
            self.open_btn.configure(state='normal')
            self._render_report(comp.report)
            if comp.report:
                self.report_btn.configure(state='normal')
            before = Compressor._fmt_size(comp.original_size)
            after = Compressor._fmt_size(comp.final_size)
            self.stats_var.set(self.t('stats_done', before=before, after=after,
                                      delta=self._delta_label(comp.reduction)))
            self.status_dot_lbl.configure(fg=self.GREEN)
            self._finish_steps(True)
            self._show_summary(comp, before, after, elapsed)
        elif comp and comp.cancel_flag.is_set():
            self.status_dot_lbl.configure(fg=self.YELLOW)
        else:
            self.status_dot_lbl.configure(fg=self.RED)

    @staticmethod
    def _delta_label(reduction: float | None) -> str:
        if reduction is None:
            return "—"
        sign = '-' if reduction >= 0 else '+'
        return f"{sign}{abs(reduction):.1f}%"

    def _dialog(self, title: str, width: int | None = None):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.configure(bg=self.BG)
        win.transient(self.root)
        win.resizable(False, False)
        wrap = tk.Frame(win, bg=self.BG, padx=26, pady=22)
        wrap.pack(fill='both', expand=True)
        if width:
            wrap.configure(width=width)
        return win, wrap

    def _center_dialog(self, win):
        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{max(0, x)}+{max(0, y)}")
        win.grab_set()

    def _show_summary(self, comp: 'Compressor', before: str, after: str,
                      elapsed: str):
        saved = Compressor._fmt_size(
            max(0, (comp.original_size or 0) - (comp.final_size or 0)))
        shrank = (comp.reduction or 0) >= 0
        delta = self._delta_label(comp.reduction)
        body = self.t('summary_body', before=before, after=after, saved=saved,
                      delta=delta)
        if elapsed:
            body += "\n" + self.t('summary_elapsed', dur=elapsed)
        dry_run = bool(comp.opts.get('dry_run'))
        if dry_run:
            body += "\n\n" + self.t('summary_dry_run')

        win, wrap = self._dialog(self.t('summary_title'))

        tk.Label(wrap, text=self.t('summary_title'), bg=self.BG, fg=self.FG,
                 font=('Segoe UI', 15, 'bold')).pack(anchor='w')

        bar_w, bar_h, row_h = 300, 15, 27
        original = max(1, comp.original_size or 1)
        ratio = min(1.0, max(0.02, (comp.final_size or 0) / original))
        canvas = tk.Canvas(wrap, width=bar_w + 150, height=row_h * 2 + 8,
                           bg=self.BG, highlightthickness=0)
        canvas.pack(anchor='w', pady=(16, 6))
        canvas.create_rectangle(0, 4, bar_w, 4 + bar_h, fill=self.BORDER,
                                outline='')
        canvas.create_text(bar_w + 10, 4 + bar_h / 2, anchor='w', text=before,
                           fill=self.SUB, font=('Segoe UI', 8))
        y2 = row_h + 6
        tone = self.GREEN if shrank else self.YELLOW
        canvas.create_rectangle(0, y2, bar_w * ratio, y2 + bar_h, fill=tone,
                                outline='')
        canvas.create_text(bar_w + 10, y2 + bar_h / 2, anchor='w',
                           text=f"{after}  ({delta})", fill=tone,
                           font=('Segoe UI', 8, 'bold'))

        tk.Label(wrap, text=body, bg=self.BG, fg=self.FG, justify='left',
                 font=('Segoe UI', 10)).pack(anchor='w', pady=(8, 18))

        row = tk.Frame(wrap, bg=self.BG)
        row.pack(fill='x')
        if not dry_run:
            ttk.Button(row, text=self.t('summary_open_folder'),
                       style='Accent.TButton',
                       command=lambda: (win.destroy(), self._open_output())).pack(
                side='left')
        if comp.report:
            ttk.Button(row, text=self.t('report_show'),
                       style='TButton' if not dry_run else 'Accent.TButton',
                       command=lambda: (win.destroy(),
                                        self._show_page('report'))).pack(
                side='left', padx=(0 if dry_run else 8, 0))
        ttk.Button(row, text=self.t('summary_close'), command=win.destroy).pack(
            side='right')

        self._center_dialog(win)

    def _show_about(self):
        win, wrap = self._dialog(self.t('about_title'))

        head = tk.Frame(wrap, bg=self.BG)
        head.pack(anchor='w')
        tk.Label(head, text="🗜", bg=self.BG, fg=self.ACCENT,
                 font=('Segoe UI', 22)).pack(side='left', padx=(0, 12))
        titles = tk.Frame(head, bg=self.BG)
        titles.pack(side='left')
        tk.Label(titles, text="Compressez PM GMod", bg=self.BG, fg=self.FG,
                 font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        tk.Label(titles, text=f"v{VERSION}  ·  {self.t('sidebar_oss')}",
                 bg=self.BG, fg=self.SUB, font=('Segoe UI', 9)).pack(anchor='w')

        tk.Label(wrap, text=self.t('about_intro'), bg=self.BG, fg=self.FG,
                 justify='left', font=('Segoe UI', 9)).pack(anchor='w',
                                                            pady=(16, 12))

        link = tk.Label(wrap, text=REPO_URL, bg=self.BG, fg=self.ACCENT,
                        font=('Segoe UI', 9, 'underline'), cursor='hand2')
        link.pack(anchor='w')
        link.bind('<Button-1>', lambda e: self._open_repo())

        tk.Frame(wrap, bg=self.BORDER, height=1).pack(fill='x', pady=14)

        tk.Label(wrap, text=self.t('sidebar_libs'), bg=self.BG, fg=self.SUB,
                 font=('Segoe UI', 8, 'bold')).pack(anchor='w')
        for name, ok in ((self.t('lib_pillow'), PIL_AVAILABLE),
                         (self.t('lib_srctools'), SRCTOOLS_AVAILABLE),
                         (self.t('lib_ffmpeg'), FFMPEG_AVAILABLE)):
            tk.Label(wrap, text=f"{'✓' if ok else '✗'}  {name}", bg=self.BG,
                     fg=self.GREEN if ok else self.SUB,
                     font=('Segoe UI', 9)).pack(anchor='w')

        ttk.Button(wrap, text=self.t('summary_close'), command=win.destroy).pack(
            anchor='e', pady=(18, 0))
        self._center_dialog(win)

    def _has_unseen_release(self) -> bool:
        return bool(releases_since(self._seen_version))

    def _paint_changelog_button(self):
        unseen = self._has_unseen_release()
        label = self.t('btn_changelog') + (" •" if unseen else "")
        self.changelog_btn._idle_fg = self.ACCENT if unseen else self.SUB
        self.changelog_btn.configure(text=label,
                                     fg=self.changelog_btn._idle_fg)

    def _show_changelog(self):
        unseen = {r['version'] for r in releases_since(self._seen_version)}
        self._seen_version = VERSION
        self._paint_changelog_button()

        win = tk.Toplevel(self.root)
        win.title(self.t('changelog_title'))
        win.configure(bg=self.BG)
        win.transient(self.root)
        win.geometry("640x580")
        win.minsize(480, 360)

        head = tk.Frame(win, bg=self.SIDEBAR, padx=22, pady=14)
        head.pack(fill='x')
        tk.Label(head, text=self.t('changelog_title'), bg=self.SIDEBAR,
                 fg=self.FG, font=('Segoe UI', 15, 'bold')).pack(anchor='w')
        tk.Label(head, text=self.t('changelog_sub'), bg=self.SIDEBAR,
                 fg=self.SUB, font=('Segoe UI', 9)).pack(anchor='w')
        tk.Frame(win, bg=self.BORDER, height=1).pack(fill='x')

        area = ScrollArea(win, self.BG)
        area.outer.pack(fill='both', expand=True, padx=(20, 6), pady=14)
        self._extra_scrolls[win] = area

        for release in RELEASES:
            self._render_release(area.inner, release,
                                 release['version'] in unseen)

        tk.Frame(win, bg=self.BORDER, height=1).pack(fill='x')
        footer = tk.Frame(win, bg=self.SIDEBAR, padx=20, pady=12)
        footer.pack(fill='x')
        link = tk.Label(footer, text=self.t('changelog_full'), bg=self.SIDEBAR,
                        fg=self.ACCENT, font=('Segoe UI', 9, 'underline'),
                        cursor='hand2')
        link.pack(side='left')
        link.bind('<Button-1>',
                  lambda e: self._open_url(REPO_URL + '/blob/main/CHANGELOG.md'))
        ttk.Button(footer, text=self.t('summary_close'),
                   command=win.destroy).pack(side='right')

        def on_destroy(event):
            if event.widget is win:
                self._extra_scrolls.pop(win, None)

        win.bind('<Destroy>', on_destroy)
        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _render_release(self, parent, release: dict, highlight: bool):
        block = tk.Frame(parent, bg=self.BG)
        block.pack(fill='x', pady=(0, 18))

        title = tk.Frame(block, bg=self.BG)
        title.pack(fill='x', pady=(0, 8))
        tk.Label(title, text=f"v{release['version']}", bg=self.BG,
                 fg=self.FG, font=('Segoe UI', 12, 'bold')).pack(side='left')
        if release['date']:
            tk.Label(title, text=release['date'], bg=self.BG, fg=self.SUB,
                     font=('Segoe UI', 8)).pack(side='left', padx=(9, 0))
        if release['version'] == VERSION:
            self._pill(title, self.t('changelog_current'), self.ACCENT)
        elif highlight:
            self._pill(title, self.t('changelog_unseen'), self.GREEN)

        for kind, text in release['entries']:
            row = tk.Frame(block, bg=self.BG)
            row.pack(fill='x', pady=2)
            tone = getattr(self, ENTRY_TONES.get(kind, 'SUB'))
            tk.Label(row, text=self.t('changelog_' + kind), bg=tone,
                     fg=self.ON_ACCENT, font=('Segoe UI', 7, 'bold'),
                     padx=6, pady=2, width=9).pack(side='left', anchor='n')
            body = tk.Label(row, text=text.get(self.lang, text['fr']),
                            bg=self.BG, fg=self.FG, font=('Segoe UI', 9),
                            justify='left', anchor='w', wraplength=470)
            body.pack(side='left', fill='x', expand=True, padx=(10, 0))
            row.bind('<Configure>',
                     lambda e, lbl=body: lbl.configure(
                         wraplength=max(200, e.width - 100)))

    def _pill(self, parent, text: str, tone: str):
        tk.Label(parent, text=text, bg=tone, fg=self.ON_ACCENT,
                 font=('Segoe UI', 7, 'bold'), padx=7,
                 pady=1).pack(side='left', padx=(9, 0))

    def _open_url(self, url: str):
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _open_repo(self):
        self._open_url(REPO_URL)

    def _cancel(self):
        if self._compressor:
            self._compressor.cancel()

    def _open_output(self):
        output = Path(self.output_var.get().strip())
        self._open_path(output if output.is_dir() else output.parent)

    def _open_path(self, target):
        target = str(target)
        try:
            if sys.platform == 'win32':
                os.startfile(target)
            elif sys.platform == 'darwin':
                subprocess.run(['open', target])
            else:
                subprocess.run(['xdg-open', target])
        except Exception as e:
            messagebox.showerror(self.t('msg_error_title'),
                                 self.t('msg_open_folder_error', e=e))

    @staticmethod
    def _tag_for(msg: str) -> str:
        if msg.startswith('▶'):
            return 'header'
        if '✗' in msg or 'ERREUR' in msg or 'ERROR' in msg:
            return 'error'
        if '⚠' in msg:
            return 'warning'
        if '✓' in msg:
            return 'success'
        return 'info'

    def _passes_filter(self, tag: str) -> bool:
        mode = self.log_filter_var.get()
        if mode == 'warn':
            return tag in ('warning', 'error')
        if mode == 'error':
            return tag == 'error'
        return True

    def _set_log_filter(self, value: str):
        self._log_filter = value
        self.log_filter_var.set(value)
        self._paint_log_filter()
        self._refilter_log()

    def _paint_log_filter(self):
        active = self.log_filter_var.get()
        for value, btn in self._filter_btns.items():
            selected = value == active
            btn.configure(bg=self.ACCENT if selected else self.CARD,
                          fg=self.ON_ACCENT if selected else self.SUB,
                          font=('Segoe UI', 8, 'bold' if selected else 'normal'))

    def _paint_nav_badge(self):
        _, _, _, badge = self._nav['log']
        if self._counts['error']:
            badge.configure(text=str(self._counts['error']), fg=self.RED)
        elif self._counts['warning']:
            badge.configure(text=str(self._counts['warning']), fg=self.YELLOW)
        else:
            badge.configure(text="")

    def _log(self, msg: str, tag: str | None = None):
        tag = tag or self._tag_for(msg)

        def apply():
            self._log_entries.append((msg, tag))
            if tag in self._counts:
                self._counts[tag] += 1
                self._paint_nav_badge()
            if self._passes_filter(tag):
                self.log_box.configure(state='normal')
                self.log_box.insert('end', msg + '\n', tag)
                self.log_box.see('end')
                self.log_box.configure(state='disabled')

        self._ui(apply)

    def _refilter_log(self):
        self.log_box.configure(state='normal')
        self.log_box.delete('1.0', 'end')
        for msg, tag in self._log_entries:
            if self._passes_filter(tag):
                self.log_box.insert('end', msg + '\n', tag)
        self.log_box.see('end')
        self.log_box.configure(state='disabled')

    def _copy_log(self):
        self.root.clipboard_clear()
        self.root.clipboard_append('\n'.join(m for m, _ in self._log_entries))
        self._set_status(self.t('log_copied'))

    def _save_log(self):
        path = filedialog.asksaveasfilename(
            title=self.t('dialog_save_log'), defaultextension='.txt',
            filetypes=[(self.t('filetype_log'), "*.txt *.log"),
                       (self.t('filetype_all'), "*.*")])
        if not path:
            return
        try:
            Path(path).write_text('\n'.join(m for m, _ in self._log_entries),
                                  encoding='utf-8')
            self._log(self.t('log_saved', path=path))
        except OSError as e:
            messagebox.showerror(self.t('msg_error_title'), str(e))

    def _set_prog(self, val: float):
        def apply():
            self.prog_var.set(val)
            self.prog_pct_var.set(f"{val:.0f}%")
        self._ui(apply)

    def _set_status(self, msg: str):
        self._ui(lambda: self.status_var.set(msg))

    def _set_current_file(self, name: str):
        display = f"→ {name}" if name else ""
        if len(display) > 58:
            display = '…' + display[-57:]
        self._ui(lambda: self.file_var.set(display))

    def _clear_log(self):
        self._log_entries.clear()
        self._counts = {'warning': 0, 'error': 0}
        self._paint_nav_badge()
        self.log_box.configure(state='normal')
        self.log_box.delete('1.0', 'end')
        self.log_box.configure(state='disabled')

    def _log_header(self):
        self._log(self.t('log_app_version', version=VERSION))
        self._log(
            f"PIL : {'✓' if PIL_AVAILABLE else '✗'}  |  "
            f"srctools : {'✓' if SRCTOOLS_AVAILABLE else '✗'}  |  "
            f"ffmpeg : {'✓' if FFMPEG_AVAILABLE else '✗'}",
            tag='info',
        )
        if not PIL_AVAILABLE:
            self._log(self.t('log_install_pillow'), tag='info')
        self._log("")

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
            'profile_id':          self._profile_label_to_id.get(
                self.profile_var.get(), 'custom'),
            'rem_chands':          self.rem_chands.get(),
            'rem_unused':          self.rem_unused.get(),
            'check_materials':     self.check_materials.get(),
            'rem_unused_tex':      self.rem_unused_tex.get(),
            'dedup_tex':           self.dedup_tex.get(),
            'strip_whitelist':     self.strip_whitelist.get(),
            'convert_uncompressed': self.convert_uncompressed.get(),
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
            'page':                self._page,
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
        self.dedup_tex.set(state.get('dedup_tex', False))
        self.strip_whitelist.set(state.get('strip_whitelist', False))
        self.convert_uncompressed.set(state.get('convert_uncompressed', True))
        self.comp_tex.set(state.get('comp_tex', True))
        self.max_res.set(self.t('no_limit') if state.get('max_res_no_limit', False)
                         else state.get('max_res', '1024'))
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
            state['recent_sources'] = self._recent
            state['seen_version'] = self._seen_version
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(json.dumps(state, indent=2), encoding='utf-8')
        except OSError:
            pass

    def _on_close(self):
        if self._compressor is not None:
            self._compressor.cancel()
        self._stop_pump()
        self._stop_timer()
        self._save_config()
        self.root.destroy()

    def _rebuild(self):
        state = self._collect_state()
        entries = list(self._log_entries)
        counts = dict(self._counts)
        step_state, steps_done = self._step_state, self._steps_done

        for child in self.root.winfo_children():
            child.destroy()

        self.root.configure(bg=self.BG)
        self.pages, self.scrolls = {}, {}
        self._setup_styles()
        self._build_ui()
        self._restore_state(state)

        self._log_entries = entries
        self._counts = counts
        self._step_state, self._steps_done = step_state, steps_done
        self._paint_nav_badge()
        self._refilter_log()
        self._draw_pipeline()

    def _on_drop_source(self, event):
        raw = event.data.strip()
        path = raw[1:raw.index('}')] if raw.startswith('{') else raw.split()[0]
        path = path.strip()
        if path:
            self._set_source(path)

    def run(self):
        self.root.mainloop()
