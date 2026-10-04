"""Render the brand SVGs to PNG at the sizes each use needs (#172).

The brand artwork is maintained as SVG under ``assets/brand/svg/``, as the
designer supplied it. This script renders each SVG to the PNG sizes listed in
``RENDERS`` under ``assets/brand/png/``, plus a multi-size ``favicon.ico``::

    python scripts/render_brand_assets.py

Rendering uses a headless Chromium browser (Microsoft Edge or Google Chrome),
because the SVGs use text, rounded caps and Bezier strokes that only a full
SVG renderer draws correctly, and a browser is already on every development
machine. Pass ``--browser`` if neither is found in its usual place.

The wordmarks are SVG ``<text>`` in ``Inter, Segoe UI, Arial, sans-serif``.
A PNG therefore uses the first of those installed where it was rendered:
Segoe UI on Windows without Inter. Converting the text to paths in a vector
editor would fix the typography everywhere; the supplied files have not.

Requires Pillow, installed with the ``test`` extra (through matplotlib).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "assets" / "brand" / "svg"
PNG = ROOT / "assets" / "brand" / "png"

BROWSERS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "microsoft-edge",
    "google-chrome",
    "chromium",
    "chromium-browser",
)

# Chromium will not size a window below a few hundred pixels, so every render
# is taken in a window at least this big and cropped to the image afterwards.
MIN_WINDOW = 600

APP_BLUE = "#1473E6"

# svg (relative to SVG): [(png relative to PNG, width, height, background)]
# A background of None keeps transparency; a colour fills behind the art.
RENDERS = {
    "logos/embeddedtestbench-logo-horizontal.svg": [
        ("logos/logo_horizontal.png", 900, 220, None),
        ("logos/logo_horizontal@2x.png", 1800, 440, None),
    ],
    "logos/embeddedtestbench-logo-compact.svg": [
        ("logos/logo_compact.png", 420, 90, None),
        ("logos/logo_compact@2x.png", 840, 180, None),
    ],
    "logos/embeddedtestbench-logo-monochrome.svg": [
        ("logos/logo_monochrome.png", 900, 220, None),
        ("logos/logo_monochrome@2x.png", 1800, 440, None),
    ],
    "headers/embeddedtestbench-github-header.svg": [
        ("headers/github_header.png", 1200, 260, None),
        ("headers/github_header@2x.png", 2400, 520, None),
    ],
    "headers/embeddedtestbench-website-header.svg": [
        ("headers/website_header.png", 1200, 180, None),
        ("headers/website_header@2x.png", 2400, 360, None),
    ],
    "icons/embeddedtestbench-app-blue.svg": [
        ("icons/app_icon_1024.png", 1024, 1024, None),
        ("icons/app_icon_512.png", 512, 512, None),
        ("icons/app_icon_192.png", 192, 192, None),
        # iOS applies its own corner mask and shows transparency as black,
        # so the touch icon is a full-bleed square.
        ("icons/apple_touch_icon.png", 180, 180, APP_BLUE),
    ],
    "icons/embeddedtestbench-app-light.svg": [
        ("icons/app_icon_light_512.png", 512, 512, None),
        ("icons/app_icon_light_256.png", 256, 256, None),
    ],
    "icons/embeddedtestbench-app-dark.svg": [
        ("icons/app_icon_dark_512.png", 512, 512, None),
        ("icons/app_icon_dark_256.png", 256, 256, None),
    ],
    "icons/embeddedtestbench-social-circle.svg": [
        ("icons/social_circle_512.png", 512, 512, None),
        ("icons/social_circle_400.png", 400, 400, None),
    ],
    "icons/embeddedtestbench-favicon.svg": [
        ("favicon/favicon_16.png", 16, 16, None),
        ("favicon/favicon_32.png", 32, 32, None),
        ("favicon/favicon_48.png", 48, 48, None),
    ],
    "icons/embeddedtestbench-glyph.svg": [
        ("icons/glyph_512.png", 512, 512, None),
        ("icons/glyph_64.png", 64, 64, None),
        ("icons/glyph_32.png", 32, 32, None),
        ("icons/glyph_24.png", 24, 24, None),
        ("icons/glyph_16.png", 16, 16, None),
    ],
    "icons/embeddedtestbench-glyph-monochrome.svg": [
        ("icons/glyph_monochrome_512.png", 512, 512, None),
        ("icons/glyph_monochrome_64.png", 64, 64, None),
    ],
}
for _name in ("psu", "jlink", "oscilloscope", "dmm", "ble", "rf", "temperature"):
    RENDERS[f"instrument-icons/embeddedtestbench-{_name}.svg"] = [
        (f"instruments/{_name}_{side}.png", side, side, None) for side in (64, 128, 256)
    ]

FAVICON_ICO = "favicon/favicon.ico"
FAVICON_ICO_PARTS = ("favicon/favicon_16.png", "favicon/favicon_32.png",
                     "favicon/favicon_48.png")

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><style>
html, body {{ margin: 0; padding: 0; background: transparent; overflow: hidden; }}
div {{ width: {width}px; height: {height}px; background: {background}; }}
img {{ display: block; width: {width}px; height: {height}px; }}
</style></head>
<body><div><img src="{src}"></div></body></html>
"""


