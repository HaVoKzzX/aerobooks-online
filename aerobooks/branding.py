"""AeroBooks mark — the same gold takeoff icon used in the app header."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

GOLD = (196, 163, 90, 255)
TAKEOFF = "\ue905"  # Material Icons ligature flight_takeoff


def _font_path() -> Path:
    here = Path(__file__).resolve().parent
    bundled = here / "assets" / "MaterialIcons-Regular.ttf"
    if bundled.exists():
        return bundled
    from aerobooks import paths

    for candidate in (
        paths.install_dir() / "MaterialIcons-Regular.ttf",
        paths.install_dir() / "aerobooks" / "assets" / "MaterialIcons-Regular.ttf",
    ):
        if candidate.exists():
            return candidate
    mp = paths.meipass()
    if mp:
        for candidate in (
            mp / "aerobooks" / "assets" / "MaterialIcons-Regular.ttf",
            mp / "MaterialIcons-Regular.ttf",
        ):
            if candidate.exists():
                return candidate
    raise FileNotFoundError("Material Icons font is missing")


def render_logo_png(dest: Path, size: int = 512) -> Path:
    """Gold flight_takeoff glyph on a transparent square — matches the app header icon."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    scale = 4
    canvas = size * scale
    im = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    font = ImageFont.truetype(str(_font_path()), int(canvas * 0.92))
    bbox = draw.textbbox((0, 0), TAKEOFF, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (canvas - w) / 2 - bbox[0]
    y = (canvas - h) / 2 - bbox[1]
    draw.text((x, y), TAKEOFF, font=font, fill=GOLD)
    logo = im.resize((size, size), Image.Resampling.LANCZOS)
    logo.save(dest, format="PNG")
    return dest


def logo_png_path() -> Path:
    from aerobooks import paths

    here = Path(__file__).resolve().parent
    preferred = here / "assets" / "aerobooks_logo.png"
    candidates = [preferred]
    if paths.meipass():
        candidates.append(paths.meipass() / "aerobooks" / "assets" / "aerobooks_logo.png")
        candidates.append(paths.meipass() / "aerobooks_logo.png")
    candidates.append(paths.install_dir() / "aerobooks_logo.png")
    for path in candidates:
        if path.exists():
            return path
    cache = paths.data_dir() / "branding" / "aerobooks_logo.png"
    return render_logo_png(cache)
