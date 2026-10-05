"""Generate the GitHub wiki and the GitHub Pages home page from the repository.

    python scripts/publish_docs.py wiki <out-dir> [--clean] [--ref main] [--repo owner/name]
    python scripts/publish_docs.py home <out-dir> [--ref main] [--repo owner/name]

``wiki`` writes one flat wiki page per document: ``Home`` from the README's
introduction, one page per user guide and instrument note in ``docs/``, one
``ASPICE-<name>`` page per ASPICE work product, an ``ASPICE-Index`` page and
``_Sidebar``. Relative links between published documents become wiki links;
every other relative link points at the file on ``--ref`` in the repository.
``--clean`` first removes the top-level ``*.md`` pages already in ``<out-dir>``,
so a renamed or deleted document does not leave a stale page behind.

``home`` writes the home page served by GitHub Pages from the ``gh-pages``
branch: ``README.md`` with the website header banner, the README's
introduction and links to the wiki, the latest release and the system
qualification report; the favicons and ``_includes/head-custom.html``, which
links them from the theme's <head>.

The brand artwork (#194) is the compact logo on the wiki's ``Home`` and
``_Sidebar`` and the GitHub header banner on ``ASPICE-Index``, as PNG renders.

Both outputs are generated, never edited by hand, and published from ``main``
by ``.github/workflows/wiki_publish.yml`` and ``pages_publish.yml``
(ETB-SUP8-001 §5.8). The output depends only on the repository content and the
arguments - no timestamp - so a run with nothing changed changes nothing.

Standard library only, Python 3.8 and later.

Traces to: ETB-SUP8-001 §5.8 and §6.3, issues #184 and #194.
"""

from __future__ import annotations

import argparse
import posixpath
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = "dermot-murphy/EmbeddedTestBench"
DEFAULT_REF = "main"

#: User guides, in sidebar order: (path, label). A missing file is skipped, so
#: a guide can be listed before it is written.
GUIDES = (
    ("docs/User_Manual.md", "User Manual"),
    ("docs/Bench_Runner_Guide.md", "Bench Runner Guide"),
    ("docs/Bench_Self_Check_Setup.md", "Bench Self-Check Setup"),
    ("docs/robot/Robot_Keyword_Catalogue.md", "Robot Keyword Catalogue"),
    ("docs/test_bench/Embedded_Test_Bench_Monitor.md", "Embedded Test Bench Monitor"),
    ("docs/README.md", "Documentation Overview"),
)

#: Instrument notes, in sidebar order: (path, label).
INSTRUMENTS = (
    ("docs/psu/GPD3303D_Notes.md", "GPD-3303D Power Supply"),
    ("docs/dmm/TTi1604_Notes.md", "TTi 1604 Multimeter"),
    ("docs/jlink/JLink_Integration_Notes.md", "SEGGER J-Link"),
    ("docs/s2lp/S2LP_Devkit_Notes.md", "S2-LP Development Kit"),
    ("docs/ble/BLE_Dongle_Notes.md", "Nordic BLE Dongle"),
    ("docs/pico_sht30/Pico_SHT30_Notes.md", "Pico 2 + SHT30-D Thermometer"),
    ("docs/tek3014b/VISA_Determination_Report.md", "TDS3014B Oscilloscope (VISA)"),
)

#: Published as pages and reached through links from their parent page, but
#: given no sidebar entry of their own.
SUPPORTING = (
    "docs/pico_sht30/References.md",
)

#: Wiki page names that differ from the file name, where the file name alone
#: would be too generic to identify the page.
SLUG_OVERRIDES = {
    "docs/README.md": "Documentation-Index",
    "docs/pico_sht30/References.md": "Pico-SHT30-References",
}

#: Not published as pages, by path prefix: run records and change records stay
#: in the repository, and a link to one points at the file there.
UNPUBLISHED = (
    "docs/aspice/qualification/",
    "docs/pico_sht30/Issue_104_Change_Report.md",
)

