"""Split the brand artwork sheet into the individual images it shows (#172).

The artwork was supplied as one composite raster, ``assets/brand/source/
brand_sheet.png``. Each image on it carries a caption saying what it is for.
This script crops each one, removes the sheet's background where the art sits
on it, and writes it at the sizes its purpose calls for, so the files under
``assets/brand/`` can be regenerated rather than edited by hand::

    python scripts/split_brand_sheet.py

The crop boxes were measured from the sheet: rows and columns of pixels that
differ from the background by more than 40 levels, plus a margin for
anti-aliasing. If the sheet is replaced, re-measure them.

Backgrounds are removed in one of three ways, chosen per image:

* ``key`` - every pixel is unmixed from the background colour (GIMP's "colour
  to alpha"), so the white inside a logo becomes transparent with it. For art
  drawn on the sheet's white.
* ``flood`` - only background connected to the crop's edge is unmixed, so
  white enclosed by the art (an instrument's face, a tile's glyph) stays
  opaque. For tiles and filled shapes.
* ``tile`` - inside a given rounded rectangle is opaque; outside it is
  unmixed, which keeps a white tile's drop shadow as a soft shadow. For the
  white tile, which ``flood`` would leak into because it matches the sheet.

Requires Pillow and numpy, both installed with the ``test`` extra (through
matplotlib).

Sizes larger than the area an image covers on the sheet are upscaled, and
softer for it: the 1024 px app icon covers 375 px of the sheet. A vector
master would remove that limit; none exists yet.
"""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SHEET = ROOT / "assets" / "brand" / "source" / "brand_sheet.png"
OUT = ROOT / "assets" / "brand"

WHITE = (254, 254, 254)
PANEL = (241, 248, 254)  # the light blue panel behind the instrument icons
MARGIN = 6
FLOOD_THRESHOLD = 40
ALPHA_FLOOR = 0.10

# name: (box on the sheet, background colour, removal mode, outputs)
# An output is (file name, size): size None keeps the cropped size, an int
# makes a square of that side, padding the crop to a square first.
IMAGES = {
    "logo_horizontal": ((49, 74, 755, 418), WHITE, "key",
                        [("logo/logo_horizontal.png", None)]),
    "app_icon": ((818, 82, 1192, 446), WHITE, "flood",
                 [("app_icon/app_icon_1024.png", 1024),
                  ("app_icon/app_icon_512.png", 512),
                  ("app_icon/app_icon_192.png", 192),
                  ("app_icon/apple_touch_icon_180.png", 180)]),
    "header": ((42, 592, 483, 685), WHITE, "key",
               [("logo/header_horizontal.png", None)]),
    "app_icon_light": ((535, 550, 723, 715), WHITE, "tile",
                       [("app_icon/app_icon_light_256.png", 256)]),
    "app_icon_dark": ((796, 549, 980, 716), WHITE, "flood",
                      [("app_icon/app_icon_dark_256.png", 256)]),
    "favicon": ((1072, 572, 1196, 697), WHITE, "flood",
                [("favicon/favicon_16.png", 16),
                 ("favicon/favicon_32.png", 32),
                 ("favicon/favicon_48.png", 48)]),
    "mono": ((42, 842, 426, 931), WHITE, "key",
             [("logo/logo_monochrome.png", None)]),
    "mono_dark": ((471, 843, 764, 932), WHITE, "flood",
                  [("logo/logo_monochrome_dark.png", None)]),
    "glyph": ((834, 841, 972, 935), WHITE, "key",
              [("icon/glyph.png", None)]),
    "simplified": ((1074, 841, 1174, 935), WHITE, "key",
                   [("icon/simplified_16.png", 16),
                    ("icon/simplified_24.png", 24),
                    ("icon/simplified_32.png", 32),
                    ("icon/simplified_64.png", 64)]),
    "psu": ((69, 1070, 172, 1145), PANEL, "flood",
            [("instruments/psu_64.png", 64), ("instruments/psu_128.png", 128)]),
    "jlink": ((256, 1048, 312, 1156), PANEL, "flood",
              [("instruments/jlink_64.png", 64), ("instruments/jlink_128.png", 128)]),
    "oscilloscope": ((397, 1070, 525, 1149), PANEL, "flood",
                     [("instruments/oscilloscope_64.png", 64),
                      ("instruments/oscilloscope_128.png", 128)]),
    "dmm": ((604, 1055, 673, 1158), PANEL, "flood",
            [("instruments/dmm_64.png", 64), ("instruments/dmm_128.png", 128)]),
    "ble": ((756, 1066, 856, 1150), PANEL, "flood",
            [("instruments/ble_64.png", 64), ("instruments/ble_128.png", 128)]),
    "rf": ((915, 1059, 1008, 1156), PANEL, "flood",
           [("instruments/rf_64.png", 64), ("instruments/rf_128.png", 128)]),
    "temperature": ((1097, 1058, 1175, 1155), PANEL, "flood",
                    [("instruments/temperature_64.png", 64),
                     ("instruments/temperature_128.png", 128)]),
}

TILE_RADIUS = 24
FAVICON_ICO = "favicon/favicon.ico"
FAVICON_ICO_SIZES = (16, 32, 48)


