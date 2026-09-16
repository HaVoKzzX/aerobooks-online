"""App and setup icons from the gold flight_takeoff mark.

App shortcut: navy tile + gold takeoff icon.
Setup.exe: the same tile with a small gear in the corner.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FONT = ROOT / "aerobooks" / "assets" / "MaterialIcons-Regular.ttf"
APP_ICO = HERE / "aerobooks.ico"
SETUP_ICO = HERE / "aerobooks-setup.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]

NAVY = (27, 54, 93, 255)
NAVY_DEEP = (16, 35, 63, 255)
GOLD = (196, 163, 90, 255)
GOLD_LIGHT = (232, 197, 106, 255)
TAKEOFF = "\ue905"
GEAR = "\ue8b8"


def _font(px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT), px)


def _glyph(ch: str, size: int, fill: tuple[int, int, int, int], font_px: int | None = None) -> Image.Image:
    scale = 4
    canvas = size * scale
    im = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    font = _font(font_px * scale if font_px else int(canvas * 0.86))
    bbox = draw.textbbox((0, 0), ch, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (canvas - w) / 2 - bbox[0]
    y = (canvas - h) / 2 - bbox[1]
    draw.text((x, y), ch, font=font, fill=fill)
    return im.resize((size, size), Image.Resampling.LANCZOS)


def _tile(size: int) -> Image.Image:
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    m = max(1, round(size / 18))
    d.rounded_rectangle(
        [m, m, size - m - 1, size - m - 1],
        radius=max(2, size // 6),
        fill=NAVY,
    )
    return im


def app_icon(size: int) -> Image.Image:
    tile = _tile(size)
    plane = _glyph(TAKEOFF, size, GOLD, font_px=max(10, int(size * 0.62)))
    return Image.alpha_composite(tile, plane)


def setup_icon(size: int) -> Image.Image:
    tile = _tile(size)
    plane = _glyph(TAKEOFF, size, GOLD, font_px=max(10, int(size * 0.56)))
    shifted = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shifted.paste(plane, (-max(0, size // 22), -max(1, size // 16)), plane)
    base = Image.alpha_composite(tile, shifted)
    if size < 20:
        d = ImageDraw.Draw(base)
        r = max(3, size // 4)
        pad = max(1, size // 12)
        d.ellipse([size - pad - r, size - pad - r, size - pad, size - pad], fill=GOLD_LIGHT)
        return base

    badge_r = max(8, int(size * 0.32))
    badge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(badge)
    pad = max(1, int(size * 0.07))
    cx = size - pad - badge_r // 2
    cy = size - pad - badge_r // 2
    d.ellipse(
        [cx - badge_r // 2, cy - badge_r // 2, cx + badge_r // 2, cy + badge_r // 2],
        fill=NAVY_DEEP,
        outline=GOLD_LIGHT,
        width=max(1, size // 42),
    )
    gear_px = max(8, int(badge_r * 0.70))
    gear = _glyph(GEAR, gear_px, GOLD_LIGHT)
    badge.paste(gear, (cx - gear_px // 2, cy - gear_px // 2), gear)
    return Image.alpha_composite(base, badge)


def _save_ico(path: Path, maker) -> None:
    images = [maker(s) for s in SIZES]
    images[0].save(path, format="ICO", sizes=[(s, s) for s in SIZES], append_images=images[1:])
    preview = maker(256)
    preview.save(path.with_suffix(".png"), format="PNG")
    print(f"Wrote {path}")


def main() -> None:
    if not FONT.exists():
        raise FileNotFoundError(f"Missing icon font: {FONT}")
    _save_ico(APP_ICO, app_icon)
    _save_ico(SETUP_ICO, setup_icon)


if __name__ == "__main__":
    main()
