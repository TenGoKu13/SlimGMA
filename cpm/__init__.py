from .constants import VERSION
from .i18n import STRINGS, t
from .gma import GMAFile
from .analysis import (
    norm_key, resolve_material_ref, parse_vmt_refs, parse_mdl_materials,
    read_vtf_info, build_dependency_graph, find_duplicate_textures,
    audit_textures, VTF_UNCOMPRESSED_FORMATS, is_gma_whitelisted,
    check_gma_whitelist, dedup_textures,
)
from .report import build_html_report
from .compressor import Compressor
from .cli import cli_main

__all__ = [
    'VERSION', 'STRINGS', 't', 'GMAFile', 'norm_key', 'resolve_material_ref',
    'parse_vmt_refs', 'parse_mdl_materials', 'read_vtf_info',
    'build_dependency_graph', 'find_duplicate_textures', 'audit_textures',
    'VTF_UNCOMPRESSED_FORMATS', 'is_gma_whitelisted', 'check_gma_whitelist',
    'dedup_textures', 'build_html_report', 'Compressor', 'cli_main',
]
