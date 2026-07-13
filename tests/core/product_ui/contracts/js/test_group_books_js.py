from pathlib import Path

import pytest

from tests.core.product_ui.helpers import ProductUiTestCase


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


class ProductUiGroupBooksJsContractsTests(ProductUiTestCase):
    def setUp(self):
        super().setUp()
        self.source = Path("web/static/web/js/groups/books.js").read_text(
            encoding="utf-8"
        )

    def test_add_book_uses_current_book_id_payload(self):
        self.assertIn("JSON.stringify({ book_id: bookId })", self.source)
        self.assertNotIn("JSON.stringify({ book: bookId })", self.source)

    def test_series_index_uses_nested_current_book_shape(self):
        self.assertIn("b.series.series_index != null", self.source)
        self.assertIn("String(b.series.series_index)", self.source)
        self.assertNotIn("b.series_index != null", self.source)

    def test_remove_route_keeps_group_and_book_uuids(self):
        self.assertIn("/books/${encodeURIComponent(", self.source)
        self.assertIn("String(groupId)", self.source)
        self.assertIn("String(bookId)", self.source)
        self.assertIn('{ method: "DELETE", headers }', self.source)

    def test_mutation_errors_prefer_bounded_fields_and_hide_raw_bodies(self):
        self.assertIn("export function groupBookMutationError", self.source)
        self.assertIn("summarizeFieldErrors", self.source)
        self.assertIn('typeof error.body === "object"', self.source)
        self.assertIn("Failed to add book to group.", self.source)
        self.assertIn("Failed to remove book from group.", self.source)
        self.assertNotIn("setBookSearchStatus(extractApiErrorMessage(e2)", self.source)
        self.assertNotIn("setStatus(booksStatus, extractApiErrorMessage(e2)", self.source)
