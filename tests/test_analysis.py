import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import compressez_pm as m


def make_mdl(material_name: str = "head", cdmaterials: str = "models/mymodel/") -> bytes:
    buf = bytearray(512)
    buf[0:4] = b'IDST'
    textureindex = 224
    name_off_rel = 64
    struct.pack_into('<i', buf, 204, 1)
    struct.pack_into('<i', buf, 208, textureindex)
    struct.pack_into('<i', buf, 212, 1)
    struct.pack_into('<i', buf, 216, 300)
    struct.pack_into('<i', buf, textureindex, name_off_rel)
    name_abs = textureindex + name_off_rel
    buf[name_abs:name_abs + len(material_name)] = material_name.encode()
    struct.pack_into('<i', buf, 300, 320)
    buf[320:320 + len(cdmaterials)] = cdmaterials.encode()
    return bytes(buf)


def make_vtf(width: int = 2048, height: int = 2048, fmt: int = 13,
             mipmaps: int = 1) -> bytes:
    buf = bytearray(80)
    buf[0:4] = b'VTF\x00'
    struct.pack_into('<II', buf, 4, 7, 4)
    struct.pack_into('<HH', buf, 16, width, height)
    struct.pack_into('<I', buf, 20, 0)
    struct.pack_into('<H', buf, 24, 1)
    struct.pack_into('<i', buf, 52, fmt)
    buf[56] = mipmaps
    return bytes(buf)


def vmt(basetexture: str) -> bytes:
    return (f'"VertexLitGeneric"\n{{\n\t"$basetexture" "{basetexture}"\n}}\n').encode()


def test_parse_vmt_refs_resolves_paths():
    refs = m.parse_vmt_refs('"$basetexture" "models/x/head"')
    assert refs['basetexture'] == 'materials/models/x/head.vtf'


def test_parse_vmt_refs_ignores_env_cubemap():
    assert m.parse_vmt_refs('"$envmap" "env_cubemap"') == {}


def test_resolve_material_ref_adds_prefix_and_suffix():
    assert m.resolve_material_ref('models/x/body') == 'materials/models/x/body.vtf'
    assert m.resolve_material_ref('materials/models/x/body.vtf') == 'materials/models/x/body.vtf'


def test_parse_mdl_materials_reads_name_and_dir():
    names, dirs = m.parse_mdl_materials(make_mdl("head", "models/mymodel/"))
    assert names == ["head"]
    assert dirs == ["models/mymodel/"]


def test_parse_mdl_materials_rejects_non_mdl():
    assert m.parse_mdl_materials(b'NOPE' + b'\x00' * 300) == ([], [])


def test_read_vtf_info_dxt1():
    info = m.read_vtf_info(make_vtf(1024, 1024, fmt=13))
    assert info['width'] == 1024 and info['height'] == 1024
    assert info['format_name'] == 'DXT1'


def test_read_vtf_info_rejects_garbage():
    assert m.read_vtf_info(b'not a vtf') is None


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
    assert g['orphan_vmt'] == []


def test_find_duplicate_textures():
    same = make_vtf(512, 512)
    files = {
        'materials/a.vtf': same,
        'materials/b.vtf': same,
        'materials/c.vtf': make_vtf(256, 256),
    }
    groups = m.find_duplicate_textures(files)
    assert groups == [['materials/a.vtf', 'materials/b.vtf']]


def test_audit_flags_oversized_and_uncompressed():
    files = {
        'materials/big.vtf': make_vtf(2048, 2048, fmt=0),
    }
    issues = m.audit_textures(files, max_res=1024)
    kinds = {i['issue'] for i in issues}
    assert 'audit_oversized' in kinds
    assert 'audit_uncompressed' in kinds


def test_audit_flags_npot():
    files = {'materials/odd.vtf': make_vtf(300, 200, fmt=13)}
    issues = m.audit_textures(files, max_res=None)
    assert any(i['issue'] == 'audit_npot' for i in issues)


def test_classify_roles():
    C = m.Compressor
    assert C._classify_texture_role('materials/x/head.vtf') == 'role_head'
    assert C._classify_texture_role('materials/x/casque.vtf') == 'role_helmet'
    assert C._classify_texture_role('materials/x/body_normal.vtf') == 'role_normalmap'
    assert C._classify_texture_role('materials/x/eye_glow.vtf') == 'role_eye_effect'