#: ASPICE process groups, in index and sidebar order: (filename code, group).
PROCESS_GROUPS = (
    ("SYS", "System Engineering (SYS)"),
    ("SWE", "Software Engineering (SWE)"),
    ("MAN", "Management (MAN)"),
    ("SUP", "Support Processes (SUP)"),
    ("ACQ", "Acquisition (ACQ)"),
    ("PA", "Capability Level 2 (PA 2.1 / PA 2.2)"),
    ("DEV", "Deviations (DEV)"),
)
OTHER_GROUP = "Other"
GROUP_ORDER = tuple(group for _, group in PROCESS_GROUPS) + (OTHER_GROUP,)

#: Brand artwork on the wiki (#194): the compact logo on Home and in the
#: sidebar, the GitHub header banner on ASPICE-Index. Each is linked as a raw
#: file on the ref, not copied into the wiki.
WIKI_LOGO = "assets/brand/png/logos/logo_compact.png"
WIKI_BANNER = "assets/brand/png/headers/github_header.png"

#: The PNG render of each brand SVG master. A wiki page shows the PNG, as the
#: brand README and #194 advise for the wiki, so an image in a document that
#: names the SVG master is pointed at its render on the wiki.
BRAND_PNG = {
    "assets/brand/svg/logos/embeddedtestbench-logo-compact.svg":
        "assets/brand/png/logos/logo_compact.png",
    "assets/brand/svg/logos/embeddedtestbench-logo-horizontal.svg":
        "assets/brand/png/logos/logo_horizontal.png",
    "assets/brand/svg/logos/embeddedtestbench-logo-monochrome.svg":
        "assets/brand/png/logos/logo_monochrome.png",
    "assets/brand/svg/headers/embeddedtestbench-github-header.svg":
        "assets/brand/png/headers/github_header.png",
    "assets/brand/svg/headers/embeddedtestbench-website-header.svg":
        "assets/brand/png/headers/website_header.png",
}

#: Copied onto the home page (#194): (repository path, path on gh-pages). The
#: website header banner tops the page; the favicons are linked from
#: ``_includes/head-custom.html``, which the Primer theme includes in <head>.
HOME_BANNER = ("assets/brand/svg/headers/embeddedtestbench-website-header.svg",
               "assets/embeddedtestbench-website-header.svg")
HOME_FAVICONS = (
    ("assets/brand/svg/icons/embeddedtestbench-favicon.svg",
     "assets/embeddedtestbench-favicon.svg"),
    ("assets/brand/png/favicon/favicon_32.png", "assets/favicon_32.png"),
    ("assets/brand/png/favicon/favicon.ico", "favicon.ico"),
)
HEAD_CUSTOM = "_includes/head-custom.html"

#: README lines that are only a brand image. The wiki Home page and the home
#: page carry their own brand artwork, so these are left out of the README
#: introduction they reuse.
_BRAND_IMG_LINE = re.compile(r"""^\s*<img\b[^>]*\bsrc=["']assets/brand/[^>]*>\s*$""", re.I)

SYS5_REPORT = "docs/aspice/EmbeddedTestBench_SYS5_002_System_Qualification_Test_Report.md"

_LINK = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)\)")
_ABSOLUTE = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|//|#)")
_FENCE = re.compile(r"^\s*(```|~~~)")
_IMG_SRC = re.compile(r"""(<img\b[^>]*?\bsrc=)(["'])([^"']+)\2""", re.I)
_FRONT_MATTER = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


