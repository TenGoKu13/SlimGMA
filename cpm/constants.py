import os
import sys
from pathlib import Path


APP_NAME = "Slimgma"
VERSION = "1.3.0"
LICENSE_NAME = "MIT"
REPO_URL = "https://github.com/TenGoKu13/SlimGMA"

LEGACY_CONFIG_DIR = 'CompressezPMGMod'


def _config_base() -> Path:
    if sys.platform == 'win32':
        return Path(os.environ.get('APPDATA', Path.home()))
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))


CONFIG_PATH = _config_base() / APP_NAME / 'config.json'
LEGACY_CONFIG_PATH = _config_base() / LEGACY_CONFIG_DIR / 'config.json'

CHAND_PATTERNS = [
    r"models/weapons/c_.*",
    r"materials/models/weapons/c_.*",
    r"models/weapons/cstrike/c_.*",
    r"materials/models/weapons/cstrike/c_.*",
    r"models/weapons/v_.*_c\..*",
]

USELESS_EXTENSIONS = {
    '.txt', '.md', '.pdf', '.doc', '.docx', '.nfo', '.log',
    '.bat', '.sh', '.psd', '.xcf', '.ai', '.eps',
}

TEXTURE_EXTENSIONS = {'.vtf', '.png', '.jpg', '.jpeg', '.tga', '.bmp'}

PIL_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tga', '.bmp'}

SOUND_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.flac', '.aif', '.aiff'}

VTF_FORMAT_SIZES = {
    0:  ('RGBA8888', 4, False),
    1:  ('ABGR8888', 4, False),
    2:  ('RGB888', 3, False),
    3:  ('BGR888', 3, False),
    4:  ('RGB565', 2, False),
    5:  ('I8', 1, False),
    6:  ('IA88', 2, False),
    7:  ('P8', 1, False),
    8:  ('A8', 1, False),
    9:  ('RGB888_BLUESCREEN', 3, False),
    10: ('BGR888_BLUESCREEN', 3, False),
    11: ('ARGB8888', 4, False),
    12: ('BGRA8888', 4, False),
    13: ('DXT1', 8, True),
    14: ('DXT3', 16, True),
    15: ('DXT5', 16, True),
    16: ('BGRX8888', 4, False),
    17: ('BGR565', 2, False),
    18: ('BGRX5551', 2, False),
    19: ('BGRA4444', 2, False),
    20: ('DXT1_ONEBITALPHA', 8, True),
    21: ('BGRA5551', 2, False),
    22: ('UV88', 2, False),
    23: ('UVWQ8888', 4, False),
    24: ('RGBA16161616F', 8, False),
    25: ('RGBA16161616', 8, False),
    26: ('UVLX8888', 4, False),
    27: ('R32F', 4, False),
    28: ('RGB323232F', 12, False),
    29: ('RGBA32323232F', 16, False),
}


