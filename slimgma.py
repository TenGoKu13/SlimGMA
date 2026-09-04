#!/usr/bin/env python3
from __future__ import annotations

import sys

from cpm import (
    VERSION, STRINGS, t, GMAFile, norm_key, resolve_material_ref,
    parse_vmt_refs, parse_mdl_materials, read_vtf_info, build_dependency_graph,
    find_duplicate_textures, audit_textures, VTF_UNCOMPRESSED_FORMATS,
    is_gma_whitelisted, check_gma_whitelist, dedup_textures,
    Compressor, cli_main,
)
from cpm.gui import App, TK_AVAILABLE


if __name__ == '__main__':
    if len(sys.argv) > 1:
        cli_main()
    elif TK_AVAILABLE:
        App().run()
    else:
        print("tkinter non disponible. Utilisez le mode CLI :")
        print("  python slimgma.py --help")
        sys.exit(1)