class Site:
    """Where links point: the repository, the ref, and the published pages."""

    def __init__(self, root, repo, ref, pages, brand_png=False):
        self.root = Path(root)
        self.repo = repo
        self.ref = ref
        self.pages = pages  # repository-relative POSIX path -> wiki slug
        self.brand_png = brand_png  # show a brand SVG master as its PNG render

    @property
    def repo_url(self):
        """The repository's web address."""
        return "https://github.com/" + self.repo

    @property
    def pages_url(self):
        """The GitHub Pages address of the repository's home page."""
        owner, _, name = self.repo.partition("/")
        return "https://%s.github.io/%s/" % (owner.lower(), name)

    def file_url(self, rel, image=False):
        """The address of a repository file or directory at this ref."""
        if image:
            kind = "raw"
            if self.brand_png:
                rel = BRAND_PNG.get(rel, rel)
        elif (self.root / rel).is_dir():
            kind = "tree"
        else:
            kind = "blob"
        return "%s/%s/%s/%s" % (self.repo_url, kind, self.ref, quote(rel))


def read_text(path):
    """A file's text with LF line endings."""
    return Path(path).read_text(encoding="utf-8").replace("\r\n", "\n")


def write_text(path, text):
    """Write with LF line endings and exactly one trailing newline."""
    # Bytes, not write_text(newline=...), which needs Python 3.10.
    Path(path).write_bytes((text.rstrip("\n") + "\n").encode("utf-8"))


def aspice_stem(rel):
    """The document's name without the product or ASPICE prefix."""
    stem = posixpath.splitext(posixpath.basename(rel))[0]
    stem = re.sub(r"^EmbeddedTestBench_", "", stem)
    return re.sub(r"^ASPICE_", "", stem)


def is_aspice(rel):
    """True for an ASPICE work product or template."""
    return (posixpath.dirname(rel) == "docs/aspice"
            or (rel.startswith("docs/templates/") and "ASPICE" in rel))


def slug(rel):
    """The wiki page name for a repository-relative document path."""
    if is_aspice(rel):
        return "ASPICE-" + aspice_stem(rel).replace("_", "-")
    if rel in SLUG_OVERRIDES:
        return SLUG_OVERRIDES[rel]
    stem = posixpath.splitext(posixpath.basename(rel))[0]
    return re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-")


def aspice_display(rel):
    """The ASPICE document's name as shown in the index and sidebar."""
    return aspice_stem(rel).replace("_", " ")


def title_of(text, fallback):
    """The document's first level-one heading, or the fallback."""
    match = re.search(r"^# +(.+?)\s*$", text, re.M)
    return match.group(1) if match else fallback


def classify(rel):
    """The ASPICE process group a document belongs to, from its file name."""
    name = posixpath.basename(rel).upper()
    for code, group in PROCESS_GROUPS:
        if re.search(r"_%s\d" % code, name):
            return group
    return OTHER_GROUP


def doc_field(text, name):
    """A value from a document's identification table."""
    match = re.search(r"\|\s*\*\*%s\*\*\s*\|\s*([^|]+?)\s*\|" % re.escape(name), text)
    return match.group(1) if match else ""


