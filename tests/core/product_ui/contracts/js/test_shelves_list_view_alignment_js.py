from pathlib import Path

import pytest

from tests.core.product_ui.js import REPOSITORY_ROOT as ROOT
from tests.core.product_ui.js import run_node_json


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


def test_shelves_list_scope_page_and_page_size_are_url_backed():
    module_uri = (ROOT / "web/static/web/js/shelves/list.js").as_uri()
    result = run_node_json(
        f"""
        const mod = await import("{module_uri}");
        console.log(JSON.stringify({{
          state: mod.shelfListState("?scope=shared&page=3&page_size=40"),
          browser: mod.shelfListBrowserHref("shared", 3, 40, "?unused=kept"),
          api: mod.shelfListApiUrl("shared", 3, 40),
        }}));
        """
    )

    assert result["state"] == {"scope": "shared", "page": 3, "pageSize": 40}
    assert result["browser"] == "/shelves/?unused=kept&scope=shared&page=3&page_size=40"
    assert result["api"] == (
        "/api/v1/shelves/?scope=shared&include_preview_books=true"
        "&page_size=40&page=3"
    )


def test_shelf_view_page_size_and_ordering_are_url_backed():
    module_uri = (ROOT / "web/static/web/js/shelves/view.js").as_uri()
    result = run_node_json(
        f"""
        const mod = await import("{module_uri}");
        const state = mod.shelfViewListState("?ordering=position&page=2&page_size=30");
        console.log(JSON.stringify({{
          state,
          browser: mod.shelfViewBrowserHref("shelf-id", state),
        }}));
        """
    )

    assert result["state"] == {
        "page": 2,
        "pageSize": 30,
        "ordering": "position",
    }
    assert result["browser"] == (
        "/shelves/shelf-id/?page=2&page_size=30&ordering=position"
    )


def test_shelf_lists_use_library_pagers_and_restore_history_state():
    list_js = Path("web/static/web/js/shelves/list.js").read_text(encoding="utf-8")
    view_js = Path("web/static/web/js/shelves/view.js").read_text(encoding="utf-8")

    for source in (list_js, view_js):
        assert 'window.addEventListener("popstate"' in source
        assert "page_size" in source
        assert 'reason: "page-size"' in source or 'history: "push"' in source
    assert "page: 1, pageSize: nextPageSize" in list_js
    assert "page: 1, pageSize: nextPageSize" in view_js


def test_shelf_view_uses_safe_library_rows_shared_metadata_and_optional_tags():
    view_js = Path("web/static/web/js/shelves/view.js").read_text(encoding="utf-8")

    assert 'el("article", "library-row")' in view_js
    assert 'el("div", "library-row__body")' in view_js
    assert 'el("h3", "library-row__title")' in view_js
    assert '"library-row__meta book-metadata"' in view_js
    assert "bookMetadataItems(book)" in view_js
    assert "Array.isArray(book.tags)" in view_js
    assert 'el("span", "pill", tag)' in view_js
    assert "link.href = `/library/books/${encodeURIComponent(bookId)}/`" in view_js
    assert view_js.count('const link = el("a"') == 1
    for sensitive in (
        "download_url",
        "checksum",
        "storage_path",
        "source_filename",
    ):
        assert sensitive not in view_js


def test_shelf_description_is_subtle_user_text_without_a_card_or_quote_block():
    template = Path("web/templates/web/shelves/detail.html").read_text(
        encoding="utf-8"
    )
    css = Path("web/static/web/css/groups-shelves.css").read_text(encoding="utf-8")

    assert '<p id="shelf-view-description"' in template
    description_css = css.split(".shelf-view-description {", 1)[1].split("}", 1)[0]
    assert "color: var(--muted)" in description_css
    assert "font-style: italic" in description_css
    assert "white-space: pre-wrap" in description_css
    assert "background" not in description_css
    assert "border" not in description_css
    assert "blockquote" not in template
