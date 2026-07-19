from pathlib import Path

import pytest


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


class TestShelfBookSearchJavaScriptContracts:
    def setup_method(self):
        self.source = Path("web/static/web/js/shelves/book_search.js").read_text(
            encoding="utf-8"
        )

    def test_picker_uses_bookverse_search_and_shelf_exclusion(self):
        self.assert_source("/api/v1/library/search?")
        self.assert_source('ordering: "title"')
        self.assert_source("exclude_shelf: String(shelfId)")
        assert "/api/v1/library/books/" not in self.source
        assert "/api/v1/library/groups/" not in self.source

    def test_picker_keeps_existing_safe_rendering_and_bounded_errors(self):
        for contract in (
            "escapeHtml(title)",
            "escapeHtml(meta)",
            "mountCovers(searchResults)",
            "extractApiErrorMessage(e2)",
            'data-action="add-book"',
            'JSON.stringify({ book: bookId })',
        ):
            self.assert_source(contract)

    def assert_source(self, value: str):
        assert value in self.source