def test_whitelist_accepts_standard_addon_files():
    for path in (
        'lua/autorun/sh_pm.lua',
        'lua/a/b/c/deep.lua',
        'models/player/bob.mdl',
        'models/player/bob.dx90.vtx',
        'materials/models/bob/head.vtf',
        'materials/models/bob/head.vmt',
        'sound/bob/hello.wav',
        'addon.json',
    ):
        assert m.is_gma_whitelisted(path), path


def test_whitelist_rejects_junk():
    for path in (
        'readme.txt',
        'source.psd',
        'stray.blend',
        'materials/notes.txt',
        'models/raw.blend',
    ):
        assert not m.is_gma_whitelisted(path), path


def test_check_gma_whitelist_lists_offenders():
    files = {
        'lua/autorun/ok.lua': b'',
        'bad.blend': b'',
        '__meta__': b'{}',
    }
    assert m.check_gma_whitelist(files) == ['bad.blend']


def test_dedup_prefers_referenced_copy_and_rewrites_vmt():
    same = make_vtf(512, 512)
    files = {
        'materials/models/x/head.vmt': vmt('models/x/head'),
        'materials/models/x/zz_dup.vmt': vmt('models/x/zz_dup'),
        'materials/models/x/head.vtf': same,
        'materials/models/x/zz_dup.vtf': same,
    }
    result = m.dedup_textures(files)

    assert result['removed'] == ['materials/models/x/zz_dup.vtf']
    assert 'materials/models/x/zz_dup.vtf' not in files
    assert 'materials/models/x/head.vtf' in files
    assert result['rewritten_vmt'] == ['materials/models/x/zz_dup.vmt']
    rewritten = files['materials/models/x/zz_dup.vmt'].decode()
    assert 'models/x/head' in rewritten
    assert 'zz_dup' not in rewritten.replace('zz_dup.vmt', '')
    assert result['saved'] == len(same)


def test_dedup_orphan_duplicate_merged_without_rewrite():
    same = make_vtf(256, 256)
    files = {
        'materials/models/x/head.vmt': vmt('models/x/head'),
        'materials/models/x/head.vtf': same,
        'materials/models/x/copy.vtf': same,
    }
    result = m.dedup_textures(files)
    assert result['removed'] == ['materials/models/x/copy.vtf']
    assert result['rewritten_vmt'] == []
    assert 'materials/models/x/head.vtf' in files


def test_dedup_no_duplicates_is_noop():
    files = {
        'materials/a.vtf': make_vtf(64, 64),
        'materials/b.vtf': make_vtf(128, 128),
    }
    before = dict(files)
    result = m.dedup_textures(files)
    assert result['removed'] == [] and result['saved'] == 0
    assert files == before


def _dummy_compressor(opts=None) -> 'm.Compressor':
    base = {'lang': 'fr', 'lua_chands': True}
    base.update(opts or {})
    return m.Compressor(base, log_fn=lambda _m: None,
                        progress_fn=lambda _v: None, status_fn=lambda _s: None)


def test_generate_lua_uses_valid_gmod_api():
    files = {
        'models/player/bob.mdl': b'',
        'models/weapons/c_arms_bob.mdl': b'',
    }
    _dummy_compressor()._generate_lua(files, 'bob_addon')

    lua_path = 'lua/autorun/sh_bob_addon_pm.lua'
    assert lua_path in files
    lua = files[lua_path].decode()
    assert 'player_manager.AddValidModel' in lua
    assert 'list.Set("PlayerOptionsModel"' in lua
    assert 'player_manager.AddValidHands' in lua
    assert 'models/weapons/c_arms_bob.mdl' in lua
    assert 'GetBodygroupsString' not in lua


def test_generate_lua_without_chands():
    files = {'models/player/bob.mdl': b''}
    _dummy_compressor()._generate_lua(files, 'bob')
    lua = files['lua/autorun/sh_bob_pm.lua'].decode()
    assert 'AddValidModel' in lua
    assert 'AddValidHands' not in lua


