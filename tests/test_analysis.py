"""Tests du moteur d'analyse de Compressez PM GMod.

Ces tests portent sur les fonctions pures (parsing .mdl/.vmt/.vtf, graphe de
dépendances, doublons, audit) et ne nécessitent ni tkinter ni GUI.

Lancement :  pytest -q
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import compressez_pm as m  # noqa: E402


# ─── Fabriques de fichiers binaires factices ────────────────────────────────

def make_mdl(material_name: str = "head", cdmaterials: str = "models/mymodel/") -> bytes:
    """Construit un .mdl minimal mais valide pour parse_mdl_materials."""
    buf = bytearray(512)
    buf[0:4] = b'IDST'
    textureindex = 224
    name_off_rel = 64                      # nom placé juste après le struct texture
    struct.pack_into('<i', buf, 204, 1)              # numtextures
    struct.pack_into('<i', buf, 208, textureindex)   # textureindex
    struct.pack_into('<i', buf, 212, 1)              # numcdtextures
    struct.pack_into('<i', buf, 216, 300)            # cdtextureindex
    struct.pack_into('<i', buf, textureindex, name_off_rel)  # sznameindex
    name_abs = textureindex + name_off_rel
    buf[name_abs:name_abs + len(material_name)] = material_name.encode()
    struct.pack_into('<i', buf, 300, 320)            # pointeur -> chaîne cdmat
    buf[320:320 + len(cdmaterials)] = cdmaterials.encode()
    return bytes(buf)


def make_vtf(width: int = 2048, height: int = 2048, fmt: int = 13,
             mipmaps: int = 1) -> bytes:
    """Construit un en-tête .vtf minimal lisible par read_vtf_info."""
    buf = bytearray(80)
    buf[0:4] = b'VTF\x00'
    struct.pack_into('<II', buf, 4, 7, 4)            # version 7.4
    struct.pack_into('<HH', buf, 16, width, height)
    struct.pack_into('<I', buf, 20, 0)               # flags
    struct.pack_into('<H', buf, 24, 1)               # frames
    struct.pack_into('<i', buf, 52, fmt)             # high-res format
    buf[56] = mipmaps
    return bytes(buf)


def vmt(basetexture: str) -> bytes:
    return (f'"VertexLitGeneric"\n{{\n\t"$basetexture" "{basetexture}"\n}}\n').encode()


# ─── parse_vmt_refs ─────────────────────────────────────────────────────────

def test_parse_vmt_refs_resolves_paths():
    refs = m.parse_vmt_refs('"$basetexture" "models/x/head"')
    assert refs['basetexture'] == 'materials/models/x/head.vtf'


def test_parse_vmt_refs_ignores_env_cubemap():
    assert m.parse_vmt_refs('"$envmap" "env_cubemap"') == {}


def test_resolve_material_ref_adds_prefix_and_suffix():
    assert m.resolve_material_ref('models/x/body') == 'materials/models/x/body.vtf'
    assert m.resolve_material_ref('materials/models/x/body.vtf') == 'materials/models/x/body.vtf'


# ─── parse_mdl_materials ────────────────────────────────────────────────────

def test_parse_mdl_materials_reads_name_and_dir():
    names, dirs = m.parse_mdl_materials(make_mdl("head", "models/mymodel/"))
    assert names == ["head"]
    assert dirs == ["models/mymodel/"]


def test_parse_mdl_materials_rejects_non_mdl():
    assert m.parse_mdl_materials(b'NOPE' + b'\x00' * 300) == ([], [])


# ─── read_vtf_info ──────────────────────────────────────────────────────────

def test_read_vtf_info_dxt1():
    info = m.read_vtf_info(make_vtf(1024, 1024, fmt=13))
    assert info['width'] == 1024 and info['height'] == 1024
    assert info['format_name'] == 'DXT1'


def test_read_vtf_info_rejects_garbage():
    assert m.read_vtf_info(b'not a vtf') is None


# ─── build_dependency_graph ─────────────────────────────────────────────────

def test_dependency_graph_flags_orphan_vtf():
    files = {
        'materials/models/x/head.vmt': vmt('models/x/head'),
        'materials/models/x/head.vtf': make_vtf(),
        'materials/models/x/leftover.vtf': make_vtf(),
    }
    g = m.build_dependency_graph(files)
    assert 'materials/models/x/leftover.vtf' in g['orphan_vtf']
    assert 'materials/models/x/head.vtf' not in g['orphan_vtf']


def test_dependency_graph_mdl_links_vmt():
    files = {
        'models/mymodel/char.mdl': make_mdl("head", "models/mymodel/"),
        'materials/models/mymodel/head.vmt': vmt('models/mymodel/head'),
        'materials/models/mymodel/head.vtf': make_vtf(),
        'materials/models/mymodel/unused.vmt': vmt('models/mymodel/unused'),
    }
    g = m.build_dependency_graph(files)
    assert g['mdl_materials_parsed'] is True
    assert 'materials/models/mymodel/head.vmt' in g['referenced_vmt']
    assert 'materials/models/mymodel/unused.vmt' in g['orphan_vmt']


def test_dependency_graph_no_mdl_means_no_vmt_orphans():
    files = {
        'materials/models/x/a.vmt': vmt('models/x/a'),
        'materials/models/x/a.vtf': make_vtf(),
    }
    g = m.build_dependency_graph(files)
    assert g['orphan_vmt'] == []          # pas de .mdl -> aucun faux positif


# ─── find_duplicate_textures ────────────────────────────────────────────────

def test_find_duplicate_textures():
    same = make_vtf(512, 512)
    files = {
        'materials/a.vtf': same,
        'materials/b.vtf': same,
        'materials/c.vtf': make_vtf(256, 256),
    }
    groups = m.find_duplicate_textures(files)
    assert groups == [['materials/a.vtf', 'materials/b.vtf']]


# ─── audit_textures ─────────────────────────────────────────────────────────

def test_audit_flags_oversized_and_uncompressed():
    files = {
        'materials/big.vtf': make_vtf(2048, 2048, fmt=0),   # RGBA8888, 2048px
    }
    issues = m.audit_textures(files, max_res=1024)
    kinds = {i['issue'] for i in issues}
    assert 'audit_oversized' in kinds
    assert 'audit_uncompressed' in kinds


def test_audit_flags_npot():
    files = {'materials/odd.vtf': make_vtf(300, 200, fmt=13)}
    issues = m.audit_textures(files, max_res=None)
    assert any(i['issue'] == 'audit_npot' for i in issues)


# ─── classification (regression) ────────────────────────────────────────────

def test_classify_roles():
    C = m.Compressor
    assert C._classify_texture_role('materials/x/head.vtf') == 'role_head'
    assert C._classify_texture_role('materials/x/casque.vtf') == 'role_helmet'
    assert C._classify_texture_role('materials/x/body_normal.vtf') == 'role_normalmap'
    assert C._classify_texture_role('materials/x/eye_glow.vtf') == 'role_eye_effect'