def find_browser(given: str | None) -> str:
    """The browser executable to render with."""
    for candidate in ((given,) if given else BROWSERS):
        if Path(candidate).is_file():
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    raise SystemExit("No Edge or Chrome found; pass --browser <path>")


def render(browser: str, svg: Path, size: tuple[int, int], background: str | None,
           work: Path) -> Image.Image:
    """Render ``svg`` at ``size`` pixels; return it as an RGBA image."""
    width, height = size
    page = work / "page.html"
    shot = work / "shot.png"
    page.write_text(PAGE.format(width=width, height=height, src=svg.as_uri(),
                                background=background or "transparent"),
                    encoding="utf-8")
    shot.unlink(missing_ok=True)
    subprocess.run(
        [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         "--force-device-scale-factor=1", "--default-background-color=00000000",
         f"--window-size={max(width, MIN_WINDOW)},{max(height, MIN_WINDOW)}",
         f"--user-data-dir={work / 'profile'}", f"--screenshot={shot}",
         page.as_uri()],
        check=True, capture_output=True, timeout=120)
    # On Windows the executable can hand the work to a child process and
    # return first, so wait for the screenshot rather than for the process.
    deadline = time.monotonic() + 60
    while not shot.is_file() or shot.stat().st_size == 0:
        if time.monotonic() > deadline:
            raise SystemExit(f"{browser} wrote no screenshot of {svg.name}")
        time.sleep(0.2)
    time.sleep(0.2)
    with Image.open(shot) as image:
        return image.convert("RGBA").crop((0, 0, width, height))


def main() -> int:
    """Render every PNG and the favicon; print each file and its size."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--browser", help="path to msedge, chrome or chromium")
    parser.add_argument("--svg", type=Path, default=SVG)
    parser.add_argument("--out", type=Path, default=PNG)
    args = parser.parse_args()

    browser = find_browser(args.browser)
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        for svg_name, outputs in RENDERS.items():
            for png_name, width, height, background in outputs:
                image = render(browser, args.svg / svg_name, (width, height),
                               background, work)
                path = args.out / png_name
                path.parent.mkdir(parents=True, exist_ok=True)
                image.save(path, optimize=True)
                print(f"{png_name}  {width}x{height}")

    # Each size in the icon is its own render, not a downscale of the largest.
    parts = [Image.open(args.out / name) for name in FAVICON_ICO_PARTS]
    parts[-1].save(args.out / FAVICON_ICO, sizes=[part.size for part in parts],
                   append_images=parts[:-1])
    print(f"{FAVICON_ICO}  {', '.join(f'{p.size[0]}x{p.size[1]}' for p in parts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
