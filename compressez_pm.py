#!/usr/bin/env python3
# Requires Python 3.9+ (Windows 64-bit compatible)
"""
Compressez PM GMod
Outil de compression d'addons Playermodel pour Garry's Mod.

Ce fichier est le point d'entrée. Toute la logique vit désormais dans le
package `cpm/` (deps, constants, i18n, gma, analysis, report, compressor,
gui, cli). Il est aussi conservé comme façade : `import compressez_pm`
ré-exporte l'API publique, de sorte que les scripts et les tests existants
continuent de fonctionner sans changement.
"""
from __future__ import annotations

import sys

# Ré-export de l'API publique du package.
from cpm import (  # noqa: F401
    VERSION, STRINGS, t, GMAFile, norm_key, resolve_material_ref,
    parse_vmt_refs, parse_mdl_materials, read_vtf_info, build_dependency_graph,
    find_duplicate_textures, audit_textures, VTF_UNCOMPRESSED_FORMATS,
    is_gma_whitelisted, check_gma_whitelist, dedup_textures,
    build_html_report, Compressor, cli_main,
)
from cpm.gui import App, TK_AVAILABLE  # noqa: F401


if __name__ == '__main__':
    if len(sys.argv) > 1:
        cli_main()
    elif TK_AVAILABLE:
        App().run()
    else:
        print("tkinter non disponible. Utilisez le mode CLI :")
        print("  python compressez_pm.py --help")
        sys.exit(1)
