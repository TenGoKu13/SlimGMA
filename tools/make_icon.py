import sys
from pathlib import Path

from PIL import Image, ImageDraw

SIZES = (16, 24, 32, 48, 64, 128, 256)
CANVAS = 1024
BG = (77, 108, 255, 255)
BG_DEEP = (53, 89, 224, 255)
GLYPH = (255, 255, 255, 255)


def rounded_square(size: int, radius: int) -> Image.Image:
    gradient = Image.new('RGB', (1, size))
    pen = ImageDraw.Draw(gradient)
    for row in range(size):
        ratio = row / max(1, size - 1)
        pen.point((0, row), fill=tuple(
            round(BG[band] + (BG_DEEP[band] - BG[band]) * ratio)
            for band in range(3)))
    plate = gradient.resize((size, size)).convert('RGBA')

    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=radius, fill=255)
    plate.putalpha(mask)
    return plate


def draw_glyph(plate: Image.Image) -> None:
    size = plate.width
    pen = ImageDraw.Draw(plate)
    unit = size / 32
    mid = size / 2
    half_gap = 1.6 * unit
    bar = 2.2 * unit
    inset = 7.0 * unit
    wing = 5.4 * unit
    tip = 4.4 * unit

    pen.rectangle((inset, mid - half_gap - bar, size - inset, mid - half_gap),
                  fill=GLYPH)
    pen.rectangle((inset, mid + half_gap, size - inset, mid + half_gap + bar),
                  fill=GLYPH)

    top = mid - half_gap - bar
    pen.polygon([(mid - wing, top - tip - 1.4 * unit),
                 (mid + wing, top - tip - 1.4 * unit),
                 (mid, top - 1.4 * unit)], fill=GLYPH)

    bottom = mid + half_gap + bar
    pen.polygon([(mid - wing, bottom + tip + 1.4 * unit),
                 (mid + wing, bottom + tip + 1.4 * unit),
                 (mid, bottom + 1.4 * unit)], fill=GLYPH)


def render(size: int) -> Image.Image:
    scale = 4
    big = size * scale
    plate = rounded_square(big, radius=int(big * 0.22))
    draw_glyph(plate)
    return plate.resize((size, size), Image.LANCZOS)


def main() -> int:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else 'assets/slimgma.ico')
    target.parent.mkdir(parents=True, exist_ok=True)
    layers = [render(size) for size in SIZES]
    layers[-1].save(target, format='ICO',
                    sizes=[(size, size) for size in SIZES])
    preview = target.with_suffix('.png')
    render(256).save(preview)
    print(f"{target} ({', '.join(str(s) for s in SIZES)})")
    print(preview)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
