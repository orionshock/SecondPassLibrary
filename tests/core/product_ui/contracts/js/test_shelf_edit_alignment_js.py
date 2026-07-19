from pathlib import Path

import pytest


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


def test_shelf_edit_tabs_sections_and_delete_panel_follow_layout_contract():
    template = Path("web/templates/web/shelves/edit.html").read_text(
        encoding="utf-8"
    )

    details = template.index('data-tab="details"')
    books = template.index('data-tab="books"')
    add = template.index('data-tab="add"')
    assert details < books < add
    assert ">Details</button>" in template
    assert ">Books</button>" in template
    assert ">Add Books</button>" in template
    assert "Books in shelf" not in template
    assert "View shelf" not in template
    assert "View group" not in template
    assert 'class="shelf-edit-section' in template
    assert 'id="shelf-edit-items" class="card' not in template
    assert 'id="shelf-edit-add" class="card' not in template
    assert 'id="shelf-edit" class="card' not in template
    assert '<details id="shelf-edit-danger"' in template
    assert "<summary class=\"danger-zone__summary\">Delete Shelf</summary>" in template
    assert "<details id=\"shelf-edit-danger\"" in template
    assert " open" not in template.split('<details id="shelf-edit-danger"', 1)[1].split(">", 1)[0]
    assert template.index('id="shelf-edit-delete-btn"') > template.index('<details id="shelf-edit-danger"')


def test_shelf_edit_details_are_bounded_vertical_and_actions_align_right():
    template = Path("web/templates/web/shelves/edit.html").read_text(
        encoding="utf-8"
    )
    css = Path("web/static/web/css/groups-shelves.css").read_text(encoding="utf-8")

    assert 'class="shelf-edit-form"' in template
    assert template.count('class="shelf-edit-form__field"') == 3
    assert 'class="shelf-edit-form__actions"' in template
    assert "width: min(100%, 720px)" in css
    assert ".shelf-edit-form__field {" in css
    assert "justify-content: flex-end" in css


def test_delete_shelf_confirmation_guards_delete_request():
    source = Path("web/static/web/js/shelves/edit.js").read_text(encoding="utf-8")

    confirmation = 'window.confirm(`Permanently delete ${shelfName || "this shelf"}? This cannot be undone.`)'
    assert confirmation in source
    confirm_index = source.index(confirmation)
    cancel_index = source.index("if (!ok) return;", confirm_index)
    delete_index = source.index('method: "DELETE"', cancel_index)
    assert confirm_index < cancel_index < delete_index


def test_shelf_edit_books_and_add_results_use_library_rows_and_safe_metadata():
    items = Path("web/static/web/js/shelves/items.js").read_text(encoding="utf-8")
    search = Path("web/static/web/js/shelves/book_search.js").read_text(
        encoding="utf-8"
    )

    for source in (items, search):
        assert 'class="library-row shelf-edit-book-row"' in source
        assert 'class="library-row__title"' in source
        assert 'class="library-row__meta book-metadata"' in source
        assert "renderBookMetadataHtml(b)" in source
        assert "/library/books/${encodeURIComponent(bid)}/" in source
        for sensitive in (
            "download_url",
            "checksum",
            "storage_path",
            "source_filename",
        ):
            assert sensitive not in source
    assert 'class="shelf-edit-book-row__actions"' in items
    for action in ("move-up", "move-down", "move-to", "remove-item"):
        assert f'data-action="{action}"' in items
    assert 'aria-label="Move ${escapeHtml(title)} to position"' in items
    assert 'data-action="add-book"' in search


def test_shelf_edit_books_have_library_pagers_and_page_size_reset():
    template = Path("web/templates/web/shelves/_edit_items_pager.html").read_text(
        encoding="utf-8"
    )
    items = Path("web/static/web/js/shelves/items.js").read_text(encoding="utf-8")

    assert "library-pager" in template
    assert "library-pager--sticky" in template
    assert "Per page" in template
    assert "Previous" in template
    assert "Next" in template
    assert "currentPage = 1" in items
    assert "page_size=${currentPageSize}" in items
