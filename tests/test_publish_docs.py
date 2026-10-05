"""The wiki and home page generator in scripts/publish_docs.py.

The wiki and the gh-pages home page are generated from the repository and never
edited by hand (ETB-SUP8-001 §5.7), so the generator is what has to be right:
page names, link rewriting, the sidebar reaching every guide, and a second run
over unchanged content producing exactly the same files.

Traces to: SWE4-UT-PUBLISH.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_publish():
    spec = importlib.util.spec_from_file_location(
        "publish_docs_script", ROOT / "scripts" / "publish_docs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


publish = load_publish()


def site(pages=None, root=ROOT):
    return publish.Site(root, "owner/Repo", "main", pages or {})


class TestSlugs:
    @pytest.mark.parametrize("rel, expected", [
        ("docs/aspice/EmbeddedTestBench_SWE1_SW_Requirements.md", "ASPICE-SWE1-SW-Requirements"),
        ("docs/aspice/EmbeddedTestBench_SYS5_002_System_Qualification_Test_Report.md",
         "ASPICE-SYS5-002-System-Qualification-Test-Report"),
        ("docs/templates/ASPICE_CL2_Test_Case_Template_1.md", "ASPICE-CL2-Test-Case-Template-1"),
        ("docs/Bench_Runner_Guide.md", "Bench-Runner-Guide"),
        ("docs/psu/GPD3303D_Notes.md", "GPD3303D-Notes"),
        ("docs/README.md", "Documentation-Index"),
        ("docs/pico_sht30/References.md", "Pico-SHT30-References"),
    ])
    def test_page_names(self, rel, expected):
        assert publish.slug(rel) == expected

    def test_two_documents_on_one_page_are_refused(self):
        with pytest.raises(ValueError, match="Bench-Runner-Guide"):
            publish.page_map(["docs/Bench_Runner_Guide.md", "docs/x/Bench_Runner_Guide.md"])

    def test_every_repository_document_has_its_own_page(self):
        assert len(publish.page_map(publish.discover(ROOT))) > 40

    def test_qualification_run_records_are_not_pages(self):
        assert not [rel for rel in publish.discover(ROOT) if "/qualification/" in rel]

    @pytest.mark.parametrize("name, group", [
        ("EmbeddedTestBench_ACQ4_Supplier_Monitoring_Plan.md", "Acquisition (ACQ)"),
        ("EmbeddedTestBench_SUP8_Configuration_Management_Plan.md", "Support Processes (SUP)"),
        ("EmbeddedTestBench_Traceability_Matrix.md", "Other"),
    ])
    def test_process_group_comes_from_the_code_and_a_digit(self, name, group):
        assert publish.classify("docs/aspice/" + name) == group


class TestLinkRewriting:
    PAGES = {"docs/aspice/A_SWE1.md": "ASPICE-SWE1", "docs/Guide.md": "Guide"}

    def rewrite(self, text, src="docs/aspice/A_SYS2.md"):
        return publish.rewrite_links(text, src, site(self.PAGES))

    def test_a_published_document_becomes_its_wiki_page_keeping_the_anchor(self):
        assert self.rewrite("[r](A_SWE1.md#3-scope)") == "[r](ASPICE-SWE1#3-scope)"

    def test_a_link_up_a_directory_resolves_against_the_source(self):
        assert self.rewrite("[g](../Guide.md)") == "[g](Guide)"

    def test_any_other_file_points_at_its_blob_on_the_ref(self):
        assert (self.rewrite("[s](../../specs/x.yaml#L3)")
                == "[s](https://github.com/owner/Repo/blob/main/specs/x.yaml#L3)")

    def test_a_directory_points_at_its_tree(self):
        assert (self.rewrite("[d](../../benchtools)")
                == "[d](https://github.com/owner/Repo/tree/main/benchtools)")

    def test_an_image_points_at_the_raw_file_even_if_it_is_a_document(self):
        assert (self.rewrite("![i](../Guide.md)")
                == "![i](https://github.com/owner/Repo/raw/main/docs/Guide.md)")

    @pytest.mark.parametrize("text", [
        "[a](https://example.com/x.md)", "[a](#local)", "[a](mailto:x@y.z)",
        "[a](../../../outside.md)",
    ])
    def test_absolute_links_anchors_and_escapes_are_left_alone(self, text):
        assert self.rewrite(text) == text

    def test_an_html_image_points_at_the_raw_file(self):
        logo = '<img src="../../assets/brand/svg/logos/logo.svg" alt="ETB" width="240">'
        assert self.rewrite(logo) == (
            '<img src="https://github.com/owner/Repo/raw/main/assets/brand/svg/logos/logo.svg"'
            ' alt="ETB" width="240">')

    def test_an_absolute_html_image_is_left_alone(self):
        logo = "<img alt='x' src='https://example.com/logo.svg'>"
        assert self.rewrite(logo) == logo

    def test_links_inside_a_fenced_block_are_left_alone(self):
        text = "```\n[r](A_SWE1.md)\n```\n[r](A_SWE1.md)"
        assert self.rewrite(text) == "```\n[r](A_SWE1.md)\n```\n[r](ASPICE-SWE1)"


class TestDocumentPage:
    def page(self, tmp_path, text):
        rel = "docs/aspice/X_SWE1.md"
        (tmp_path / "docs" / "aspice").mkdir(parents=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
        return publish.document_page(rel, site(root=tmp_path), "footer").split("\n")

    def test_the_source_note_goes_under_the_title(self, tmp_path):
        lines = self.page(tmp_path, "# Title\n\nBody\n")
        assert lines[:4] == ["# Title", "", "*Source: [`docs/aspice/X_SWE1.md`]"
                             "(https://github.com/owner/Repo/blob/main/docs/aspice/X_SWE1.md)*",
                             ""]

    def test_a_logo_above_the_title_is_kept_and_rewritten(self, tmp_path):
        lines = self.page(tmp_path, '<img src="../../assets/logo.svg" alt="ETB" width="240">\n'
                                    "# Title\n\nBody\n")
        assert lines[0] == ('<img src="https://github.com/owner/Repo/raw/main/assets/logo.svg"'
                            ' alt="ETB" width="240">')
        assert lines[1] == "# Title"
        assert lines[3].startswith("*Source: ")

    def test_a_document_without_a_title_gets_the_note_first(self, tmp_path):
        lines = self.page(tmp_path, "Body only\n")
        assert lines[0].startswith("*Source: ") and lines[2] == "Body only"


@pytest.fixture(scope="module")
def wiki(tmp_path_factory):
    out = tmp_path_factory.mktemp("wiki")
    (out / "Stale-Page.md").write_text("left over\n")
    publish.generate_wiki(out, clean=True)
    return out


class TestGeneratedWiki:
    def test_clean_removes_pages_that_are_no_longer_generated(self, wiki):
        assert not (wiki / "Stale-Page.md").exists()

    def test_the_sidebar_reaches_every_page_except_supporting_ones(self, wiki):
        sidebar = (wiki / "_Sidebar.md").read_text(encoding="utf-8")
        supporting = {publish.slug(rel) for rel in publish.SUPPORTING}
        unreached = [page.stem for page in wiki.glob("*.md")
                     if page.stem not in {"Home", "_Sidebar"} | supporting
                     and "|%s]]" % page.stem not in sidebar]
        assert not unreached

    def test_a_supporting_page_is_linked_from_another_page(self, wiki):
        text = "".join(p.read_text(encoding="utf-8") for p in wiki.glob("*.md"))
        for rel in publish.SUPPORTING:
            assert "](%s" % publish.slug(rel) in text

    def test_every_wiki_link_names_a_generated_page(self, wiki):
        pages = {page.stem for page in wiki.glob("*.md")}
        text = "".join(p.read_text(encoding="utf-8") for p in wiki.glob("*.md"))
        named = set(re.findall(r"\[\[[^|\]]*\|([^\]]+)\]\]", text))
        named |= set(re.findall(r"\]\(([A-Za-z][\w-]*)(?:#[^)]*)?\)", text))
        assert named - pages - {"Home"} == set()

    def test_a_second_run_changes_nothing(self, wiki, tmp_path):
        publish.generate_wiki(tmp_path)
        first = {p.name: p.read_bytes() for p in wiki.glob("*.md")}
        second = {p.name: p.read_bytes() for p in tmp_path.glob("*.md")}
        assert first == second

    def test_pages_have_lf_line_endings(self, wiki):
        assert not [p.name for p in wiki.glob("*.md") if b"\r\n" in p.read_bytes()]


_RAW_IMG = re.compile(r'<img src="https://github\.com/dermot-murphy/EmbeddedTestBench/raw/main/'
                      r'([^"]+)" alt="Embedded Test Bench" width="[^"]+">')


class TestWikiBrand:
    """The logo and banner on the wiki (#194)."""

    def first_image(self, wiki, page):
        first = (wiki / (page + ".md")).read_text(encoding="utf-8").split("\n")[0]
        match = _RAW_IMG.fullmatch(first)
        assert match, first
        return match.group(1)

    def test_home_and_the_sidebar_open_with_the_compact_logo(self, wiki):
        assert self.first_image(wiki, "Home") == publish.WIKI_LOGO
        assert self.first_image(wiki, "_Sidebar") == publish.WIKI_LOGO

    def test_the_aspice_index_opens_with_the_header_banner(self, wiki):
        assert self.first_image(wiki, "ASPICE-Index") == publish.WIKI_BANNER

    def test_the_readme_artwork_is_not_repeated_on_home(self, wiki):
        home = (wiki / "Home.md").read_text(encoding="utf-8")
        assert home.count("<img ") == 1 and "# EmbeddedTestBench" in home

    def test_a_document_logo_is_shown_as_its_png_render(self, wiki):
        page = (wiki / "ASPICE-SUP8-Configuration-Management-Plan.md").read_text(encoding="utf-8")
        assert self.first_image(wiki, "ASPICE-SUP8-Configuration-Management-Plan") == (
            "assets/brand/png/logos/logo_compact.png")
        assert ".svg" not in page.split("\n")[0]

    def test_every_brand_image_on_the_wiki_is_a_png_that_exists(self, wiki):
        text = "".join(p.read_text(encoding="utf-8") for p in wiki.glob("*.md"))
        images = set(re.findall(r"/raw/main/(assets/brand/[^\")\s]+)", text))
        assert images
        assert not [rel for rel in images
                    if not rel.endswith(".png") or not (ROOT / rel).is_file()]

    def test_every_brand_svg_has_an_existing_png_render(self):
        for svg, png in publish.BRAND_PNG.items():
            assert (ROOT / svg).is_file() and (ROOT / png).is_file()


def test_the_home_page_carries_the_banner_and_the_links(tmp_path):
    written = publish.generate_home(tmp_path, repo="owner/Repo")
    assert all((tmp_path / name).is_file() for name in written)
    page = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert page.startswith("![Embedded Test Bench](%s)\n" % publish.HOME_BANNER[1])
    assert "assets/brand/" not in page
    assert "https://github.com/owner/Repo/wiki" in page
    assert "https://github.com/owner/Repo/releases/latest" in page
    assert "/wiki/ASPICE-SYS5-002-System-Qualification-Test-Report" in page


def test_the_home_page_head_links_every_favicon_it_copies(tmp_path):
    written = publish.generate_home(tmp_path, repo="owner/Repo")
    head = (tmp_path / "_includes" / "head-custom.html").read_text(encoding="utf-8")
    linked = re.findall(r"href=\"\{\{ '/([^']+)' \| relative_url \}\}\"", head)
    assert linked == [target for _, target in publish.HOME_FAVICONS]
    assert all(target in written for target in linked)
    assert (tmp_path / "favicon.ico").read_bytes() == (
        ROOT / "assets/brand/png/favicon/favicon.ico").read_bytes()


def test_the_pages_address_is_derived_from_the_repository():
    assert site().pages_url == "https://owner.github.io/Repo/"
