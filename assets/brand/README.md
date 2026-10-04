# Brand assets

The EmbeddedTestBench logo, app icons, favicon and instrument icons (#172).

- **`svg/`** holds the masters, as the designer supplied them. Use an SVG
  directly wherever SVG is accepted (web pages, GitHub Markdown, documents);
  it scales without loss. `svg/README.md` is the designer's own note.
- **`png/`** holds raster renders of the SVGs at the sizes listed below, for
  places that need a bitmap: app manifests, `favicon.ico`, slide decks, and
  anything that does not render SVG.

Regenerate the PNGs after changing an SVG, rather than editing a PNG:

```sh
python scripts/render_brand_assets.py
```

The script renders with headless Microsoft Edge or Google Chrome, and needs
Pillow, installed with the `test` extra.

## Masters — `svg/`

| File | Purpose |
| --- | --- |
| `logos/embeddedtestbench-logo-horizontal.svg` | Main logo: mark beside the wordmark. For light backgrounds. |
| `logos/embeddedtestbench-logo-compact.svg` | Smaller lock-up for tight spaces such as a navigation bar. |
| `logos/embeddedtestbench-logo-monochrome.svg` | Single colour, for print and documents. |
| `headers/embeddedtestbench-github-header.svg` | Repository banner: logo, tagline and technology badges on dark. |
| `headers/embeddedtestbench-website-header.svg` | Website header on a transparent background. |
| `icons/embeddedtestbench-app-blue.svg` | Application icon, primary. |
| `icons/embeddedtestbench-app-light.svg` | Application icon for light interfaces. |
| `icons/embeddedtestbench-app-dark.svg` | Application icon for dark interfaces. |
| `icons/embeddedtestbench-social-circle.svg` | Circular avatar for social and chat profiles. |
| `icons/embeddedtestbench-favicon.svg` | Favicon. Modern browsers accept it directly. |
| `icons/embeddedtestbench-glyph.svg` | The mark alone, without the orbit, for small sizes. |
| `icons/embeddedtestbench-glyph-monochrome.svg` | The mark alone, single colour. |
| `instrument-icons/embeddedtestbench-<instrument>.svg` | One icon per bench instrument: `psu`, `jlink`, `oscilloscope`, `dmm`, `ble`, `rf`, `temperature`. |

## Renders — `png/`

Every PNG has a transparent background unless the SVG draws one. `@2x` files
are for high-density screens.

| Files | Sizes | From |
| --- | --- | --- |
| `logos/logo_horizontal.png`, `@2x` | 900 × 220, 1800 × 440 | horizontal logo |
| `logos/logo_compact.png`, `@2x` | 420 × 90, 840 × 180 | compact logo |
| `logos/logo_monochrome.png`, `@2x` | 900 × 220, 1800 × 440 | monochrome logo |
| `headers/github_header.png`, `@2x` | 1200 × 260, 2400 × 520 | GitHub header |
| `headers/website_header.png`, `@2x` | 1200 × 180, 2400 × 360 | website header |
| `icons/app_icon_1024.png`, `_512`, `_192` | 1024, 512, 192 | blue app icon: store, installer and web app manifest sizes |
| `icons/apple_touch_icon.png` | 180 × 180 | blue app icon, as a full-bleed square: iOS applies its own corner mask and shows transparency as black |
| `icons/app_icon_light_512.png`, `_256` | 512, 256 | light app icon |
| `icons/app_icon_dark_512.png`, `_256` | 512, 256 | dark app icon |
| `icons/social_circle_512.png`, `_400` | 512, 400 | social icon; 400 px is the common avatar upload size |
| `icons/glyph_512.png`, `_64`, `_32`, `_24`, `_16` | 512 … 16 | glyph, including the small sizes it exists for |
| `icons/glyph_monochrome_512.png`, `_64` | 512, 64 | monochrome glyph |
| `favicon/favicon_16.png`, `_32`, `_48` | 16, 32, 48 | favicon |
| `favicon/favicon.ico` | 16, 32, 48 in one file | favicon; each size is its own render, not a downscale |
| `instruments/<instrument>_64.png`, `_128`, `_256` | 64, 128, 256 | instrument icons |

## Notes

- **Wordmark typography depends on the rendering machine.** The wordmarks are
  SVG text in `Inter, Segoe UI, Arial, sans-serif`. A browser showing an SVG
  uses the first of those it has. The PNGs here were rendered on Windows
  without Inter, so they use Segoe UI. The designer's note recommends
  converting the text to paths for exact typography everywhere; the supplied
  files have not been converted.
- **Dark artwork on a transparent background disappears on a dark page.** Use
  the dark app icon, the social icon or the GitHub header there.
