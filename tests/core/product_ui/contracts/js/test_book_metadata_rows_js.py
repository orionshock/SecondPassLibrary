from pathlib import Path

import pytest

from tests.core.product_ui.js import REPOSITORY_ROOT as ROOT
from tests.core.product_ui.js import run_node_json


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


def test_shared_book_metadata_renders_icons_accessible_labels_and_escaped_values():
    module_uri = (ROOT / "web/static/web/js/ui/book_metadata.js").as_uri()
    result = run_node_json(
        f"""
        const mod = await import("{module_uri}");
        const html = mod.renderBookMetadataHtml({{
          authors: [{{ name: "Ada <script>bad()</script>" }}],
          series: {{ name: "Series & <b>unsafe</b>", series_index: "2" }},
          publisher: "Press <img src=x onerror=bad()>",
          published_date: "2024-06-01",
          download_url: "SECRET_DOWNLOAD",
          checksum: "SECRET_CHECKSUM",
          storage_path: "SECRET_STORAGE",
          source_filename: "SECRET_SOURCE",
        }});
        console.log(JSON.stringify({{ html }}));
        """
    )

    html = result["html"]
    for icon in ("person", "auto_stories", "apartment"):
        assert f'aria-hidden="true">{icon}</span>' in html
    for label in ("Author: ", "Series: ", "Publisher: "):
        assert f'<span class="sr-only">{label}</span>' in html
    assert "&lt;script&gt;bad()&lt;/script&gt;" in html
    assert "Series &amp; &lt;b&gt;unsafe&lt;/b&gt; 2" in html
    assert "Press &lt;img src=x onerror=bad()&gt; 2024" in html
    assert "<script>" not in html
    assert "<a " not in html
    assert "metadata-piece" not in html
    for secret in ("SECRET_DOWNLOAD", "SECRET_CHECKSUM", "SECRET_STORAGE", "SECRET_SOURCE"):
        assert secret not in html


def test_compact_book_surfaces_share_metadata_renderer_and_keep_title_links():
    sources = {
        path: Path(path).read_text(encoding="utf-8")
        for path in (
            "web/static/web/js/library/list.js",
            "web/static/web/js/groups/view_renderers.js",
            "web/static/web/js/groups/shared.js",
            "web/static/web/js/shelves/view.js",
            "web/static/web/js/shelves/items.js",
            "web/static/web/js/shelves/book_search.js",
        )
    }

    for path, source in sources.items():
        assert "book_metadata.js" in source, path
    for path in (
        "web/static/web/js/library/list.js",
        "web/static/web/js/groups/view_renderers.js",
        "web/static/web/js/groups/shared.js",
        "web/static/web/js/shelves/items.js",
        "web/static/web/js/shelves/book_search.js",
    ):
        assert "book-metadata" in sources[path]
    assert "libraryBookDetailHref(b.id, context)" in sources["web/static/web/js/library/list.js"]
    assert "/library/books/${encodeURIComponent" in sources["web/static/web/js/groups/view_renderers.js"]
    assert "/library/books/${encodeURIComponent" in sources["web/static/web/js/shelves/book_search.js"]


def test_book_metadata_css_uses_compact_wrapping_groups_without_dot_separators():
    css = Path("web/static/web/css/library.css").read_text(encoding="utf-8")

    assert ".book-metadata__item" in css
    assert ".book-metadata__icon.material-symbols-outlined" in css
    assert "font-size: 16px" in css
    assert "opacity: 0.62" in css
    assert "flex-wrap: wrap" in css
    metadata_css = css.split(".book-metadata {", 1)[1].split("}", 1)[0]
    assert "gap:" in metadata_css
    assert "content:" not in metadata_css


def test_ui_docs_define_shared_accessible_compact_book_icon_vocabulary():
    docs = Path("docs/ui.md").read_text(encoding="utf-8")

    assert "### Product UI icon conventions" in docs
    assert "Material Symbols Outlined" in docs
    assert '`aria-hidden="true"`' in docs
    assert "Author is `person`" in docs
    assert "Series is `auto_stories`" in docs
    assert "Publisher is" in docs and "`apartment`" in docs
    assert "visually hidden Author, Series, or Publisher" in docs
    assert "values are not links" in docs
    assert "book title remains the primary" in docs
    assert "Do not add" in docs and "dot separators" in docs
    assert "Library book rows" in docs
    assert "Group View book rows" in docs
    assert "Group Edit assigned and add-book rows" in docs
    assert "Shelf View item rows" in docs
    assert "Shelf Edit item and add-book rows" in docs
    assert "Avoid `menu_book` for Series" in docs
    assert "Avoid `store` for Publisher" in docs


def test_ui_docs_record_reader_client_icon_vocabulary_for_consistent_reuse():
    docs = Path("docs/ui.md").read_text(encoding="utf-8")

    assert "#### Reader-client icon reference" in docs
    assert "Product UI surfaces are not required to use these icons" in docs
    assert "represent the same action or concept with an icon" in docs
    assert "prefer the" in docs and "same token" in docs
    for token in (
        "arrow_back",
        "arrow_forward",
        "auto_stories",
        "bookmark",
        "bookmark_add",
        "bookmark_added",
        "border_color",
        "chat_bubble",
        "check",
        "check_circle",
        "chevron_left",
        "chevron_right",
        "close",
        "delete",
        "done",
        "edit",
        "edit_note",
        "expand_more",
        "flag",
        "format_list_numbered",
        "groups",
        "home",
        "ink_highlighter",
        "keyboard_arrow_down",
        "keyboard_arrow_up",
        "library_books",
        "link",
        "local_library",
        "menu",
        "menu_book",
        "more_vert",
        "my_location",
        "open_in_new",
        "person",
        "public",
        "radio_button_unchecked",
        "search",
        "settings",
        "sort_by_alpha",
    ):
        assert f"| `{token}` |" in docs