def discover(root):
    """Every document published as a wiki page, as sorted relative paths."""
    found = []
    for path in sorted((Path(root) / "docs").rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        if not rel.startswith(UNPUBLISHED):
            found.append(rel)
    return found


def page_map(docs):
    """Map each document to its wiki page, refusing two documents on one page."""
    pages = {}
    owners = {}
    for rel in docs:
        name = slug(rel)
        if name in owners:
            raise ValueError("%s and %s would both publish to wiki page %s"
                             % (owners[name], rel, name))
        owners[name] = rel
        pages[rel] = name
    return pages


def _resolve(target, src_dir):
    """A relative link target as (repository path, anchor), or None to leave it."""
    if _ABSOLUTE.match(target):
        return None
    path, _, anchor = target.partition("#")
    rel = posixpath.normpath(posixpath.join(src_dir, path))
    if rel.startswith("../") or rel == "..":
        return None
    return rel, anchor


def _unfenced(lines):
    """The indices of the lines that are outside fenced code blocks."""
    fenced = None
    for index, line in enumerate(lines):
        fence = _FENCE.match(line)
        if fenced:
            if fence and fence.group(1) == fenced:
                fenced = None
        elif fence:
            fenced = fence.group(1)
        else:
            yield index


def rewrite_links(text, src_rel, site):
    """Rewrite the relative links in a document published from ``src_rel``.

    A link to a published document becomes a link to its wiki page, keeping any
    anchor. An image - Markdown or an HTML ``<img src>`` - points at the raw
    file, a directory at its tree and any other file at its blob, all on
    ``site.ref``. Absolute links, anchors and everything inside fenced code
    blocks are left alone.
    """
    src_dir = posixpath.dirname(src_rel)

    def fix(match):
        bang, label, target = match.group(1), match.group(2), match.group(3)
        resolved = _resolve(target, src_dir)
        if resolved is None:
            return match.group(0)
        rel, anchor = resolved
        suffix = "#" + anchor if anchor else ""
        if not bang and rel in site.pages:
            return "[%s](%s%s)" % (label, site.pages[rel], suffix)
        return "%s[%s](%s%s)" % (bang, label, site.file_url(rel, image=bool(bang)), suffix)

    def fix_img(match):
        resolved = _resolve(match.group(3), src_dir)
        if resolved is None:
            return match.group(0)
        quote_mark = match.group(2)
        return "%s%s%s%s" % (match.group(1), quote_mark,
                             site.file_url(resolved[0], image=True), quote_mark)

    lines = text.split("\n")
    for index in _unfenced(lines):
        lines[index] = _IMG_SRC.sub(fix_img, _LINK.sub(fix, lines[index]))
    return "\n".join(lines)


def document_page(rel, site, footer):
    """A document as a wiki page: links rewritten, its source noted, a footer.

    The source note goes under the first level-one heading, which need not be
    the first line: a document may open with a logo above its title.
    """
    text = _FRONT_MATTER.sub("", read_text(site.root / rel), count=1)
    lines = rewrite_links(text, rel, site).rstrip().split("\n")
    note = "*Source: [`%s`](%s)*" % (rel, site.file_url(rel))
    title = next((i for i in _unfenced(lines) if lines[i].startswith("# ")), -1)
    lines[title + 1:title + 1] = ["", note] if title >= 0 else [note, ""]
    return "\n".join(lines) + "\n\n---\n\n" + footer


def readme_intro(site):
    """The README's introduction: everything before its first ``##`` section.

    Lines that are only a brand image (the README's banner and logo) are left
    out: the pages that reuse the introduction carry their own artwork.
    """
    text = read_text(site.root / "README.md")
    intro = re.split(r"\n(?=## )", text, maxsplit=1)[0].rstrip()
    intro = re.sub(r"\n-{3,}$", "", intro).rstrip()
    lines = intro.split("\n")
    unfenced = set(_unfenced(lines))
    kept = [line for i, line in enumerate(lines)
            if i not in unfenced or not _BRAND_IMG_LINE.match(line)]
    intro = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
    return rewrite_links(intro, "README.md", site)


def brand_img(site, rel, width):
    """An HTML image of a brand asset, as its raw file on the ref."""
    return '<img src="%s" alt="Embedded Test Bench" width="%s">' % (
        site.file_url(rel, image=True), width)


def sidebar_entries(entries, site):
    """(label, slug) pairs for the listed documents that exist."""
    return [(label, site.pages[rel]) for rel, label in entries
            if (site.root / rel).is_file() and rel in site.pages]


def user_guides(site, others):
    """The User Guide entries: those listed, then any guide not listed anywhere."""
    listed = {rel for rel, _ in GUIDES + INSTRUMENTS} | set(SUPPORTING)
    return sidebar_entries(GUIDES, site) + [
        (title_of(read_text(site.root / rel), slug(rel)), site.pages[rel])
        for rel in others if rel not in listed]


def process_groups(aspice):
    """The ASPICE documents by process group."""
    groups = {}
    for rel in aspice:
        groups.setdefault(classify(rel), []).append(rel)
    return groups


def generate_wiki(out, root=ROOT, repo=DEFAULT_REPO, ref=DEFAULT_REF, clean=False):
    """Write every wiki page into ``out``; return the page names written."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if clean:
        for old in out.glob("*.md"):
            old.unlink()

    site = Site(root, repo, ref, page_map(discover(root)), brand_png=True)
    written = []

    def emit(name, text):
        write_text(out / (name + ".md"), text)
        written.append(name)

    aspice = [rel for rel in site.pages if is_aspice(rel)]
    others = [rel for rel in site.pages if not is_aspice(rel)]
    for rel in aspice:
        emit(site.pages[rel], document_page(
            rel, site, "*[[ASPICE Documentation Index|ASPICE-Index]]*"))
    for rel in others:
        emit(site.pages[rel], document_page(rel, site, "*[[Home]]*"))

    guides = user_guides(site, others)
    instruments = sidebar_entries(INSTRUMENTS, site)
    groups = process_groups(aspice)
    emit("Home", home_wiki_page(site, guides, instruments))
    emit("ASPICE-Index", aspice_index(site, aspice, groups))
    emit("_Sidebar", sidebar(site, guides, instruments, groups))
    return written


def wiki_list(entries):
    """Markdown list items linking to wiki pages."""
    return ["- [[%s|%s]]" % entry for entry in entries]


def home_wiki_page(site, guides, instruments):
    """The wiki's Home page: the logo, the README introduction and the contents."""
    lines = [brand_img(site, WIKI_LOGO, 240), "", readme_intro(site), "",
             "---", "", "## User Guide", ""]
    lines += wiki_list(guides)
    lines += ["", "## Instruments", ""] + wiki_list(instruments)
    lines += ["", "## ASPICE CL2 Documentation", "",
              "- [[ASPICE Documentation Index|ASPICE-Index]]", "",
              "## Elsewhere", "",
              "- [Home page](%s)" % site.pages_url,
              "- [Full README](%s)" % site.file_url("README.md"),
              "- [Latest release](%s/releases/latest)" % site.repo_url,
              "", "---", "",
              "*Generated from the `%s` branch by `scripts/publish_docs.py`. "
              "The repository holds the controlled copies; these pages are not edited "
              "by hand.*" % site.ref]
    return "\n".join(lines)


def aspice_index(site, aspice, groups):
    """The ASPICE-Index page: the banner, documents by process group, then by ID."""
    lines = [brand_img(site, WIKI_BANNER, "100%"), "", "# ASPICE CL2 Documentation", "",
             "**Embedded Test Bench** | Automotive SPICE® PAM v4.0 | Capability Level 2", "",
             "*Generated from `docs/aspice/` on the `%s` branch.*" % site.ref, "",
             "This section contains the ASPICE CL2 work products for Embedded Test Bench. "
             "The documents in the repository are the controlled copies; these pages are "
             "generated from them and are not edited by hand.", "",
             "---", ""]
    for group in GROUP_ORDER:
        if groups.get(group):
            lines += ["## %s" % group, ""]
            lines += wiki_list((aspice_display(rel), site.pages[rel]) for rel in groups[group])
            lines.append("")
    rows = []
    for rel in aspice:
        text = read_text(site.root / rel)
        rows.append((doc_field(text, "Document ID"), doc_field(text, "Related Process"), rel))
    lines += ["---", "", "## Document ID Reference", "",
              "| Document ID | Process | Page |", "|---|---|---|"]
    for doc_id, process, rel in sorted(rows):
        lines.append("| %s | %s | [[%s|%s]] |"
                     % (doc_id, process, aspice_display(rel), site.pages[rel]))
    source = site.file_url("docs/aspice")
    lines += ["", "---", "", "*Source: [%s](%s)*" % (source, source)]
    return "\n".join(lines)


def sidebar(site, guides, instruments, groups):
    """The _Sidebar page: the logo, user guides, instruments, then ASPICE by process."""
    lines = [brand_img(site, WIKI_LOGO, 180), "",
             "## [[Embedded Test Bench|Home]]", "", "**User Guide**", ""]
    lines += wiki_list(guides)
    lines += ["", "**Instruments**", ""] + wiki_list(instruments)
    lines += ["", "---", "", "**ASPICE CL2 Docs**", "",
              "[[Documentation Index|ASPICE-Index]]", ""]
    for group in GROUP_ORDER:
        if groups.get(group):
            short = re.sub(r"\s*\(.*\)$", "", group)
            lines.append("*%s*" % short)
            lines += wiki_list((aspice_display(rel), slug(rel)) for rel in groups[group])
            lines.append("")
    return "\n".join(lines)


def generate_home(out, root=ROOT, repo=DEFAULT_REPO, ref=DEFAULT_REF):
    """Write the GitHub Pages home page into ``out``; return the files written."""
    out = Path(out)
    site = Site(root, repo, ref, {})
    copied = []
    for source, target in (HOME_BANNER,) + HOME_FAVICONS:
        (out / target).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(Path(root) / source), str(out / target))
        copied.append(target)

    intro = readme_intro(site).split("\n")
    title = next((i for i in _unfenced(intro) if intro[i].startswith("# ")), None)
    if title is not None:
        del intro[title]
    wiki = site.repo_url + "/wiki"
    # The theme's page header already shows the site title from _config.yml.
    lines = ["![Embedded Test Bench](%s)" % HOME_BANNER[1], ""]
    lines += ["\n".join(intro).strip(), "", "## Links", "",
              "- [Documentation wiki](%s)" % wiki,
              "- [Latest release](%s/releases/latest)" % site.repo_url,
              "- [System qualification test report (ETB-SYS5-002)](%s/%s)"
              % (wiki, slug(SYS5_REPORT)),
              "- [Source repository](%s)" % site.repo_url,
              "", "---", "",
              "*Generated from `README.md` on the `%s` branch by `scripts/publish_docs.py`. "
              "This branch is not edited by hand.*" % ref]
    write_text(out / "README.md", "\n".join(lines))
    write_text(out / "_config.yml", "\n".join([
        "# Generated by scripts/publish_docs.py - not edited by hand.",
        "title: Embedded Test Bench",
        "description: Bench test tooling - instrument drivers, a debug probe driver "
        "and a declarative test runner.",
    ]))
    write_head_custom(out)
    return ["README.md", "_config.yml", HEAD_CUSTOM] + copied


