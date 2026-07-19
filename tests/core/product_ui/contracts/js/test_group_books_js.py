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

    def test_book_rows_use_shared_library_style_presentation(self):
        shared = Path("web/static/web/js/groups/shared.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('class="library-row group-edit-book-row"', shared)
        self.assertIn('class="library-row__title"', shared)
        self.assertIn('class="library-row__meta"', shared)
        self.assertIn("b.series.series_index != null", shared)
        self.assertIn("b.publisher", shared)
        self.assertIn("b.published_date", shared)
        self.assertIn('data-action="remove-book"', shared)
        self.assertIn('data-action="add-book"', shared)

    def test_remove_route_keeps_group_and_book_uuids(self):
        self.assertIn("/books/${encodeURIComponent(", self.source)
        self.assertIn("String(groupId)", self.source)
        self.assertIn("String(bookId)", self.source)
        self.assertIn('{ method: "DELETE", headers }', self.source)

    def test_mutation_errors_prefer_bounded_fields_and_hide_raw_bodies(self):
        self.assertIn("groupMutationErrorMessage", self.source)
        self.assertIn("Failed to add book to group.", self.source)
        self.assertIn("Failed to remove book from group.", self.source)
        self.assertNotIn("groupBookMutationError", self.source)
        self.assertNotIn("setBookSearchStatus(extractApiErrorMessage(e2)", self.source)
        self.assertNotIn("setStatus(booksStatus, extractApiErrorMessage(e2)", self.source)

    def test_add_picker_uses_server_side_complete_group_exclusion(self):
        self.assertIn("/api/v1/library/search?", self.source)
        self.assertIn('ordering: "title"', self.source)
        self.assertIn("exclude_group: String(groupId)", self.source)
        self.assertNotIn("/api/v1/library/books/?${params.toString()}", self.source)
        self.assertNotIn("fetchAllPaginatedResults", self.source)
        self.assertNotIn("groupBookIds", self.source)
        self.assertNotIn("page_size=", self.source)

    def test_add_picker_keeps_existing_rendering_pagination_and_bounded_errors(self):
        self.assertIn("createPagedListController", self.source)
        self.assertIn("renderBooksCompact(payload", self.source)
        self.assertIn('loadErrorText: "Book search failed."', self.source)
        self.assertIn("bookSearchNext", self.source)
        self.assertIn("bookSearchPrev", self.source)

    def test_assigned_books_keep_page_and_step_back_after_last_removal(self):
        self.assertIn("initialUrl: groupBooksApiUrl(groupId)", self.source)
        self.assertIn("state.resultCount === 1 && state.previousUrl", self.source)
        self.assertIn('booksCtl.loadPrevious("remove-back")', self.source)
        self.assertIn("await booksCtl.reload()", self.source)
        self.assertIn('window.addEventListener("popstate"', self.source)

    def test_empty_picker_query_uses_broad_search_empty_result_contract(self):
        self.assertIn("q: term", self.source)
        self.assertNotIn('initialUrl: "/api/v1/library/books/"', self.source)
        self.assertNotIn('setBookSearchStatus("Enter a search term."', self.source)
        self.assertNotIn("if (!term)", self.source)

    def test_add_refreshes_assigned_and_excluded_search_results(self):
        add_success = self.source.split('setBookSearchStatus("Added."', 1)[1]
        self.assertIn("await booksCtl.reload()", add_success)
        self.assertIn("await bookSearchCtl.reload()", add_success)
