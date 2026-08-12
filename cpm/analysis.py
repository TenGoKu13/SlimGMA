import fnmatch
import re
import struct
from pathlib import Path

from .constants import (
    VMT_TEXTURE_KEYS, VTF_FORMAT_SIZES, TEXTURE_EXTENSIONS, GMA_WHITELIST,
)


MODEL_COMPANION_SUFFIXES = (
    '.vvd', '.vtx', '.dx90.vtx', '.dx80.vtx', '.sw.vtx',
    '.phy', '.ani', '.mdl',
)


def norm_key(path: str) -> str:
    return path.replace('\\', '/').lower().lstrip('/')


def resolve_material_ref(ref: str) -> str:
    ref = ref.strip().strip('"\'').replace('\\', '/').lower().lstrip('/')
    if not ref:
        return ''
    if not ref.endswith('.vtf'):
        ref += '.vtf'
    if not ref.startswith('materials/'):
        ref = 'materials/' + ref
    return ref


_VMT_KV_RE = re.compile(r'\$(\w+)"?\s+"?([^"\r\n{}]+)"?', re.IGNORECASE)


def parse_vmt_refs(text: str) -> dict[str, str]:
    refs: dict[str, str] = {}
    for m in _VMT_KV_RE.finditer(text):
        key = m.group(1).lower()
        if key not in VMT_TEXTURE_KEYS:
            continue
        raw = m.group(2).strip()
        if not raw or raw.lower() == 'env_cubemap':
            continue
        resolved = resolve_material_ref(raw)
        if resolved:
            refs[key] = resolved
    return refs


def _read_cstr(data: bytes, offset: int, limit: int = 260) -> str:
    if offset < 0 or offset >= len(data):
        return ''
    end = data.find(b'\x00', offset, offset + limit)
    if end == -1:
        end = min(offset + limit, len(data))
    return data[offset:end].decode('latin-1', errors='replace')


def parse_mdl_materials(data: bytes) -> tuple[list[str], list[str]]:
    if len(data) < 224 or data[:4] != b'IDST':
        return [], []
    try:
        numtextures    = struct.unpack_from('<i', data, 204)[0]
        textureindex   = struct.unpack_from('<i', data, 208)[0]
        numcdtextures  = struct.unpack_from('<i', data, 212)[0]
        cdtextureindex = struct.unpack_from('<i', data, 216)[0]

        if not (0 <= numtextures < 4096 and 0 <= numcdtextures < 512):
            return [], []

        names: list[str] = []
        for i in range(numtextures):
            struct_off = textureindex + i * 64
            if struct_off + 4 > len(data):
                break
            sznameindex = struct.unpack_from('<i', data, struct_off)[0]
            name = _read_cstr(data, struct_off + sznameindex)
            if name:
                names.append(name.replace('\\', '/').strip('/').lower())

        dirs: list[str] = []
        for i in range(numcdtextures):
            ptr_off = cdtextureindex + i * 4
            if ptr_off + 4 > len(data):
                break
            str_off = struct.unpack_from('<i', data, ptr_off)[0]
            d = _read_cstr(data, str_off)
            if d:
                d = d.replace('\\', '/').lower().strip('/')
                dirs.append(d + '/' if d and not d.endswith('/') else d)
        return names, dirs
    except (struct.error, IndexError):
        return [], []


def read_vtf_info(data: bytes) -> dict | None:
    if len(data) < 63 or data[:4] != b'VTF\x00':
        return None
    try:
        ver_maj, ver_min = struct.unpack_from('<II', data, 4)
        width, height = struct.unpack_from('<HH', data, 16)
        flags = struct.unpack_from('<I', data, 20)[0]
        frames = struct.unpack_from('<H', data, 24)[0]
        high_fmt = struct.unpack_from('<i', data, 52)[0]
        mipmaps = data[56]
        fmt_name = VTF_FORMAT_SIZES.get(high_fmt, (f'UNKNOWN_{high_fmt}',))[0]
        return {
            'version': (ver_maj, ver_min),
            'width': width, 'height': height,
            'format': high_fmt, 'format_name': fmt_name,
            'mipmaps': mipmaps, 'flags': flags, 'frames': frames,
        }
    except (struct.error, IndexError):
        return None