def test_fmt_size():
    fmt = m.Compressor._fmt_size
    assert fmt(0) == '0 o'
    assert fmt(512) == '512 o'
    assert fmt(2048) == '2.0 Ko'
    assert fmt(5 * 1024 * 1024) == '5.0 Mo'


def test_sound_encoders_keep_extension():
    encoders = m.Compressor._SOUND_ENCODERS
    assert set(encoders) == {'.mp3', '.ogg', '.wav'}


def test_generated_lua_has_no_comment_header():
    files = {'models/player/bob.mdl': b''}
    _dummy_compressor()._generate_lua(files, 'bob')
    lua = files['lua/autorun/sh_bob_pm.lua'].decode()
    assert not any(line.lstrip().startswith('--') for line in lua.splitlines())


def test_reduction_label_sign():
    comp = _dummy_compressor()
    comp.reduction = 20.0
    assert comp.reduction_label() == '-20.0%'
    comp.reduction = -2.7
    assert comp.reduction_label() == '+2.7%'
    comp.reduction = None
    assert comp.reduction_label() == '—'


def test_build_report_keeps_translation_keys():
    comp = _dummy_compressor()
    comp.original_size, comp.final_size, comp.reduction = 2048, 1024, 50.0
    comp.analysis = {
        'roles': {'role_head': ['materials/a.vtf']},
        'orphan_vtf': ['materials/b.vtf'],
        'orphan_vmt': ['materials/c.vmt'],
        'duplicates': [['materials/d.vtf', 'materials/e.vtf']],
        'audit': [{'path': 'materials/f.vtf', 'issue': 'audit_npot',
                   'detail': '300x300'}],
        'removed': True,
    }
    report = comp.build_report({'a': b'', '__meta__': b''}, 'bob')

    assert report['addon'] == 'bob'
    assert report['removed'] is True
    assert report['summary'] == {'original': '2.0 Ko', 'final': '1.0 Ko',
                                 'reduction': '-50.0%', 'files': '1'}
    assert report['roles'] == [('role_head', ['materials/a.vtf'])]
    assert report['orphans'] == ['materials/b.vtf', 'materials/c.vmt']
    assert report['duplicates'] == [['materials/d.vtf', 'materials/e.vtf']]
    assert report['audit'] == [{'path': 'materials/f.vtf',
                                'issue': 'audit_npot', 'detail': '300x300'}]


def test_build_report_without_analysis_is_empty_but_valid():
    comp = _dummy_compressor()
    report = comp.build_report({}, 'bob')
    assert report['roles'] == [] and report['orphans'] == []
    assert report['duplicates'] == [] and report['audit'] == []


def test_report_labels_exist_for_every_audit_issue():
    for issue in ('audit_oversized', 'audit_uncompressed', 'audit_npot'):
        assert m.STRINGS['report_' + issue]['fr']
        assert m.STRINGS['report_' + issue]['en']


def test_no_html_report_is_written(tmp_path):
    from cpm.compressor import Compressor
    src = tmp_path / 'addon'
    (src / 'models' / 'player').mkdir(parents=True)
    (src / 'models' / 'player' / 'bob.mdl').write_bytes(b'IDST' + bytes(400))
    out = tmp_path / 'out'
    Compressor({'source': str(src), 'output': str(out), 'lang': 'fr'},
               log_fn=lambda *_: None, progress_fn=lambda *_: None,
               status_fn=lambda *_: None).run()
    assert not list(tmp_path.rglob('*.html'))


def test_gui_delta_label():
    from cpm.gui import App
    assert App._delta_label(20.0) == '-20.0%'
    assert App._delta_label(0) == '-0.0%'
    assert App._delta_label(-2.7) == '+2.7%'
    assert App._delta_label(None) == '—'


def test_target_size_skips_quality_passes_without_pil_images():
    comp = _dummy_compressor()
    comp.opts.update({'max_resolution': '1024', 'texture_quality': 85})

    only_vtf = {'materials/a.vtf': b'', 'models/b.mdl': b''}
    steps = comp._target_size_steps(only_vtf)
    assert {q for _res, q in steps} == {85}

    with_png = dict(only_vtf, **{'materials/c.png': b''})
    assert len({q for _res, q in comp._target_size_steps(with_png)}) > 1