def color_to_alpha(rgb: np.ndarray, bg: tuple[int, int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Unmix ``bg`` from each pixel; return (straight RGB, alpha), floats 0-1."""
    pixel = rgb / 255.0
    back = np.array(bg, dtype=float) / 255.0
    # A background channel at or near full scale leaves no room above it, and
    # dividing by that gap would turn one level of noise into full opacity.
    headroom = (1.0 - back) > 0.05
    above = np.where((pixel > back) & headroom,
                     (pixel - back) / np.maximum(1.0 - back, 1e-6), 0.0)
    below = np.where(pixel < back, (back - pixel) / np.maximum(back, 1e-6), 0.0)
    alpha = np.clip(np.maximum(above, below).max(axis=2), 0.0, 1.0)
    safe = np.maximum(alpha, 1e-6)[..., None]
    colour = np.clip((pixel - back) / safe + back, 0.0, 1.0)
    # The sheet's background is not flat: compression noise near the art
    # would unmix to faint specks that show on a dark page. Treat anything
    # within ALPHA_FLOOR of the background as background.
    alpha = np.clip((alpha - ALPHA_FLOOR) / (1.0 - ALPHA_FLOOR), 0.0, 1.0)
    return colour, alpha


def edge_connected(near: np.ndarray) -> np.ndarray:
    """Pixels of ``near`` reachable from the image border through ``near``."""
    height, width = near.shape
    seen = np.zeros_like(near)
    border = ([(row, 0) for row in range(height)]
              + [(row, width - 1) for row in range(height)]
              + [(0, col) for col in range(width)]
              + [(height - 1, col) for col in range(width)])
    queue = deque()
    for row, col in border:
        if near[row, col] and not seen[row, col]:
            seen[row, col] = True
            queue.append((row, col))
    while queue:
        row, col = queue.popleft()
        for nrow, ncol in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
            if (0 <= nrow < height and 0 <= ncol < width
                    and near[nrow, ncol] and not seen[nrow, ncol]):
                seen[nrow, ncol] = True
                queue.append((nrow, ncol))
    return seen


def grow(mask: np.ndarray, steps: int) -> np.ndarray:
    """Dilate ``mask`` by ``steps`` pixels, four-connected."""
    out = mask.copy()
    for _ in range(steps):
        grown = out.copy()
        grown[1:, :] |= out[:-1, :]
        grown[:-1, :] |= out[1:, :]
        grown[:, 1:] |= out[:, :-1]
        grown[:, :-1] |= out[:, 1:]
        out = grown
    return out


def rounded_mask(size: tuple[int, int], inset: int, radius: int) -> np.ndarray:
    """An anti-aliased rounded rectangle, inset from the edges, as 0-1 floats."""
    scale = 4
    width, height = size
    big = Image.new("L", (width * scale, height * scale), 0)
    ImageDraw.Draw(big).rounded_rectangle(
        (inset * scale, inset * scale,
         (width - inset) * scale - 1, (height - inset) * scale - 1),
        radius=radius * scale, fill=255)
    return np.asarray(big.resize(size, Image.Resampling.LANCZOS), dtype=float) / 255.0


def opaque_where(keep: np.ndarray, rgb: np.ndarray, colour: np.ndarray,
                 alpha: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Blend unmixed pixels back to the original where ``keep`` (0-1) is set."""
    keep3 = keep[..., None]
    return (keep3 * rgb / 255.0 + (1.0 - keep3) * colour,
            keep + (1.0 - keep) * alpha)


def cut(sheet: Image.Image, box, bg, mode: str) -> Image.Image:
    """Crop one image from the sheet and remove its background."""
    crop = sheet.crop((box[0] - MARGIN, box[1] - MARGIN, box[2] + MARGIN, box[3] + MARGIN))
    rgb = np.asarray(crop, dtype=float)
    colour, alpha = color_to_alpha(rgb, bg)
    if mode == "flood":
        near = np.abs(rgb - np.array(bg, dtype=float)).max(axis=2) < FLOOD_THRESHOLD
        # Grown by two pixels so the art's anti-aliased edge, too far from the
        # background to pass the threshold, is unmixed rather than fringed.
        background = grow(edge_connected(near), 2)
        colour, alpha = opaque_where((~background).astype(float), rgb, colour, alpha)
    elif mode == "tile":
        colour, alpha = opaque_where(rounded_mask(crop.size, MARGIN, TILE_RADIUS),
                                     rgb, colour, alpha)
    elif mode != "key":
        raise ValueError(f"unknown mode {mode!r}")
    rgba = np.dstack([colour, alpha]) * 255.0
    image = Image.fromarray(np.round(rgba).astype(np.uint8), "RGBA")
    return image.crop(image.getbbox())


def square(image: Image.Image, side: int) -> Image.Image:
    """Pad to a centred square, then scale to ``side`` pixels."""
    width, height = image.size
    extent = max(width, height)
    canvas = Image.new("RGBA", (extent, extent), (0, 0, 0, 0))
    canvas.paste(image, ((extent - width) // 2, (extent - height) // 2))
    # Resample in premultiplied alpha so transparent pixels' colour does not
    # bleed into the edges.
    scaled = canvas.convert("RGBa").resize((side, side), Image.Resampling.LANCZOS)
    scaled = scaled.convert("RGBA")
    if side > extent:
        scaled = scaled.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
    return scaled


def main() -> int:
    """Write every image; print each file and its size."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sheet", type=Path, default=SHEET)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    sheet = Image.open(args.sheet).convert("RGB")
    favicon_source = None
    for name, (box, bg, mode, outputs) in IMAGES.items():
        image = cut(sheet, box, bg, mode)
        if name == "favicon":
            favicon_source = image
        for filename, side in outputs:
            result = image if side is None else square(image, side)
            path = args.out / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            result.save(path, optimize=True)
            print(f"{filename}  {result.size[0]}x{result.size[1]}")

    ico = square(favicon_source, max(FAVICON_ICO_SIZES))
    ico.save(args.out / FAVICON_ICO, sizes=[(side, side) for side in FAVICON_ICO_SIZES])
    print(f"{FAVICON_ICO}  {', '.join(f'{side}x{side}' for side in FAVICON_ICO_SIZES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
