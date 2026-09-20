from io import BytesIO

from .deps import SRCTOOLS_AVAILABLE

if SRCTOOLS_AVAILABLE:
    from srctools.vtf import VTF, Frame, ImageFormats, VTFFlags
else:
    VTF = Frame = ImageFormats = VTFFlags = None


UNCOMPRESSED = {
    'RGBA8888', 'ABGR8888', 'ARGB8888', 'BGRA8888', 'BGRX8888',
    'RGB888', 'BGR888', 'UVLX8888',
}
ALPHA_FLAGS_NAMES = ('ONEBITALPHA', 'EIGHTBITALPHA')


def available() -> bool:
    return SRCTOOLS_AVAILABLE


def _alpha_flag(name: str):
    return getattr(VTFFlags, name, None)


def _is_cubemap(source) -> bool:
    envmap = getattr(VTFFlags, 'ENVMAP', None)
    return envmap is not None and bool(source.flags & envmap)


def _declares_alpha(source) -> bool:
    for name in ALPHA_FLAGS_NAMES:
        flag = _alpha_flag(name)
        if flag is not None and source.flags & flag:
            return True
    return False


def _uses_alpha(frame) -> bool:
    try:
        image = frame.to_PIL()
    except Exception:
        return True
    if 'A' not in (image.getbands() or ()):
        return False
    try:
        low, _high = image.getextrema()[-1]
    except (TypeError, IndexError):
        return True
    return low < 255


def _target_format(source, frame, to_dxt: bool):
    current = source.format
    if current.name.startswith('DXT'):
        return current
    if not to_dxt or current.name not in UNCOMPRESSED:
        return current
    if not current.a:
        return ImageFormats.DXT1
    if not _declares_alpha(source) or not _uses_alpha(frame):
        return ImageFormats.DXT1
    return ImageFormats.DXT5


def _target_size(width: int, height: int, max_res: int | None) -> tuple[int, int]:
    if not max_res:
        return width, height
    while max(width, height) > max_res:
        if width % 2 or height % 2 or width < 2 or height < 2:
            break
        width //= 2
        height //= 2
    return width, height


def _downscale(frame, width: int, height: int):
    frame.load()
    while frame.width > width or frame.height > height:
        smaller = Frame(max(1, frame.width // 2), max(1, frame.height // 2))
        smaller.rescale_from(frame)
        frame = smaller
        if frame.width == width and frame.height == height:
            break
    return frame


def _rebuild_flags(source, fmt):
    flags = source.flags
    for name in ALPHA_FLAGS_NAMES:
        flag = _alpha_flag(name)
        if flag is not None:
            flags &= ~flag
    if fmt.a:
        flag = _alpha_flag('EIGHTBITALPHA')
        if flag is not None:
            flags |= flag
    return flags


BLANK_SAMPLES = 8


def _has_colour(frame) -> bool:
    step_x = max(1, frame.width // BLANK_SAMPLES)
    step_y = max(1, frame.height // BLANK_SAMPLES)
    for x in range(0, frame.width, step_x):
        for y in range(0, frame.height, step_y):
            if tuple(frame[x, y])[:3] != (0, 0, 0):
                return True
    return False


CARRIED_HEADER = (
    ('reflectivity', 'ref'),
    ('bumpmap_scale', 'bump_scale'),
    ('low_format', 'thumb_fmt'),
    ('sheet_info', 'sheet_info'),
    ('hotspot_info', 'hotspot_info'),
    ('hotspot_flags', 'hotspot_flags'),
)


def _carried_header(source) -> dict:
    carried = {}
    for attribute, parameter in CARRIED_HEADER:
        value = getattr(source, attribute, None)
        if value is not None:
            carried[parameter] = value
    return carried


def optimize(data: bytes, max_res: int | None, to_dxt: bool = True) -> bytes | None:
    if not SRCTOOLS_AVAILABLE:
        return None

    try:
        source = VTF.read(BytesIO(data))
    except Exception:
        return None
    if source.frame_count != 1 or getattr(source, 'depth', 1) != 1:
        return None
    if _is_cubemap(source):
        return None

    width, height = _target_size(source.width, source.height, max_res)
    original = source.get(mipmap=0)
    frame = _downscale(original, width, height)
    if (frame.width, frame.height) != (width, height):
        return None
    try:
        if _has_colour(original) and not _has_colour(frame):
            return None
    except Exception:
        return None

    fmt = _target_format(source, frame, to_dxt)
    if (width, height) == (source.width, source.height) and fmt is source.format:
        return None

    result = VTF(width, height, version=source.version, fmt=fmt,
                 flags=_rebuild_flags(source, fmt), **_carried_header(source))
    result.get(mipmap=0).copy_from(frame)
    result.compute_mipmaps()

    out = BytesIO()
    result.save(out)
    return out.getvalue()
