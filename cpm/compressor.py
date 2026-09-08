import os
import struct
import json
import shutil
import zipfile
import threading
import time
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .deps import (
    PIL_AVAILABLE, Image, SRCTOOLS_AVAILABLE, FFMPEG_AVAILABLE, run_hidden,
)
from .constants import (
    VERSION, CONFIG_PATH, CHAND_PATTERNS, USELESS_EXTENSIONS, PIL_EXTENSIONS,
    TEXTURE_EXTENSIONS, SOUND_EXTENSIONS, VTF_FORMAT_SIZES, _vtf_format_size,
    VMT_TEXTURE_KEYS, TEXTURE_ROLE_KEYWORDS, NORMALMAP_HINTS, EFFECTMAP_HINTS,
)
from .i18n import t
from .gma import GMAFile
from . import vtf as vtf_tools
from .analysis import (
    norm_key, resolve_material_ref, parse_vmt_refs, parse_mdl_materials,
    read_vtf_info, build_dependency_graph, find_duplicate_textures,
    audit_textures, VTF_UNCOMPRESSED_FORMATS, check_gma_whitelist,
    dedup_textures,
)


class Compressor:
    TOTAL_STEPS = 7

    def __init__(self, opts: dict, log_fn, progress_fn, status_fn,
                 current_file_fn=None, step_fn=None):
        self.opts        = opts
        self.log         = log_fn
        self.set_progress = progress_fn
        self.set_status  = status_fn
        self.set_current_file = current_file_fn or (lambda *_: None)
        self.set_step    = step_fn or (lambda *_: None)
        self.cancel_flag = threading.Event()
        self.original_size: int | None = None
        self.final_size: int | None = None
        self.reduction: float | None = None
        self.analysis: dict = {}
        self.report: dict = {}
        self._tex_cache: dict = {}
        self.lang        = opts.get('lang', 'fr')

    def t(self, key: str, **kwargs) -> str:
        return t(key, self.lang, **kwargs)

    def cancel(self):
        self.cancel_flag.set()

    def run(self):
        if self.opts.get('batch'):
            self._run_batch()
            return

        try:
            src = Path(self.opts['source'])
            T = self.TOTAL_STEPS

            self.set_status(self.t('loading_files'))
            files = self._load_files(src)

            if not files:
                self.log(self.t('err_no_files'))
                return

            self.log(self.t('files_loaded', n=len(files)))
            original_size = sum(len(v) for v in files.values())
            self.original_size = original_size
            self.log(self.t('original_size', size=self._fmt_size(original_size)))
            self.log("")

            if self.opts.get('dry_run'):
                self.log(self.t('dry_run_active'))
                self.log("")

            self.set_step(1)
            self.log(self.t('step_chands', n=1, total=T))
            if self.opts.get('remove_chands') and not self.cancel_flag.is_set():
                self.set_status(self.t('status_chands'))
                removed = self._remove_chands(files)
                self.log(self.t('removed_n', n=removed))
            else:
                self.log(self.t('disabled'))
            self.set_progress(15)

            self.set_step(2)
            self.log(self.t('step_unused', n=2, total=T))
            if self.opts.get('remove_unused') and not self.cancel_flag.is_set():
                self.set_status(self.t('status_unused'))
                removed = self._remove_unused(files)
                self.log(self.t('removed_n', n=removed))
            else:
                self.log(self.t('disabled'))
            self.set_progress(25)

            self.set_step(3)
            self.log(self.t('step_materials', n=3, total=T))
            if self.opts.get('check_materials', True) and not self.cancel_flag.is_set():
                self.set_status(self.t('status_materials'))
                self._check_missing_textures(files)
                self._analyze_texture_usage(files)
            else:
                self.log(self.t('disabled'))
            self.set_progress(30)

            self.set_step(4)
            self.log(self.t('step_textures', n=4, total=T))
            if self.opts.get('compress_textures') and not self.cancel_flag.is_set():
                self.set_status(self.t('status_textures'))
                if self.opts.get('target_size_mb'):
                    original_files = dict(files)
                    self._run_target_size_mode(files, original_files)
                else:
                    max_res_str = self.opts.get('max_resolution', '1024')
                    quality     = self.opts.get('texture_quality', 85)
                    max_res     = int(max_res_str) if str(max_res_str).isdigit() else None
                    self._optimize_textures(files, max_res, quality)
            else:
                self.log(self.t('disabled'))
            self.set_progress(60)

            self.set_step(5)
            self.log(self.t('step_sounds', n=5, total=T))
            if self.opts.get('compress_sounds') and not self.cancel_flag.is_set():
                if FFMPEG_AVAILABLE:
                    self.set_status(self.t('status_sounds'))
                    self._compress_sounds(files)
                else:
                    self.log(self.t('ffmpeg_missing'))
            else:
                self.log(self.t('disabled'))
            self.set_progress(75)

            self.set_step(6)
            self.log(self.t('step_lua', n=6, total=T))
            if self.opts.get('gen_lua') and not self.cancel_flag.is_set():
                self.set_status(self.t('status_lua'))
                self._generate_lua(files, Path(self.opts['source']).stem)
            else:
                self.log(self.t('disabled'))
            self.set_progress(85)

            self.set_step(7)
            self.log(self.t('step_write', n=7, total=T))
            if not self.cancel_flag.is_set():
                if self.opts.get('output_format', 'folder') == 'gma':
                    self._check_gma_whitelist(files)
                self.set_status(self.t('status_write'))
                self._write_output(files, src)
            self.set_progress(100)
            self.set_current_file("")

            if not self.cancel_flag.is_set():
                final_size = sum(len(v) for v in files.values())
                reduction  = (1 - final_size / original_size) * 100 if original_size > 0 else 0
                self.final_size = final_size
                self.reduction  = reduction
                self.report     = self.build_report(files, src.stem)
                self.log("")
                self.log(self.t('final_size', size=self._fmt_size(final_size)))
                self.log(self.t('final_reduction', pct=f"{reduction:.1f}"))
                self.log(self.t('success'))
                self.set_status(self.t('status_done'))
            else:
                self.log(self.t('cancelled'))
                self.set_status(self.t('status_cancelled'))

        except Exception as e:
            import traceback
            self.log(self.t('error_generic', e=e))
            self.log(traceback.format_exc())
            self.set_status(self.t('status_error'))

    def _load_files(self, src: Path) -> dict:
        files = {}
        if self.opts.get('source_type') == 'gma':
            gma = GMAFile()
            gma.load(str(src))
            files['__meta__'] = json.dumps({
                'name': gma.name,
                'description': gma.description,
                'author': gma.author,
            }).encode()
            for name, data in gma.files.items():
                files[name.replace('\\', '/').lower()] = data
        else:
            for fp in src.rglob('*'):
                if fp.is_file():
                    key = str(fp.relative_to(src)).replace('\\', '/').lower()
                    files[key] = fp.read_bytes()
        return files

    def _remove_chands(self, files: dict) -> int:
        to_remove = []
        for path in list(files.keys()):
            if path == '__meta__':
                continue
            for pattern in CHAND_PATTERNS:
                if re.match(pattern, path, re.IGNORECASE):
                    to_remove.append(path)
                    self.log(self.t('removed_chand', path=path))
                    break
        for p in to_remove:
            del files[p]
        return len(to_remove)

    def _remove_unused(self, files: dict) -> int:
        to_remove = []
        for path in list(files.keys()):
            if path == '__meta__':
                continue
            if Path(path).suffix.lower() in USELESS_EXTENSIONS:
                to_remove.append(path)
                self.log(self.t('removed_unused_file', path=path))
        for p in to_remove:
            del files[p]
        return len(to_remove)

    @staticmethod
    def _resolve_vtf_path(ref: str) -> str:
        return resolve_material_ref(ref)

    def _check_missing_textures(self, files: dict) -> None:
        vmt_files = {k: v for k, v in files.items() if k.endswith('.vmt')}
        if not vmt_files:
            self.log(self.t('no_vmt'))
            return

        existing = set(files.keys())
        pattern = re.compile(r'\$(\w+)"?\s+"([^"]*)"', re.IGNORECASE)
        missing_total = 0
        checked = 0

        for vmt_path, data in vmt_files.items():
            if self.cancel_flag.is_set():
                break
            try:
                text = data.decode('utf-8', errors='replace')
            except Exception:
                continue
            checked += 1
            seen_refs = set()
            for m in pattern.finditer(text):
                key = m.group(1).lower()
                if key not in VMT_TEXTURE_KEYS:
                    continue
                ref = m.group(2).strip()
                if not ref or ref.lower() == 'env_cubemap':
                    continue
                tex_path = self._resolve_vtf_path(ref)
                if not tex_path or tex_path in seen_refs:
                    continue
                seen_refs.add(tex_path)
                if tex_path not in existing:
                    self.log(self.t('missing_texture', texture=tex_path, vmt=vmt_path))
                    missing_total += 1

        if missing_total == 0:
            self.log(self.t('missing_textures_none', n=checked))
        else:
            self.log(self.t('missing_textures_found', n=missing_total))

    @staticmethod
    def _classify_texture_role(path: str) -> str:
        name = path.lower()
        stem = name.rsplit('/', 1)[-1]
        stem = stem.rsplit('.', 1)[0]
        if stem.endswith(NORMALMAP_HINTS):
            return 'role_normalmap'
        if stem.endswith(EFFECTMAP_HINTS):
            return 'role_effectmap'
        for role, keywords in TEXTURE_ROLE_KEYWORDS:
            if any(kw in name for kw in keywords):
                return role
        return 'role_other'

    def _analyze_texture_usage(self, files: dict) -> None:
        tex_files = {k: v for k, v in files.items()
                     if k != '__meta__' and Path(k).suffix.lower() in TEXTURE_EXTENSIONS}
        if not tex_files:
            self.log(self.t('classify_none'))
            self.analysis = {}
            return

        by_role: dict[str, list[str]] = {}
        for path in sorted(tex_files):
            by_role.setdefault(self._classify_texture_role(path), []).append(path)

        self.log(self.t('classify_header'))
        role_order = [r for r, _ in TEXTURE_ROLE_KEYWORDS]
        role_order += ['role_normalmap', 'role_effectmap', 'role_other']
        for role in role_order:
            items = by_role.get(role)
            if not items:
                continue
            self.log(self.t('classify_line', role=self.t(role), n=len(items)))
            for path in items:
                self.log(self.t('classify_item', path=path))

        remove = self.opts.get('remove_unused_textures', False)
        graph = build_dependency_graph(files)

        if not any(k.endswith('.vmt') for k in files):
            self.log(self.t('unused_tex_no_vmt'))
            orphan_vtf = []
        else:
            orphan_vtf = graph['orphan_vtf']
            if not orphan_vtf:
                self.log(self.t('unused_tex_none'))
            else:
                size_total = sum(len(files[k]) for k in orphan_vtf)
                self.log(self.t('unused_tex_header'))
                for path in orphan_vtf:
                    size = self._fmt_size(len(files[path]))
                    key = 'unused_tex_removed' if remove else 'unused_tex_item'
                    self.log(self.t(key, path=path, size=size))
                if remove:
                    for path in orphan_vtf:
                        del files[path]
                    self.log(self.t('unused_tex_deleted', n=len(orphan_vtf),
                                     size=self._fmt_size(size_total)))
                else:
                    self.log(self.t('unused_tex_found', n=len(orphan_vtf),
                                     size=self._fmt_size(size_total)))

        orphan_vmt = graph['orphan_vmt']
        if orphan_vmt:
            size_total = sum(len(files[k]) for k in orphan_vmt if k in files)
            self.log(self.t('orphan_vmt_header'))
            for path in orphan_vmt:
                if path not in files:
                    continue
                size = self._fmt_size(len(files[path]))
                key = 'orphan_vmt_removed' if remove else 'orphan_vmt_item'
                self.log(self.t(key, path=path, size=size))
            if remove:
                for path in orphan_vmt:
                    files.pop(path, None)
                self.log(self.t('orphan_vmt_deleted', n=len(orphan_vmt),
                                 size=self._fmt_size(size_total)))
            else:
                self.log(self.t('orphan_vmt_found', n=len(orphan_vmt),
                                 size=self._fmt_size(size_total)))

        duplicates = find_duplicate_textures(files)
        dedup_result: dict = {}
        if not duplicates:
            self.log(self.t('dup_none'))
        else:
            self.log(self.t('dup_header'))
            recoverable = 0
            for group in duplicates:
                each = len(files[group[0]])
                recoverable += each * (len(group) - 1)
                self.log(self.t('dup_group', n=len(group), size=self._fmt_size(each)))
                for path in group:
                    self.log(self.t('dup_item', path=path))
            if self.opts.get('dedup_textures'):
                dedup_result = dedup_textures(files)
                for dup, kept in sorted(dedup_result['kept'].items()):
                    self.log(self.t('dedup_merged', path=dup, kept=kept))
                if dedup_result['removed']:
                    self.log(self.t('dedup_done',
                                    n=len(dedup_result['removed']),
                                    vmt=len(dedup_result['rewritten_vmt']),
                                    size=self._fmt_size(dedup_result['saved'])))
                else:
                    self.log(self.t('dedup_nothing'))
            else:
                self.log(self.t('dup_summary', groups=len(duplicates),
                                 size=self._fmt_size(recoverable)))

        max_res_str = self.opts.get('max_resolution', '1024')
        max_res = int(max_res_str) if str(max_res_str).isdigit() else None
        issues = audit_textures(files, max_res)
        if not issues:
            self.log(self.t('audit_none'))
        else:
            self.log(self.t('audit_header'))
            for it in issues:
                self.log(self.t(it['issue'], path=it['path'], detail=it['detail']))
            self.log(self.t('audit_summary', n=len(issues)))

        self.analysis = {
            'roles': {r: list(by_role.get(r, [])) for r in role_order if by_role.get(r)},
            'orphan_vtf': list(orphan_vtf),
            'orphan_vmt': list(orphan_vmt),
            'duplicates': duplicates,
            'dedup': dedup_result,
            'audit': issues,
            'removed': remove,
        }

    def reduction_label(self) -> str:
        if self.reduction is None:
            return '—'
        return f"{'-' if self.reduction >= 0 else '+'}{abs(self.reduction):.1f}%"

    def build_report(self, files: dict, addon_name: str) -> dict:
        a = self.analysis or {}
        return {
            'addon': addon_name,
            'removed': a.get('removed', False),
            'summary': {
                'original': self._fmt_size(self.original_size or 0),
                'final': self._fmt_size(self.final_size or 0),
                'reduction': self.reduction_label(),
                'files': str(sum(1 for k in files if k != '__meta__')),
            },
            'roles': [(role, list(items)) for role, items in a.get('roles', {}).items()],
            'orphans': list(a.get('orphan_vtf', [])) + list(a.get('orphan_vmt', [])),
            'duplicates': [list(g) for g in a.get('duplicates', [])],
            'audit': [{'path': it['path'], 'issue': it['issue'],
                       'detail': it['detail']} for it in a.get('audit', [])],
        }

    def _optimize_textures(self, files: dict, max_res, quality: int, quiet: bool = False) -> None:
        tex_files = {k: v for k, v in files.items()
                     if Path(k).suffix.lower() in TEXTURE_EXTENSIONS and k != '__meta__'}

        if not tex_files:
            if not quiet:
                self.log(self.t('no_textures'))
            return

        workers = max(1, min(8, os.cpu_count() or 2))
        if not quiet:
            self.log(self.t('textures_found', n=len(tex_files)))
            if max_res is None:
                self.log(self.t('no_res_limit'))
            elif not SRCTOOLS_AVAILABLE:
                self.log(self.t('no_srctools', max_res=max_res))
            if workers > 1 and len(tex_files) > 1:
                self.log(self.t('textures_parallel', n=workers))

        total = len(tex_files)
        reduced = 0
        unchanged_vtf = 0
        done = 0

        def process_one(path: str, data: bytes):
            ext = Path(path).suffix.lower()
            cache_key = (hash(data), len(data), ext, max_res, quality)
            if cache_key in self._tex_cache:
                return path, self._tex_cache[cache_key], None
            new_data = None
            err = None
            try:
                if ext == '.vtf':
                    new_data = self._process_vtf(path, data, max_res, quality)
                elif PIL_AVAILABLE and ext in PIL_EXTENSIONS:
                    new_data = self._process_image_pil(path, data, ext, max_res, quality)
            except Exception as e:
                new_data = None
                err = e
            self._tex_cache[cache_key] = new_data
            return path, new_data, err

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(process_one, path, data)
                       for path, data in tex_files.items()]
            for fut in futures:
                if self.cancel_flag.is_set():
                    pool.shutdown(wait=False, cancel_futures=True)
                    break
                path, new_data, err = fut.result()
                data = tex_files[path]
                if err is not None and not quiet:
                    self.log(self.t('texture_error', path=path, e=err))
                if new_data and len(new_data) < len(data):
                    savings = len(data) - len(new_data)
                    if not quiet:
                        self.log(self.t('texture_saving', path=path, size=self._fmt_size(savings)))
                    files[path] = new_data
                    reduced += 1
                elif Path(path).suffix.lower() == '.vtf':
                    unchanged_vtf += 1
                done += 1
                if not quiet:
                    self.set_current_file(path)
                    self.set_progress(30 + (done / total) * 30)

        if not quiet:
            self.log(self.t('textures_reduced', reduced=reduced, total=total))
            if unchanged_vtf:
                self.log(self.t('vtf_unchanged', n=unchanged_vtf))

    def _quality_changes_anything(self, files: dict) -> bool:
        return any(Path(k).suffix.lower() in PIL_EXTENSIONS
                   for k in files if k != '__meta__')

    def _target_size_steps(self, files: dict) -> list[tuple[int | None, int]]:
        max_res_str = self.opts.get('max_resolution', '1024')
        quality     = int(self.opts.get('texture_quality', 85))
        base_res    = int(max_res_str) if str(max_res_str).isdigit() else None

        all_res = [2048, 1024, 512, 256, 128]
        res_list = [r for r in all_res if base_res is None or r <= base_res]
        if base_res is not None and base_res not in res_list:
            res_list.insert(0, base_res)
        if not res_list:
            res_list = [128]

        if self._quality_changes_anything(files):
            qual_list = sorted({q for q in (quality, 75, 60, 45, 30)
                                if 10 <= q <= 100}, reverse=True)
        else:
            qual_list = [quality]

        steps: list[tuple[int | None, int]] = []
        for res in res_list:
            for q in qual_list:
                if (res, q) not in steps:
                    steps.append((res, q))
        return steps

    def _run_target_size_mode(self, files: dict, original_files: dict) -> None:
        target_bytes = int(self.opts['target_size_mb'] * 1024 * 1024)
        self.log(self.t('step_target_size', size=self._fmt_size(target_bytes)))

        steps = self._target_size_steps(original_files)
        chosen = steps[-1]
        chosen_size = None

        for i, (res, quality) in enumerate(steps, 1):
            if self.cancel_flag.is_set():
                return
            trial = dict(original_files)
            self._optimize_textures(trial, res, quality, quiet=True)
            size = sum(len(v) for v in trial.values())
            res_label = f"{res}px" if res else self.t('no_limit')
            self.log(self.t('target_attempt', n=i, res=res_label, q=quality, size=self._fmt_size(size)))
            chosen, chosen_size = (res, quality), size
            if size <= target_bytes:
                break

        files.clear()
        files.update(original_files)
        self._optimize_textures(files, chosen[0], chosen[1])

        if chosen_size is not None and chosen_size <= target_bytes:
            self.log(self.t('target_reached', size=self._fmt_size(chosen_size), target=self._fmt_size(target_bytes)))
        else:
            self.log(self.t('target_not_reached', size=self._fmt_size(chosen_size or 0), target=self._fmt_size(target_bytes)))

    def _process_vtf(self, path: str, data: bytes, max_res, quality: int) -> bytes:
        if SRCTOOLS_AVAILABLE:
            try:
                rebuilt = vtf_tools.optimize(
                    data, max_res, self.opts.get('convert_uncompressed', True))
                if rebuilt:
                    return rebuilt
            except Exception:
                pass
        return self._process_vtf_mipstrip(data, max_res)

    def _process_vtf_mipstrip(self, data: bytes, max_res) -> bytes:
        if max_res is None:
            return data
        try:
            if data[:4] != b'VTF\x00' or len(data) < 80:
                return data

            ver_maj, ver_min, header_size = struct.unpack_from('<III', data, 4)
            if ver_maj != 7:
                return data

            width, height = struct.unpack_from('<HH', data, 16)
            flags = struct.unpack_from('<I', data, 20)[0]
            frames = struct.unpack_from('<H', data, 24)[0]
            high_fmt = struct.unpack_from('<i', data, 52)[0]
            mipmap_count = data[56]
            low_fmt = struct.unpack_from('<i', data, 57)[0]
            low_w, low_h = data[61], data[62]

            TEXTUREFLAGS_ENVMAP = 0x4000
            if frames != 1 or (flags & TEXTUREFLAGS_ENVMAP):
                return data
            if width == 0 or height == 0 or mipmap_count <= 1:
                return data
            if max(width, height) <= max_res:
                return data
            if high_fmt not in VTF_FORMAT_SIZES:
                return data

            depth = 1
            if (ver_maj, ver_min) >= (7, 2) and len(data) >= 65:
                depth = struct.unpack_from('<H', data, 63)[0] or 1
            if depth != 1:
                return data

            if (ver_maj, ver_min) >= (7, 3):
                if len(data) < 72:
                    return data
                num_res = struct.unpack_from('<I', data, 68)[0]
                high_res_offset = None
                for i in range(num_res):
                    off = 72 + i * 8
                    if off + 8 > len(data):
                        return data
                    tag = data[off:off + 3]
                    if tag == b'\x30\x00\x00':
                        high_res_offset = struct.unpack_from('<I', data, off + 4)[0]
                if high_res_offset is None:
                    return data
            else:
                low_size = 0
                if low_fmt != -1 and low_w and low_h:
                    low_size = _vtf_format_size(low_fmt, low_w, low_h) or 0
                high_res_offset = header_size + low_size

            if high_res_offset >= len(data):
                return data

            mip_sizes = []
            for m in range(mipmap_count - 1, -1, -1):
                mw = max(1, width >> m)
                mh = max(1, height >> m)
                sz = _vtf_format_size(high_fmt, mw, mh)
                if sz is None:
                    return data
                mip_sizes.append((m, mw, mh, sz))

            total_high_res = len(data) - high_res_offset
            if sum(s for _, _, _, s in mip_sizes) != total_high_res:
                return data

            keep = 0
            target = None
            for m, mw, mh, sz in mip_sizes:
                if max(mw, mh) > max_res:
                    break
                keep += sz
                target = (m, mw, mh, keep)

            if target is None or target[0] == 0:
                return data

            new_mip_level, new_w, new_h, new_high_res_size = target
            new_mipmap_count = mipmap_count - new_mip_level

            out = bytearray(data[:high_res_offset + new_high_res_size])
            struct.pack_into('<HH', out, 16, new_w, new_h)
            out[56] = new_mipmap_count
            return bytes(out)

        except (struct.error, IndexError):
            return data

    def _process_image_pil(self, path: str, data: bytes, ext: str,
                            max_res, quality: int) -> bytes:
        try:
            import io
            img = Image.open(io.BytesIO(data))
            if max_res and (img.width > max_res or img.height > max_res):
                img.thumbnail((max_res, max_res), Image.LANCZOS)
            buf = io.BytesIO()
            if ext in ('.jpg', '.jpeg'):
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')
                img.save(buf, format='JPEG', quality=quality, optimize=True)
            elif ext == '.png':
                compress_level = max(0, min(9, int((100 - quality) / 11)))
                img.save(buf, format='PNG', compress_level=compress_level, optimize=True)
            elif ext == '.tga':
                img.save(buf, format='TGA', compression='tga_rle')
            elif ext == '.bmp':
                img.save(buf, format='BMP')
            else:
                return data
            return buf.getvalue()
        except Exception:
            return data

    _SOUND_ENCODERS = {
        '.mp3': lambda bitrate: ['-c:a', 'libmp3lame', '-b:a', bitrate],
        '.ogg': lambda bitrate: ['-c:a', 'libvorbis', '-b:a', bitrate],
        '.wav': lambda bitrate: ['-c:a', 'pcm_s16le', '-ar', '22050'],
    }

    def _compress_sounds(self, files: dict) -> None:
        bitrate = self.opts.get('sound_quality', '128k')
        snd_files = {k: v for k, v in files.items()
                     if Path(k).suffix.lower() in SOUND_EXTENSIONS and k != '__meta__'}

        if not snd_files:
            self.log(self.t('no_sounds'))
            return

        self.log(self.t('sounds_found', n=len(snd_files)))

        for path, data in snd_files.items():
            if self.cancel_flag.is_set():
                break
            self.set_current_file(path)
            ext = Path(path).suffix.lower()
            encoder = self._SOUND_ENCODERS.get(ext)
            if encoder is None:
                self.log(self.t('sound_skipped_format', path=path))
                continue
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tf:
                tf.write(data)
                tmp_in = tf.name
            tmp_out = tmp_in + '.out' + ext
            try:
                result = run_hidden(
                    ['ffmpeg', '-y', '-i', tmp_in, *encoder(bitrate),
                     '-map_metadata', '-1', tmp_out],
                    capture_output=True, timeout=60,
                )
                if result.returncode == 0:
                    new_data = Path(tmp_out).read_bytes()
                    if len(new_data) < len(data):
                        files[path] = new_data
                        savings = len(data) - len(new_data)
                        self.log(self.t('sound_saving', path=path, size=self._fmt_size(savings)))
            except Exception as e:
                self.log(self.t('sound_error', path=path, e=e))
            finally:
                for tmp in (tmp_in, tmp_out):
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass

    def _generate_lua(self, files: dict, addon_stem: str) -> None:
        def is_mdl(p):
            return (p.startswith('models/') and p.endswith('.mdl')
                    and not p.startswith('models/weapons/')
                    and not re.search(r'_lod\d+\.mdl$', p))

        all_mdls = sorted(p for p in files if is_mdl(p))
        pm_models = [p for p in all_mdls if p.startswith('models/player/')]

        if not pm_models and all_mdls:
            self.log(self.t('lua_no_models_player'))
            pm_models = all_mdls

        if not pm_models:
            self.log(self.t('lua_no_models'))
            return

        for p in pm_models:
            self.log(self.t('lua_model_detected', path=p))

        self.log(self.t('lua_models_found', n=len(pm_models)))

        chand_mdls = [
            p for p in files
            if re.match(r'models/weapons/c_.*\.mdl', p, re.IGNORECASE)
        ]
        include_chands = self.opts.get('lua_chands', True) and bool(chand_mdls)

        existing_path: str | None = None
        for path, data in files.items():
            if not path.endswith('.lua'):
                continue
            try:
                if b'AddValidModel' in data or b'player_manager' in data:
                    existing_path = path
                    break
            except Exception:
                pass

        safe_stem = re.sub(r'[^a-z0-9]', '_', addon_stem.lower()).strip('_') or 'pm'
        lines: list[str] = []

        for mdl in pm_models:
            display = Path(mdl).stem.replace('_', ' ').replace('-', ' ').title()
            block = [
                'do',
                f'    local name = "{display}"',
                f'    local mdl  = "{mdl}"',
                '    player_manager.AddValidModel(name, mdl)',
                '    list.Set("PlayerOptionsModel", name, mdl)',
            ]

            if include_chands:
                stem = Path(mdl).stem.lower()
                match = next(
                    (c for c in chand_mdls
                     if stem in c or c.replace('models/weapons/c_arms_', '').split('.')[0] in stem),
                    chand_mdls[0] if chand_mdls else None,
                )
                if match:
                    block.append(
                        f'    player_manager.AddValidHands(name, "{match}", 0, "00000000")')

            block += ['end', '']
            lines += block

        if include_chands:
            self.log(self.t('lua_hands_registered', n=len(chand_mdls)))

        lua_bytes = '\n'.join(lines).encode('utf-8')

        if existing_path:
            files[existing_path] = lua_bytes
            self.log(self.t('lua_updated', path=existing_path))
        else:
            new_path = f'lua/autorun/sh_{safe_stem}_pm.lua'
            files[new_path] = lua_bytes
            self.log(self.t('lua_created', path=new_path))

    def _check_gma_whitelist(self, files: dict) -> None:
        bad = check_gma_whitelist(files)
        if not bad:
            self.log(self.t('whitelist_none'))
            return
        self.log(self.t('whitelist_header'))
        strip = self.opts.get('strip_non_whitelisted', False)
        for path in bad:
            if strip:
                del files[path]
                self.log(self.t('whitelist_stripped', path=path))
            else:
                self.log(self.t('whitelist_bad', path=path))
        if strip:
            self.log(self.t('whitelist_stripped_total', n=len(bad)))
        else:
            self.log(self.t('whitelist_found', n=len(bad)))

    @staticmethod
    def _resolve_output_path(output: Path, fmt: str) -> Path:
        if fmt == 'gma':
            return output if output.suffix == '.gma' else output.with_suffix('.gma')
        if fmt == 'zip':
            return output if output.suffix == '.zip' else output.with_suffix('.zip')
        return output

    def _backup_existing(self, output: Path, fmt: str) -> None:
        target = self._resolve_output_path(output, fmt)
        if not target.exists():
            return

        timestamp = time.strftime('%Y%m%d_%H%M%S')
        try:
            if target.is_dir():
                backup_path = target.parent / f"{target.name}_backup_{timestamp}"
                shutil.copytree(target, backup_path)
            else:
                backup_path = target.with_name(f"{target.stem}_backup_{timestamp}{target.suffix}")
                shutil.copy2(target, backup_path)
            self.log(self.t('backup_created', path=backup_path))
        except Exception as e:
            self.log(self.t('backup_failed', e=e))

    def _write_output(self, files: dict, src: Path) -> None:
        output = Path(self.opts['output'])
        fmt    = self.opts.get('output_format', 'folder')

        meta = None
        if '__meta__' in files:
            try:
                meta = json.loads(files['__meta__'].decode())
            except Exception:
                pass
        out_files = {k: v for k, v in files.items() if k != '__meta__'}

        if self.opts.get('dry_run'):
            if self.opts.get('in_place'):
                self.log(self.t('dry_run_would_replace', path=output))
                return
            if fmt == 'folder':
                self.log(self.t('dry_run_would_write_folder', path=output, n=len(out_files)))
            elif fmt == 'gma':
                self.log(self.t('dry_run_would_write_gma', path=self._resolve_output_path(output, fmt)))
            elif fmt == 'zip':
                self.log(self.t('dry_run_would_write_zip', path=self._resolve_output_path(output, fmt)))
            return

        in_place = bool(self.opts.get('in_place'))
        destination = output if fmt == 'folder' else self._resolve_output_path(output, fmt)

        if in_place:
            staging = self._staging_path(destination)
            try:
                self._write_payload(out_files, staging, fmt, meta, src)
                self._swap_into_place(staging, destination)
            finally:
                self._discard(staging)
            self.log(self.t('write_in_place', path=destination))
            return

        if self.opts.get('backup_original'):
            self._backup_existing(output, fmt)
        self._write_payload(out_files, destination, fmt, meta, src)

    def _staging_path(self, destination: Path) -> Path:
        return self._unique_path(destination.parent /
                                 (destination.name + '.slimgma-tmp'))

    @staticmethod
    def _unique_path(candidate: Path) -> Path:
        path, index = candidate, 1
        while path.exists():
            path = candidate.with_name(f"{candidate.name}{index}")
            index += 1
        return path

    @staticmethod
    def _discard(path: Path) -> None:
        try:
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
        except OSError:
            pass

    def _swap_into_place(self, staging: Path, destination: Path) -> None:
        previous = None
        if destination.exists():
            previous = self._unique_path(
                destination.parent / (destination.name + '.slimgma-old'))
            os.replace(destination, previous)
        try:
            os.replace(staging, destination)
        except OSError:
            if previous is not None:
                os.replace(previous, destination)
            raise
        if previous is None:
            return
        if self.opts.get('backup_original'):
            kept = self._unique_path(destination.with_name(
                f"{destination.stem}_backup_{time.strftime('%Y%m%d_%H%M%S')}"
                f"{destination.suffix}"))
            os.replace(previous, kept)
            self.log(self.t('backup_created', path=kept))
        else:
            self._discard(previous)

    def _write_payload(self, out_files: dict, destination: Path, fmt: str,
                       meta: dict | None, src: Path) -> None:
        if fmt == 'folder':
            if 'addon.json' not in out_files and self.opts.get('gen_addon_json', True):
                title = (meta or {}).get('name') or src.stem
                addon_info = {'title': title, 'type': 'model',
                              'tags': ['fun'], 'ignore': []}
                desc = (meta or {}).get('description')
                if desc:
                    addon_info['description'] = desc
                out_files['addon.json'] = json.dumps(
                    addon_info, indent=4, ensure_ascii=False).encode('utf-8')
                self.log(self.t('addon_json_created', title=title))
            destination.mkdir(parents=True, exist_ok=True)
            for path, data in out_files.items():
                target = destination / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            self.log(self.t('write_folder', path=destination))

        elif fmt == 'gma':
            gma = GMAFile()
            if meta:
                gma.name        = meta.get('name', src.stem)
                gma.description = meta.get('description', '')
                gma.author      = meta.get('author', '')
            else:
                gma.name = src.stem
                if 'addon.json' in out_files:
                    try:
                        info = json.loads(out_files['addon.json'].decode())
                        gma.name        = info.get('title', src.stem)
                        gma.description = info.get('description', '')
                    except Exception:
                        pass
            gma.files = out_files
            destination.parent.mkdir(parents=True, exist_ok=True)
            gma.save(str(destination))
            self.log(self.t('write_gma', path=destination))

        elif fmt == 'zip':
            destination.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(str(destination), 'w', zipfile.ZIP_DEFLATED,
                                 compresslevel=self.opts.get('zip_level', 6)) as zf:
                for path, data in out_files.items():
                    zf.writestr(path, data)
            self.log(self.t('write_zip', path=destination))

    def _run_batch(self) -> None:
        src = Path(self.opts['source'])

        addons: list[tuple[str, Path]] = []
        if src.is_dir():
            for item in sorted(src.iterdir()):
                if item.is_dir():
                    addons.append(('folder', item))
                elif item.suffix.lower() == '.gma':
                    addons.append(('gma', item))

        if not addons:
            self.log(self.t('batch_none'))
            return

        self.log(self.t('batch_found', n=len(addons), path=src))
        self.log("")

        output_root = Path(self.opts['output'])
        fmt = self.opts.get('output_format', 'folder')
        n = len(addons)
        results: list[tuple[str, int, float]] = []

        for i, (stype, path) in enumerate(addons, 1):
            if self.cancel_flag.is_set():
                break

            name = path.stem
            self.log(self.t('batch_processing', i=i, n=n, name=name))

            sub_opts = dict(self.opts)
            sub_opts['source'] = str(path)
            sub_opts['source_type'] = stype
            sub_opts['batch'] = False
            if self.opts.get('in_place'):
                sub_opts['output'] = str(path)
                sub_opts['output_format'] = 'gma' if stype == 'gma' else 'folder'
            elif fmt == 'folder':
                sub_opts['output'] = str(output_root / name)
            else:
                ext = '.gma' if fmt == 'gma' else '.zip'
                sub_opts['output'] = str(output_root / (name + ext))

            def progress_wrap(v, i=i):
                self.set_progress((i - 1 + v / 100) / n * 100)

            sub = Compressor(
                sub_opts,
                log_fn=self.log,
                progress_fn=progress_wrap,
                status_fn=self.set_status,
                current_file_fn=self.set_current_file,
            )
            sub.run()
            if sub.final_size is not None:
                results.append(sub)
            self.log("")

        self.set_progress(100)
        self.set_current_file("")

        if results:
            self.log(self.t('batch_summary_header'))
            for sub in results:
                self.log(self.t('batch_summary_line',
                                name=Path(sub.opts['source']).stem,
                                size=self._fmt_size(sub.final_size),
                                pct=f"{sub.reduction or 0.0:.1f}"))
            self.log("")
            self._aggregate_batch(src, results)

        self.log(self.t('batch_done', n=len(results)))
        self.set_status(self.t('status_done'))

    def _aggregate_batch(self, src: Path, results: list) -> None:
        self.original_size = sum(s.original_size or 0 for s in results)
        self.final_size = sum(s.final_size or 0 for s in results)
        self.reduction = ((1 - self.final_size / self.original_size) * 100
                          if self.original_size else 0.0)
        self.report = {
            'addon': src.name,
            'removed': False,
            'summary': {
                'original': self._fmt_size(self.original_size),
                'final': self._fmt_size(self.final_size),
                'reduction': self.reduction_label(),
                'files': str(sum(int(s.report.get('summary', {}).get('files', 0) or 0)
                                 for s in results)),
            },
            'roles': [], 'orphans': [], 'duplicates': [], 'audit': [],
            'batch': [{'name': Path(s.opts['source']).stem,
                       'size': self._fmt_size(s.final_size),
                       'delta': s.reduction_label()} for s in results],
        }

    @staticmethod
    def _fmt_size(n: int) -> str:
        if n < 1024:
            return f"{n} o"
        for unit in ['Ko', 'Mo', 'Go']:
            n /= 1024
            if n < 1024:
                return f"{n:.1f} {unit}"
        return f"{n / 1024:.1f} To"
