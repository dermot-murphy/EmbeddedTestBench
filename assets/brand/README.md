# Brand assets

The EmbeddedTestBench logo, app icons, favicon and instrument icons (#172).

- **`svg/`** holds the masters. Use an SVG directly wherever SVG is accepted
  (web pages, GitHub Markdown, documents); it scales without loss. All text in
  them has been converted to outlines, so they look the same on every machine
  and need no font. `svg/README.md` is the designer's own note.
- **`svg-source/`** holds the editable versions of the SVGs that contain text,
  with the text still live. Change wording here, never in `svg/`.
- **`png/`** holds raster renders of the SVGs at the sizes listed below, for
  places that need a bitmap: app manifests, `favicon.ico`, slide decks, and
  anything that does not render SVG.
- **`fonts/`** holds Inter, the brand typeface, and its licence.

After changing a file in `svg-source/`, outline it and re-render:

```sh
python scripts/outline_brand_text.py
python scripts/render_brand_assets.py
```

After changing an SVG with no text, only the second command is needed. The
outlining script needs fontTools and the render script needs Pillow, both
installed with the `test` extra. Rendering uses headless Microsoft Edge or
Google Chrome.

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

- **Typeface.** All text is Inter (`fonts/InterVariable.ttf`, SIL Open Font
  License 1.1, `fonts/LICENSE.txt`), at the weight each source file asks for:
  750 for the wordmarks. The designer set the instrument icons' labels in
  Arial; they are outlined in Inter instead, to keep to one brand typeface
  whose licence allows it.
- **Outlining is a close match, not a copy, of a browser's text layout.**
  Compared with the same source drawn by a browser with Inter loaded, the
  wordmarks differ in under 0.01 % of pixels, all at anti-aliased edges. One
  visible difference: a browser raises the "+" in "C / C++" (GitHub header) to
  cap height through Inter's contextual alternates, which the outliner does
  not apply.
- **Dark artwork on a transparent background disappears on a dark page.** Use
  the dark app icon, the social icon or the GitHub header there.
