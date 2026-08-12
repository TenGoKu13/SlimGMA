import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cpm import vtf as vtf_tools

srctools_vtf = pytest.importorskip('srctools.vtf')
ImageFormats = srctools_vtf.ImageFormats
VTF = srctools_vtf.VTF
VTFFlags = srctools_vtf.VTFFlags

pytestmark = pytest.mark.skipif(not vtf_tools.available(),
                                reason="srctools indisponible")


def make_vtf(width, height, fmt=ImageFormats.RGBA8888, alpha=255,
             flags=None, step=8):
    image = VTF(width, height, fmt=fmt,
                flags=flags if flags is not None else VTFFlags.EMPTY)
    frame = image.get(mipmap=0)
    for x in range(0, width, step):
        for y in range(0, height, step):
            frame[x, y] = (x % 256, y % 256, 64, alpha)
    buffer = io.BytesIO()
    image.save(buffer)
    return buffer.getvalue()


def read(data):
    return VTF.read(io.BytesIO(data))


def test_downscale_to_max_resolution():
    data = make_vtf(512, 512, ImageFormats.DXT5)
    out = vtf_tools.optimize(data, 128, to_dxt=True)
    result = read(out)
    assert (result.width, result.height) == (128, 128)
    assert len(out) < len(data)


def test_uncompressed_becomes_dxt_and_shrinks():
    data = make_vtf(256, 256, ImageFormats.RGBA8888)
    out = vtf_tools.optimize(data, None, to_dxt=True)
    assert read(out).format.name.startswith('DXT')
    assert len(out) < len(data) / 2


def test_opaque_uses_dxt1_translucent_uses_dxt5():
    opaque = make_vtf(128, 128, ImageFormats.RGBA8888, alpha=255,
                      flags=VTFFlags.EIGHTBITALPHA, step=1)
    translucent = make_vtf(128, 128, ImageFormats.RGBA8888, alpha=100,
                           flags=VTFFlags.EIGHTBITALPHA, step=1)
    assert read(vtf_tools.optimize(opaque, None, True)).format.name == 'DXT1'
    assert read(vtf_tools.optimize(translucent, None, True)).format.name == 'DXT5'


def test_declines_when_nothing_to_do():
    data = make_vtf(64, 64, ImageFormats.DXT1)
    assert vtf_tools.optimize(data, 256, to_dxt=True) is None


def test_conversion_disabled_keeps_format():
    data = make_vtf(128, 128, ImageFormats.RGBA8888)
    assert vtf_tools.optimize(data, None, to_dxt=False) is None
    out = vtf_tools.optimize(data, 64, to_dxt=False)
    assert read(out).format.name == 'RGBA8888'
    assert (read(out).width, read(out).height) == (64, 64)


def test_cubemaps_are_left_alone():
    import struct
    data = bytearray(make_vtf(64, 64, ImageFormats.DXT5))
    flags = struct.unpack_from('<I', data, 20)[0]
    struct.pack_into('<I', data, 20, flags | VTFFlags.ENVMAP.value)
    assert vtf_tools.optimize(bytes(data), 16, to_dxt=True) is None


def test_garbage_input_is_declined():
    assert vtf_tools.optimize(b'not a vtf at all', 64, to_dxt=True) is None
    assert vtf_tools.optimize(b'', 64, to_dxt=True) is None


def test_output_keeps_a_mipmap_chain():
    data = make_vtf(256, 256, ImageFormats.RGBA8888)
    result = read(vtf_tools.optimize(data, 64, to_dxt=True))
    assert result.mipmap_count > 1


def test_compressor_uses_the_pipeline():
    from cpm.compressor import Compressor
    compressor = Compressor({'lang': 'fr', 'convert_uncompressed': True},
                            log_fn=lambda *_: None, progress_fn=lambda *_: None,
                            status_fn=lambda *_: None)
    data = make_vtf(512, 512, ImageFormats.RGBA8888)
    out = compressor._process_vtf('materials/x.vtf', data, 128, 85)
    assert len(out) < len(data) / 10
    assert (read(out).width, read(out).height) == (128, 128)