def build_dependency_graph(files: dict) -> dict:
    keys = {k for k in files if k != '__meta__'}
    vmt_keys = {k for k in keys if k.endswith('.vmt')}
    vtf_keys = {k for k in keys if k.endswith('.vtf')}

    referenced_vtf: set[str] = set()
    for vk in vmt_keys:
        try:
            text = files[vk].decode('utf-8', errors='replace')
        except Exception:
            continue
        for resolved in parse_vmt_refs(text).values():
            referenced_vtf.add(resolved)

    referenced_vmt: set[str] = set()
    mdl_materials_parsed = False
    for mk in (k for k in keys if k.endswith('.mdl')):
        names, dirs = parse_mdl_materials(files[mk])
        if names:
            mdl_materials_parsed = True
        search_dirs = dirs or ['']
        for name in names:
            for d in search_dirs:
                cand = norm_key('materials/' + d + name + '.vmt')
                if cand in vmt_keys:
                    referenced_vmt.add(cand)
                    break
            else:
                base = name.rsplit('/', 1)[-1]
                for vk in vmt_keys:
                    if vk.rsplit('/', 1)[-1] == base + '.vmt':
                        referenced_vmt.add(vk)
                        break

    orphan_vtf = sorted(vtf_keys - referenced_vtf)
    orphan_vmt = sorted(vmt_keys - referenced_vmt) if mdl_materials_parsed else []

    reachable = set(keys)
    reachable -= set(orphan_vtf)
    reachable -= set(orphan_vmt)

    return {
        'reachable': reachable,
        'referenced_vtf': referenced_vtf,
        'referenced_vmt': referenced_vmt,
        'orphan_vtf': orphan_vtf,
        'orphan_vmt': orphan_vmt,
        'mdl_materials_parsed': mdl_materials_parsed,
    }


def find_duplicate_textures(files: dict) -> list[list[str]]:
    import hashlib
    by_hash: dict[str, list[str]] = {}
    for k, v in files.items():
        if k == '__meta__' or Path(k).suffix.lower() not in TEXTURE_EXTENSIONS:
            continue
        h = hashlib.sha1(v).hexdigest()
        by_hash.setdefault(h, []).append(k)
    return [sorted(g) for g in by_hash.values() if len(g) > 1]


VTF_UNCOMPRESSED_FORMATS = {
    'RGBA8888', 'ABGR8888', 'ARGB8888', 'BGRA8888', 'BGRX8888',
    'RGB888', 'BGR888', 'UVLX8888',
}


def is_gma_whitelisted(path: str) -> bool:
    key = norm_key(path)
    return any(fnmatch.fnmatchcase(key, pat) for pat in GMA_WHITELIST)


def check_gma_whitelist(files: dict) -> list[str]:
    return sorted(k for k in files
                  if k != '__meta__' and not is_gma_whitelisted(k))


def _vtf_ref_form(vtf_key: str) -> str:
    ref = vtf_key
    if ref.startswith('materials/'):
        ref = ref[len('materials/'):]
    if ref.endswith('.vtf'):
        ref = ref[:-4]
    return ref


def dedup_textures(files: dict) -> dict:
    referenced: set[str] = set()
    for vk in (k for k in files if k.endswith('.vmt')):
        try:
            text = files[vk].decode('utf-8', errors='replace')
        except Exception:
            continue
        referenced.update(parse_vmt_refs(text).values())

    dup_map: dict[str, str] = {}
    for group in find_duplicate_textures(files):
        vtf_group = [p for p in group if p.endswith('.vtf')]
        if len(vtf_group) < 2:
            continue
        kept = next((p for p in vtf_group if p in referenced), vtf_group[0])
        for dup in vtf_group:
            if dup != kept:
                dup_map[dup] = kept

    if not dup_map:
        return {'removed': [], 'kept': {}, 'rewritten_vmt': [], 'saved': 0}

    rewritten: list[str] = []
    for vk in [k for k in files if k.endswith('.vmt')]:
        try:
            text = files[vk].decode('utf-8', errors='replace')
        except Exception:
            continue
        pieces: list[str] = []
        last = 0
        changed = False
        for m in _VMT_KV_RE.finditer(text):
            if m.group(1).lower() not in VMT_TEXTURE_KEYS:
                continue
            resolved = resolve_material_ref(m.group(2))
            kept = dup_map.get(resolved)
            if kept is None:
                continue
            start, end = m.span(2)
            pieces.append(text[last:start])
            pieces.append(_vtf_ref_form(kept))
            last = end
            changed = True
        if changed:
            pieces.append(text[last:])
            files[vk] = ''.join(pieces).encode('utf-8')
            rewritten.append(vk)

    saved = 0
    for dup in dup_map:
        data = files.pop(dup, None)
        if data is not None:
            saved += len(data)

    return {
        'removed': sorted(dup_map),
        'kept': dict(dup_map),
        'rewritten_vmt': sorted(rewritten),
        'saved': saved,
    }


def audit_textures(files: dict, max_res: int | None = 1024) -> list[dict]:
    issues: list[dict] = []
    for k, v in files.items():
        if k == '__meta__' or not k.endswith('.vtf'):
            continue
        info = read_vtf_info(v)
        if not info:
            continue
        w, h = info['width'], info['height']
        if max_res and max(w, h) > max_res:
            issues.append({'path': k, 'issue': 'audit_oversized',
                           'detail': f"{w}×{h} > {max_res}px"})
        if info['format_name'] in VTF_UNCOMPRESSED_FORMATS:
            issues.append({'path': k, 'issue': 'audit_uncompressed',
                           'detail': info['format_name']})
        if w and h and ((w & (w - 1)) or (h & (h - 1))):
            issues.append({'path': k, 'issue': 'audit_npot',
                           'detail': f"{w}×{h}"})
    return issues