def write_head_custom(out):
    """Write the <head> include that links the favicons.

    The Primer theme's layout includes ``_includes/head-custom.html`` in <head>;
    this replaces the theme's own, which holds only commented-out examples.
    """
    (out / HEAD_CUSTOM).parent.mkdir(parents=True, exist_ok=True)
    href = "{{ '/%s' | relative_url }}"
    svg, png, ico = (href % target for _, target in HOME_FAVICONS)
    write_text(out / HEAD_CUSTOM, "\n".join([
        "<!-- Generated by scripts/publish_docs.py - not edited by hand. -->",
        '<link rel="icon" type="image/svg+xml" href="%s">' % svg,
        '<link rel="icon" type="image/png" sizes="32x32" href="%s">' % png,
        '<link rel="shortcut icon" type="image/x-icon" href="%s">' % ico,
    ]))


def main(argv=None):
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("what", choices=("wiki", "home"), help="which output to generate")
    parser.add_argument("out", help="directory to write into")
    parser.add_argument("--ref", default=DEFAULT_REF,
                        help="branch that links to repository files point at (default: main)")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="owner/name of the repository")
    parser.add_argument("--clean", action="store_true",
                        help="wiki: remove the existing top-level pages first")
    args = parser.parse_args(argv)
    if args.what == "wiki":
        written = generate_wiki(args.out, repo=args.repo, ref=args.ref, clean=args.clean)
    else:
        written = generate_home(args.out, repo=args.repo, ref=args.ref)
    print("%s: wrote %d file(s) to %s" % (args.what, len(written), args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