def _vtf_format_size(fmt: int, w: int, h: int) -> int | None:
    info = VTF_FORMAT_SIZES.get(fmt)
    if info is None:
        return None
    _, unit, is_block = info
    if is_block:
        bw = max(1, (w + 3) // 4)
        bh = max(1, (h + 3) // 4)
        return bw * bh * unit
    return w * h * unit


VMT_TEXTURE_KEYS = {
    'basetexture', 'basetexture2', 'bumpmap', 'bumpmap2', 'normalmap',
    'normalmap2', 'envmapmask', 'detail', 'blendmodulatetexture',
    'phongexponenttexture', 'phongwarptexture', 'lightwarptexture',
    'selfillummask', 'ambientocclusiontexture', 'tooltexture', 'texture2',
    'iris', 'corneatexture', 'displacementmap', 'blendmask',
}

TEXTURE_ROLE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ('role_eye_effect', ('eyeglow', 'eyeball', 'glowing_eye', 'eye_glow')),
    ('role_eyes',       ('eye', 'iris', 'cornea', 'oeil', 'yeux', 'pupil')),
    ('role_helmet',     ('helmet', 'casque', 'hat', 'chapeau', 'cap', 'mask', 'masque', 'hood', 'capuche')),
    ('role_hair',       ('hair', 'cheveux', 'beard', 'barbe', 'brow', 'lash', 'sourcil')),
    ('role_mouth',      ('mouth', 'teeth', 'tooth', 'bouche', 'dent', 'tongue', 'langue', 'lip', 'levre')),
    ('role_head',       ('head', 'face', 'tete', 'visage', 'skin_head', 'faceskin')),
    ('role_hands',      ('hand', 'arm', 'glove', 'main', 'bras', 'gant', 'c_arms', 'fist', 'finger')),
    ('role_legs',       ('leg', 'foot', 'feet', 'boot', 'shoe', 'pant', 'jambe', 'pied', 'botte', 'chaussure', 'thigh')),
    ('role_body',       ('body', 'torso', 'chest', 'corps', 'torse', 'suit', 'shirt', 'jacket', 'vest', 'cloth', 'outfit', 'skin')),
    ('role_accessory',  ('accessor', 'bag', 'belt', 'ceinture', 'strap', 'pouch', 'badge', 'patch', 'weapon', 'gun')),
]

NORMALMAP_HINTS = ('_normal', '_n', '_nrm', '_bump', '_ddn')
EFFECTMAP_HINTS = ('_phong', '_spec', '_exp', '_gloss', '_ao', '_mask', '_illum', '_detail')

GMA_WHITELIST = (
    'addon.json',
    'lua/*.lua',
    'scenes/*.vcd',
    'particles/*.pcf',
    'resource/fonts/*.ttf',
    'scripts/vehicles/*.txt',
    'resource/localization/*/*.properties',
    'maps/*.bsp',
    'maps/*.lmp',
    'maps/*.nav',
    'maps/*.ain',
    'maps/thumb/*.png',
    'sound/*.wav',
    'sound/*.mp3',
    'sound/*.ogg',
    'materials/*.vmt',
    'materials/*.vtf',
    'materials/*.png',
    'materials/*.jpg',
    'materials/*.jpeg',
    'materials/colorcorrection/*.raw',
    'models/*.mdl',
    'models/*.phy',
    'models/*.ani',
    'models/*.vvd',
    'models/*.vtx',
    'gamemodes/*/*.txt',
    'gamemodes/*/*.fgd',
    'gamemodes/*/logo.png',
    'gamemodes/*/icon24.png',
    'gamemodes/*/gamemode/*.lua',
    'gamemodes/*/entities/effects/*.lua',
    'gamemodes/*/entities/weapons/*.lua',
    'gamemodes/*/entities/entities/*.lua',
    'gamemodes/*/backgrounds/*.png',
    'gamemodes/*/content/models/*.mdl',
    'gamemodes/*/content/models/*.phy',
    'gamemodes/*/content/models/*.ani',
    'gamemodes/*/content/models/*.vvd',
    'gamemodes/*/content/models/*.vtx',
    'gamemodes/*/content/materials/*.vmt',
    'gamemodes/*/content/materials/*.vtf',
    'gamemodes/*/content/materials/*.png',
    'gamemodes/*/content/materials/*.jpg',
    'gamemodes/*/content/materials/*.jpeg',
    'gamemodes/*/content/scenes/*.vcd',
    'gamemodes/*/content/particles/*.pcf',
    'gamemodes/*/content/resource/fonts/*.ttf',
    'gamemodes/*/content/scripts/vehicles/*.txt',
    'gamemodes/*/content/resource/localization/*/*.properties',
    'gamemodes/*/content/maps/*.bsp',
    'gamemodes/*/content/maps/*.nav',
    'gamemodes/*/content/maps/*.ain',
    'gamemodes/*/content/maps/thumb/*.png',
    'gamemodes/*/content/sound/*.wav',
    'gamemodes/*/content/sound/*.mp3',
    'gamemodes/*/content/sound/*.ogg',
    'data_static/*.txt',
    'data_static/*.dat',
    'data_static/*.json',
    'data_static/*.xml',
    'data_static/*.csv',
)
