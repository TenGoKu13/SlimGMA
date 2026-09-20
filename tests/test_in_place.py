import os
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cpm.compressor import Compressor


def make_addon(root: Path) -> Path:
    (root / 'models' / 'player').mkdir(parents=True)
    (root / 'models' / 'player' / 'bob.mdl').write_bytes(b'IDST' + bytes(400))
    (root / 'models' / 'weapons').mkdir(parents=True)
    (root / 'models' / 'weapons' / 'c_arms_bob.mdl').write_bytes(b'IDST')
    materials = root / 'materials' / 'models' / 'bob'
    materials.mkdir(parents=True)
    (materials / 'head.vmt').write_text(
        '"VertexLitGeneric"\n{\n"$basetexture" "models/bob/head"\n}\n')
    header = bytearray(80)
    header[0:4] = b'VTF\x00'
    struct.pack_into('<III', header, 4, 7, 2, 80)
    struct.pack_into('<HH', header, 16, 64, 64)
    struct.pack_into('<H', header, 24, 1)
    struct.pack_into('<i', header, 52, 13)
    header[56] = 1
    struct.pack_into('<i', header, 57, -1)
    (materials / 'head.vtf').write_bytes(bytes(header) + bytes(64))
    (root / 'lisezmoi.txt').write_text('documentation inutile')
    return root


def run(source: Path, **extra):
    opts = {
        'source': str(source), 'output': str(source), 'in_place': True,
        'output_format': 'folder', 'lang': 'fr', 'remove_chands': True,
        'remove_unused': True, 'compress_textures': True,
        'max_resolution': '1024', 'check_materials': False, 'gen_lua': False,
    }
    opts.update(extra)
    compressor = Compressor(opts, log_fn=lambda *_: None,
                            progress_fn=lambda *_: None, status_fn=lambda *_: None)
    compressor.run()
    return compressor


def listing(root: Path) -> set:
    return {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}


def test_removed_files_actually_disappear_from_disk(tmp_path):
    addon = make_addon(tmp_path / 'addon')
    assert 'lisezmoi.txt' in listing(addon)

    compressor = run(addon)

    assert compressor.final_size is not None
    remaining = listing(addon)
    assert 'lisezmoi.txt' not in remaining
    assert not any('c_arms' in name for name in remaining)
    assert 'models/player/bob.mdl'.replace('/', os.sep) in remaining


def test_no_temporary_leftovers(tmp_path):
    addon = make_addon(tmp_path / 'addon')
    run(addon)
    siblings = [p.name for p in tmp_path.iterdir()]
    assert not [name for name in siblings if 'slimgma' in name]


def test_backup_keeps_the_untouched_original(tmp_path):
    addon = make_addon(tmp_path / 'addon')
    before = listing(addon)

    run(addon, backup_original=True)

    backups = [p for p in tmp_path.iterdir() if p.name.startswith('addon_backup_')]
    assert len(backups) == 1
    assert listing(backups[0]) == before
    assert 'lisezmoi.txt' not in listing(addon)


def test_original_survives_a_failure_during_the_swap(tmp_path, monkeypatch):
    addon = make_addon(tmp_path / 'addon')
    before = {name: (addon / name).read_bytes() for name in listing(addon)}

    real_replace = os.replace
    calls = {'count': 0}

    def flaky(source, destination):
        calls['count'] += 1
        if calls['count'] == 2:
            raise OSError("panne simulée")
        return real_replace(source, destination)

    monkeypatch.setattr(os, 'replace', flaky)
    compressor = run(addon)

    assert compressor.final_size is None
    assert {name: (addon / name).read_bytes() for name in listing(addon)} == before
    assert not [p.name for p in tmp_path.iterdir() if 'slimgma' in p.name]


def test_dry_run_touches_nothing(tmp_path):
    addon = make_addon(tmp_path / 'addon')
    before = {name: (addon / name).read_bytes() for name in listing(addon)}

    run(addon, dry_run=True)

    assert {name: (addon / name).read_bytes() for name in listing(addon)} == before


def test_normal_mode_still_writes_beside_the_source(tmp_path):
    addon = make_addon(tmp_path / 'addon')
    output = tmp_path / 'sortie'

    compressor = Compressor(
        {'source': str(addon), 'output': str(output), 'output_format': 'folder',
         'lang': 'fr', 'remove_unused': True, 'compress_textures': False,
         'check_materials': False, 'gen_lua': False},
        log_fn=lambda *_: None, progress_fn=lambda *_: None,
        status_fn=lambda *_: None)
    compressor.run()

    assert compressor.final_size is not None
    assert output.is_dir()
    assert 'lisezmoi.txt' in listing(addon)


def test_locked_folder_gives_a_readable_error(tmp_path, monkeypatch):
    addon = make_addon(tmp_path / 'addon')
    before = {name: (addon / name).read_bytes() for name in listing(addon)}
    messages = []

    def locked(source, destination):
        raise PermissionError(13, "utilisé par un autre processus")

    monkeypatch.setattr(os, 'replace', locked)
    opts = {'source': str(addon), 'output': str(addon), 'in_place': True,
            'output_format': 'folder', 'lang': 'fr', 'compress_textures': False,
            'check_materials': False, 'gen_lua': False}
    compressor = Compressor(opts, log_fn=messages.append,
                            progress_fn=lambda *_: None, status_fn=lambda *_: None)
    compressor.run()

    assert compressor.final_size is None
    joined = "\n".join(messages)
    assert "utilisé par un autre programme" in joined
    assert "n'a pas été touché" in joined
    assert "Traceback" not in joined
    assert {name: (addon / name).read_bytes() for name in listing(addon)} == before


def test_a_stranded_original_is_reported_with_its_path(tmp_path, monkeypatch):
    addon = make_addon(tmp_path / 'addon')
    messages = []
    real_replace = os.replace
    calls = {'count': 0}

    def flaky(source, destination):
        calls['count'] += 1
        if calls['count'] >= 2:
            raise OSError("panne")
        return real_replace(source, destination)

    monkeypatch.setattr(os, 'replace', flaky)
    opts = {'source': str(addon), 'output': str(addon), 'in_place': True,
            'output_format': 'folder', 'lang': 'fr', 'compress_textures': False,
            'check_materials': False, 'gen_lua': False}
    compressor = Compressor(opts, log_fn=messages.append,
                            progress_fn=lambda *_: None, status_fn=lambda *_: None)
    compressor.run()

    joined = "\n".join(messages)
    assert compressor.final_size is None
    assert 'slimgma-old' in joined
    assert "Traceback" not in joined
    stranded = [p for p in tmp_path.iterdir() if 'slimgma-old' in p.name]
    assert len(stranded) == 1
    assert 'lisezmoi.txt' in listing(stranded[0])


def test_in_place_log_does_not_mention_the_staging_folder(tmp_path):
    addon = make_addon(tmp_path / 'addon')
    messages = []
    opts = {'source': str(addon), 'output': str(addon), 'in_place': True,
            'output_format': 'folder', 'lang': 'fr', 'compress_textures': False,
            'check_materials': False, 'gen_lua': False}
    Compressor(opts, log_fn=messages.append, progress_fn=lambda *_: None,
               status_fn=lambda *_: None).run()

    joined = "\n".join(messages)
    assert 'slimgma-tmp' not in joined
    assert 'remplacé sur place' in joined
