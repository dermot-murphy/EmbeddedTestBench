"""Convert the text in the brand SVGs to outlines (#172).

The designer's SVGs set their lettering as ``<text>`` in ``Inter, Segoe UI,
Arial, sans-serif``. A viewer without Inter substitutes another font, so the
wordmark looked different on every machine. This script replaces each
``<text>`` with the outlines of its glyphs in Inter, so every viewer draws the
same shapes and no font is needed::

    python scripts/outline_brand_text.py

The editable files, with live text, are kept in ``assets/brand/svg-source/``.
Change the wording there, then run this script and
``scripts/render_brand_assets.py``. SVGs without text are not touched.

Inter is used for all text, including the instrument icons' labels that the
designer set in Arial: Inter is the brand typeface, and its SIL Open Font
License (``assets/brand/fonts/LICENSE.txt``) allows outlining it.

Layout follows what a browser does with the variable font: the ``wght`` axis
is set from ``font-weight`` and the ``opsz`` axis from ``font-size`` (the CSS
``font-optical-sizing: auto`` default). Pair kerning from the font's ``kern``
feature and ``letter-spacing`` are applied; ``text-anchor`` start and middle
are supported. Each glyph is placed one after another, which is all the text
in these files needs: one line, Latin, no ligatures.

Requires fontTools, installed with the ``test`` extra (through matplotlib).
"""

from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "brand" / "svg-source"
OUT = ROOT / "assets" / "brand" / "svg"
FONT = ROOT / "assets" / "brand" / "fonts" / "InterVariable.ttf"

SVG_NS = "http://www.w3.org/2000/svg"
NS = f"{{{SVG_NS}}}"
ET.register_namespace("", SVG_NS)

# Presentation attributes a <text> inherits from the elements around it.
INHERITED = ("font-family", "font-size", "font-weight", "letter-spacing",
             "text-anchor", "fill")
WEIGHTS = {"normal": 400, "bold": 700}
TEXT_ATTRIBUTES = ("x", "y", "font-family", "font-size", "font-weight",
                   "letter-spacing", "text-anchor", "fill")


def number(value: str | None, default: float = 0.0) -> float:
    """A plain SVG length (``12``, ``-1.5``, ``12px``) as a float."""
    if value is None:
        return default
    match = re.fullmatch(r"\s*(-?[\d.]+)(px)?\s*", value)
    if not match:
        raise ValueError(f"unsupported length {value!r}")
    return float(match.group(1))


@lru_cache(maxsize=None)
def instance(font_path: str, weight: float, opsz: float) -> TTFont:
    """Inter at one weight and optical size, as a static font."""
    font = TTFont(font_path)
    axes = {axis.axisTag: (axis.minValue, axis.maxValue) for axis in font["fvar"].axes}
    location = {}
    if "wght" in axes:
        location["wght"] = min(max(weight, axes["wght"][0]), axes["wght"][1])
    if "opsz" in axes:
        location["opsz"] = min(max(opsz, axes["opsz"][0]), axes["opsz"][1])
    return instantiateVariableFont(font, location)


def kern_lookups(font: TTFont) -> list:
    """The PairPos subtables of the font's ``kern`` feature."""
    if "GPOS" not in font:
        return []
    table = font["GPOS"].table
    indices = sorted({index for record in table.FeatureList.FeatureRecord
                      if record.FeatureTag == "kern"
                      for index in record.Feature.LookupListIndex})
    subtables = []
    for index in indices:
        lookup = table.LookupList.Lookup[index]
        for subtable in lookup.SubTable:
            if lookup.LookupType == 9:  # extension: unwrap
                subtable = subtable.ExtSubTable
            if subtable.LookupType == 2:
                subtables.append(subtable)
    return subtables


def kerning(subtables: list, left: str, right: str) -> float:
    """The x-advance adjustment between two glyphs, in font units."""
    for sub in subtables:
        coverage = sub.Coverage.glyphs
        if left not in coverage:
            continue
        if sub.Format == 1:
            pair_set = sub.PairSet[coverage.index(left)]
            for record in pair_set.PairValueRecord:
                if record.SecondGlyph == right:
                    return advance_of(record.Value1)
        elif sub.Format == 2:
            # The first class-based subtable covering the left glyph decides,
            # including deciding there is no adjustment.
            class1 = sub.ClassDef1.classDefs.get(left, 0)
            class2 = sub.ClassDef2.classDefs.get(right, 0)
            return advance_of(sub.Class1Record[class1].Class2Record[class2].Value1)
    return 0


def advance_of(value) -> float:
    """The XAdvance of a GPOS value record, which may be absent."""
    return (getattr(value, "XAdvance", 0) or 0) if value is not None else 0


