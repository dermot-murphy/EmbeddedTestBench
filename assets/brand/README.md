# Brand assets

The product's logo, icons and instrument icons, each as its own file at the size
its purpose calls for (#172).

All of them are cut from one composite sheet, [`source/brand_sheet.png`](source/brand_sheet.png),
by [`scripts/split_brand_sheet.py`](../../scripts/split_brand_sheet.py). Regenerate
them with that script rather than editing a file by hand:

```sh
python scripts/split_brand_sheet.py
```

It needs Pillow and numpy, both installed with the `test` extra.

## Files

Sizes are in pixels. "Transparent" means the sheet's background has been
removed; "on a tile" means the image carries its own rounded background.

### Logos — `logo/`

| File | Size | Purpose |
| --- | --- | --- |
| `logo_horizontal.png` | 718 × 356 | Main logo: mark above the wordmark. Transparent, for light backgrounds. |
| `header_horizontal.png` | 453 × 105 | Website or page header: mark beside the wordmark. Transparent, for light backgrounds. |
| `logo_monochrome.png` | 396 × 101 | Single colour, for print and documents. Transparent, for light backgrounds. |
| `logo_monochrome_dark.png` | 305 × 101 | Light logo on its own dark panel, for dark surfaces. |

### App icons — `app_icon/`

| File | Size | Purpose |
| --- | --- | --- |
| `app_icon_1024.png` | 1024 × 1024 | Application icon, store and installer size. On a blue tile. |
| `app_icon_512.png` | 512 × 512 | Application icon; web app manifest large icon. |
| `app_icon_192.png` | 192 × 192 | Web app manifest icon. |
| `apple_touch_icon_180.png` | 180 × 180 | `apple-touch-icon` for iOS home screens. |
| `app_icon_light_256.png` | 256 × 256 | Icon on a white tile, for light interfaces. |
| `app_icon_dark_256.png` | 256 × 256 | Icon on a dark tile, for dark interfaces. |

The tiles keep the sheet's rounded corners, with transparent pixels outside
them. Platforms that apply their own mask (iOS, Android adaptive icons) expect a
full-bleed square instead; one cannot be made from the sheet without redrawing
the corners.

### Favicon — `favicon/`

| File | Size | Purpose |
| --- | --- | --- |
| `favicon.ico` | 16, 32, 48 | Browser favicon, all three sizes in one file. |
| `favicon_16.png` | 16 × 16 | Browser tab. |
| `favicon_32.png` | 32 × 32 | Browser tab on high-density screens; bookmarks. |
| `favicon_48.png` | 48 × 48 | Windows site icons. |

### Mark without wordmark — `icon/`

| File | Size | Purpose |
| --- | --- | --- |
| `glyph.png` | 150 × 106 | The mark alone, with the orbit. Transparent. |
| `simplified_16.png` … `simplified_64.png` | 16, 24, 32, 64 | The mark without the orbit, for small sizes where the orbit would not resolve. Transparent. |

### Instrument icons — `instruments/`

One icon per bench instrument, each at 64 × 64 and 128 × 128, transparent. White
enclosed by an icon (an instrument's face) is kept, so they read on a dark page
too.

| Files | Instrument |
| --- | --- |
| `psu_64.png`, `psu_128.png` | Power supply (GPD-3303D) |
| `jlink_64.png`, `jlink_128.png` | J-Link debug probe |
| `oscilloscope_64.png`, `oscilloscope_128.png` | Oscilloscope |
| `dmm_64.png`, `dmm_128.png` | Digital multimeter (TTi 1604) |
| `ble_64.png`, `ble_128.png` | BLE dongle |
| `rf_64.png`, `rf_128.png` | Sub-GHz RF (S2-LP kit) |
| `temperature_64.png`, `temperature_128.png` | Temperature (Pico 2 SHT30) |

## Limitations

- **The sheet is the only source, and it is a raster image.** Any size larger
  than the area an image covers on the sheet is upscaled and is softer for it.
  The app icon covers 375 px of the sheet, so `app_icon_1024.png` and
  `app_icon_512.png` are upscaled, as are the light and dark tiles at 256 px
  and the instrument icons at 128 px. Vector masters would remove this
  limitation; none exist yet.
- **Dark artwork on a transparent background disappears on a dark page.** Use
  `logo_monochrome_dark.png` or `app_icon_dark_256.png` there.
- **The wordmark reads "EmbeddedTest"**, as supplied, not "EmbeddedTestBench".
