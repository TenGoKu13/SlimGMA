#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

from cpm import (
    VERSION, STRINGS, t, GMAFile, norm_key, resolve_material_ref,
    parse_vmt_refs, parse_mdl_materials, read_vtf_info, build_dependency_graph,
    find_duplicate_textures, audit_textures, VTF_UNCOMPRESSED_FORMATS,
    is_gma_whitelisted, check_gma_whitelist, dedup_textures,
    Compressor, cli_main,
)
from cpm.gui import App, TK_AVAILABLE

ATTACH_PARENT_PROCESS = -1


def _open_console_stream():
    if sys.platform == 'win32':
        try:
            return open('CONOUT$', 'w', encoding='utf-8', errors='replace')
        except OSError:
            pass
    return open(os.devnull, 'w', encoding='utf-8', errors='replace')


def attach_console() -> None:
    if sys.stdout is not None and sys.stderr is not None:
        return

    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.kernel32.AttachConsole(ATTACH_PARENT_PROCESS)
        except Exception:
            pass

    for name in ('stdout', 'stderr'):
        if getattr(sys, name, None) is None:
            try:
                setattr(sys, name, _open_console_stream())
            except OSError:
                pass


if __name__ == '__main__':
    if len(sys.argv) > 1:
        attach_console()
        cli_main()
    elif TK_AVAILABLE:
        App().run()
    else:
        attach_console()
        print("tkinter non disponible. Utilisez le mode CLI :")
        print("  python slimgma.py --help")
        sys.exit(1)