def runs_of(text: ET.Element) -> list[tuple[str, str | None]]:
    """The text and fill of each run: the element's own text, then each tspan."""
    runs = []
    if text.text:
        runs.append((text.text, None))
    for child in text:
        if child.tag != f"{NS}tspan":
            raise ValueError(f"unsupported element in <text>: {child.tag}")
        if child.text:
            runs.append((child.text, child.get("fill")))
        if child.tail:
            runs.append((child.tail, None))
    return runs


def fmt(value: float) -> str:
    """A coordinate to two decimal places, without trailing zeros."""
    return f"{value:.2f}".rstrip("0").rstrip(".")


def font_for(style: dict[str, str], font_path: str) -> tuple[TTFont, float]:
    """The Inter instance ``style`` asks for, and its units-to-pixels scale."""
    size = number(style.get("font-size"), 16.0)
    weight = style.get("font-weight", "normal")
    font = instance(font_path, float(WEIGHTS.get(weight, weight)), size)
    return font, size / font["head"].unitsPerEm


def layout(runs, font: TTFont, scale: float, spacing: float):
    """Place each glyph; return ([(glyph, x, fill)], total advance)."""
    cmap = font.getBestCmap()
    advances = font["hmtx"].metrics
    subtables = kern_lookups(font)
    placed = []
    pen_x = 0.0
    previous = None
    for string, fill in runs:
        for char in string:
            name = cmap.get(ord(char))
            if name is None:
                raise ValueError(f"Inter has no glyph for {char!r}")
            if previous is not None:
                pen_x += kerning(subtables, previous, name) * scale
            placed.append((name, pen_x, fill))
            pen_x += advances[name][0] * scale + spacing
            previous = name
    return placed, pen_x


def path_data(placed, font: TTFont, scale: float,
              origin: tuple[float, float]) -> dict[str | None, str]:
    """SVG path data for the placed glyphs, one path per fill."""
    glyph_set = font.getGlyphSet()
    paths: dict[str | None, list[str]] = {}
    for name, offset, fill in placed:
        pen = SVGPathPen(glyph_set, ntos=fmt)
        glyph_set[name].draw(TransformPen(
            pen, (scale, 0, 0, -scale, origin[0] + offset, origin[1])))
        if pen.getCommands():
            paths.setdefault(fill, []).append(pen.getCommands())
    return {fill: "".join(commands) for fill, commands in paths.items()}


def outline(text: ET.Element, style: dict[str, str], font_path: str) -> ET.Element:
    """A ``<g>`` of glyph outlines that draws what ``text`` draws.

    ``style`` holds the text's presentation attributes, including those it
    inherits from enclosing elements.
    """
    font, scale = font_for(style, font_path)
    runs = runs_of(text)
    placed, width = layout(runs, font, scale, number(style.get("letter-spacing")))

    origin = (number(text.get("x"))
              - {"middle": width / 2, "end": width}.get(style.get("text-anchor"), 0.0),
              number(text.get("y")))

    group = ET.Element(f"{NS}g", {"fill": style.get("fill", "#000000"),
                                  "aria-label": "".join(string for string, _ in runs)})
    for fill, data in path_data(placed, font, scale, origin).items():
        path = ET.SubElement(group, f"{NS}path", {"d": data})
        if fill is not None:
            path.set("fill", fill)
    for key, value in text.attrib.items():
        if key not in TEXT_ATTRIBUTES:
            group.set(key, value)
    return group


def ancestors(element: ET.Element, parents: dict) -> list[ET.Element]:
    """The elements enclosing ``element``, nearest first."""
    chain = []
    while element in parents:
        element = parents[element]
        chain.append(element)
    return chain


def convert(source: Path, target: Path, font_path: str) -> int:
    """Write ``source`` to ``target`` with every ``<text>`` outlined."""
    tree = ET.parse(source)
    parents = {child: parent for parent in tree.iter() for child in parent}
    count = 0
    for text in list(tree.iter(f"{NS}text")):
        parent = parents[text]
        style = {}
        for ancestor in reversed(ancestors(text, parents)):
            style.update({key: value for key, value in ancestor.attrib.items()
                          if key in INHERITED})
        style.update(text.attrib)
        group = outline(text, style, font_path)
        group.tail = text.tail
        position = list(parent).index(text)
        parent.remove(text)
        parent.insert(position, group)
        count += 1
    # Text set on a parent <g> (font-family and the like) no longer applies.
    for element in tree.iter(f"{NS}g"):
        for key in ("font-family", "font-size", "font-weight"):
            element.attrib.pop(key, None)
    target.parent.mkdir(parents=True, exist_ok=True)
    tree.write(target, encoding="utf-8", xml_declaration=False)
    return count


def main() -> int:
    """Outline every SVG under the source folder; print what was converted."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--font", type=Path, default=FONT)
    args = parser.parse_args()

    for source in sorted(args.source.rglob("*.svg")):
        relative = source.relative_to(args.source)
        count = convert(source, args.out / relative, str(args.font))
        print(f"{relative.as_posix()}  {count} text element(s) outlined")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
