import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import compressez_pm as m


def _sample_gma(tmp_path: Path) -> Path:
    gma = m.GMAFile()
    gma.name = "Mon Addon"
    gma.description = "Un playermodel de test"
    gma.author = "TenGoKu13"
    gma.files = {
        'models/player/bob.mdl': b'IDST' + b'\x00' * 60,
        'Materials/Models/Bob/head.VTF': b'VTF\x00' + b'\x01' * 40,
        'lua/autorun/sh_bob.lua': b'-- hello\n',
        'addon.json': b'{"title": "x"}',
    }
    out = tmp_path / 'sample.gma'
    gma.save(str(out))
    return out


def test_gma_roundtrip(tmp_path):
    path = _sample_gma(tmp_path)

    loaded = m.GMAFile()
    loaded.load(str(path))

    assert loaded.name == "Mon Addon"
    assert loaded.description == "Un playermodel de test"
    assert loaded.author == "TenGoKu13"

    assert set(loaded.files) == {
        'models/player/bob.mdl',
        'materials/models/bob/head.vtf',
        'lua/autorun/sh_bob.lua',
    }
    assert loaded.files['models/player/bob.mdl'] == b'IDST' + b'\x00' * 60
    assert loaded.files['lua/autorun/sh_bob.lua'] == b'-- hello\n'


def test_gma_files_sorted_like_gmad(tmp_path):
    path = _sample_gma(tmp_path)
    loaded = m.GMAFile()
    loaded.load(str(path))
    assert list(loaded.files) == sorted(loaded.files)


def test_gma_load_rejects_bad_magic(tmp_path):
    bad = tmp_path / 'bad.gma'
    bad.write_bytes(b'NOPE' + b'\x00' * 64)
    gma = m.GMAFile()
    try:
        gma.load(str(bad))
        raised = False
    except ValueError:
        raised = True
    assert raised
