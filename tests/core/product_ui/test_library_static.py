"""Tests for library book detail and edit pages."""
from pathlib import Path
from uuid import uuid4

from core import server_settings
from tests.core.product_ui.helpers import ProductUiTestCase


class ProductUiLibraryTests(ProductUiTestCase):
    """Test library and book detail/edit pages."""

    def test_unauthenticated_book_detail_redirects_to_login(self):
        book_id = uuid4()
        response = self.client.get(f"/library/books/{book_id}/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"], f"/api-auth/login/?next=/library/books/{book_id}/"
        )

    def test_unauthenticated_book_edit_redirects_to_login(self):
        book_id = uuid4()
        response = self.client.get(f"/library/books/{book_id}/edit/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            f"/api-auth/login/?next=/library/books/{book_id}/edit/",
        )

    def test_authenticated_book_detail_returns_200_and_hides_group_panel_by_default(self):
        self.client.force_login(self.user)
        book_id = uuid4()
        response = self.client.get(f"/library/books/{book_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="book-detail"')
        self.assertContains(response, f'data-book-id="{book_id}"')
        self.assertContains(response, 'id="book-shelves"')
        self.assertContains(response, 'id="book-edit-link-wrap"')
        self.assertContains(response, 'id="book-download-link"')
        self.assertContains(response, 'id="book-summary-toggle"')
        self.assertContains(response, 'data-tab="shelves"')
        self.assertContains(response, 'data-tab="metadata"')
        self.assertContains(response, 'data-tab-panel="shelves"')
        self.assertContains(response, 'data-tab-panel="metadata"')
        self.assertNotContains(response, 'id="book-groups"')
        self.assertNotContains(response, 'data-tab="groups"')
        self.assertNotContains(response, 'data-tab-panel="groups"')
        self.assertContains(response, 'id="tab-metadata"')
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(
            response, '<a class="breadcrumbs__link" href="/library/">Library</a>', html=False
        )
        self.assertContains(
            response, '<a class="breadcrumbs__link" href="/library/?view=books">Books</a>', html=False
        )
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, "Book")
        self.assertNotContains(response, "Back to Library")
        self.assertContains(
            response, f'href="/library/books/{book_id}/edit/"'
        )

    def test_authenticated_book_detail_shows_group_panel_when_enabled(self):
        server_settings.enable_advanced_library_groups()
        self.client.force_login(self.user)
        book_id = uuid4()
        response = self.client.get(f"/library/books/{book_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="book-groups"')
        self.assertContains(response, 'data-tab="groups"')
        self.assertContains(response, 'data-tab-panel="groups"')

    def test_authenticated_book_detail_malformed_id_returns_404(self):
        self.client.force_login(self.user)

        response = self.client.get("/library/books/not-a-uuid/", follow=False)

        self.assertEqual(response.status_code, 404)

    def test_authenticated_book_edit_returns_200_and_hides_group_controls_by_default(self):
        self.client.force_login(self.user)
        book_id = uuid4()
        response = self.client.get(f"/library/books/{book_id}/edit/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="book-edit-header"')
        self.assertContains(response, 'id="book-edit"')
        self.assertContains(response, f'data-book-id="{book_id}"')
        self.assertContains(response, 'data-tab="metadata"')
        self.assertContains(response, 'data-tab="authors"')
        self.assertContains(response, 'data-tab="shelves"')
        self.assertContains(response, 'data-tab="idents"')
        self.assertContains(response, 'id="tab-metadata"')
        self.assertContains(response, 'id="tab-authors"')
        self.assertContains(response, 'id="tab-shelves"')
        self.assertContains(response, 'id="tab-idents"')
        self.assertContains(response, 'id="book-edit-form"')
        self.assertContains(response, 'id="book-edit-authors-selected"')
        self.assertContains(response, 'id="book-edit-author-add-select"')
        self.assertContains(response, 'id="book-edit-series-select"')
        self.assertContains(response, 'id="book-edit-series-new"')
        self.assertContains(response, 'id="book-edit-series-index"')
        self.assertContains(response, 'id="book-edit-catalog-tags"')
        self.assertContains(response, 'id="book-edit-catalog-tag-input"')
        self.assertContains(response, 'id="book-edit-catalog-tag-options"')
        self.assertContains(response, 'id="book-edit-catalog-tag-add"')
        self.assertContains(response, 'step="0.1"')
        self.assertContains(response, 'id="book-edit-identifiers"')
        self.assertContains(response, 'id="book-edit-file-info"')
        self.assertContains(response, 'id="book-edit-shelves"')
        self.assertContains(response, 'id="book-edit-shelves-status"')
        self.assertNotContains(response, 'data-tab="groups"')
        self.assertNotContains(response, 'id="tab-groups"')
        self.assertNotContains(response, 'id="book-edit-groups"')
        self.assertNotContains(response, 'id="book-edit-groups-add"')
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(
            response, '<a class="breadcrumbs__link" href="/library/">Library</a>', html=False
        )
        self.assertContains(
            response, '<a class="breadcrumbs__link" href="/library/?view=books">Books</a>', html=False
        )
        self.assertContains(
            response,
            f'<a class="breadcrumbs__link" href="/library/books/{book_id}/">Book</a>',
            html=False,
        )
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, "Edit")
        self.assertNotContains(response, "Back to Book")

    def test_authenticated_book_edit_shows_group_controls_when_enabled(self):
        server_settings.enable_advanced_library_groups()
        self.client.force_login(self.user)
        book_id = uuid4()
        response = self.client.get(f"/library/books/{book_id}/edit/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-tab="groups"')
        self.assertContains(response, 'id="tab-groups"')
        self.assertContains(response, 'id="book-edit-groups"')
        self.assertContains(response, 'id="book-edit-groups-add"')

    def test_book_edit_uses_current_metadata_file_and_identifier_contracts(self):
        template = Path("web/templates/web/library/book_edit.html").read_text(encoding="utf-8")
        main_js = Path("web/static/web/js/book_edit/main.js").read_text(encoding="utf-8")
        metadata_js = Path("web/static/web/js/book_edit/metadata.js").read_text(encoding="utf-8")
        catalog_tags_js = Path("web/static/web/js/book_edit/catalog_tags.js").read_text(
            encoding="utf-8"
        )
        identifiers_js = Path("web/static/web/js/book_edit/identifiers_actions.js").read_text(
            encoding="utf-8"
        )
        file_js = Path("web/static/web/js/book_edit/identifiers_file.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('id="book-edit-description"', template)
        self.assertNotIn('id="book-edit-summary"', template)
        self.assertNotIn('id="book-edit-subjects"', template)
        self.assertNotIn('id="book-edit-isbn"', template)
        self.assertNotIn("Book.isbn", template)
        self.assertIn("book.description", metadata_js)
        self.assertIn("description: normalizeOptionalString", metadata_js)
        self.assertIn('precision === "month"', metadata_js)
        self.assertIn("book.series.series_index", metadata_js)
        self.assertIn("book.series.series_index", file_js)
        self.assertIn('addRow("Checksum", file.checksum', file_js)
        self.assertIn('addRow("Source filename", file.source_filename', file_js)
        self.assertIn("rootEl.dataset.bookId", main_js)
        self.assertNotIn("/identifiers/", identifiers_js)
        self.assertNotIn("fetchJSON", identifiers_js)
        self.assertIn("state.identifiers", identifiers_js)
        self.assertNotIn("data-ident-add-field", identifiers_js)
        self.assertIn("identifiers: state.identifiers", main_js)
        self.assertIn("identifiers: identifiers.map", metadata_js)
        self.assertIn("catalog_tags: catalogTags.map", metadata_js)
        self.assertIn("state.catalogTags", main_js)
        self.assertIn("bindCatalogTagActions", main_js)
        self.assertNotIn("fetchJSONWithOptions", catalog_tags_js)
        self.assertIn("data-remove-catalog-tag", catalog_tags_js)
        self.assertIn('? { name: (dom.seriesNewEl.value || "").trim() }', metadata_js)

    def test_book_detail_uses_current_metadata_contract(self):
        template = Path("web/templates/web/library/book_detail.html").read_text(encoding="utf-8")
        detail_js = Path("web/static/web/js/library/detail.js").read_text(encoding="utf-8")

        self.assertIn('id="book-metadata-body"', template)
        self.assertIn('id="book-catalog-tags-body"', template)
        self.assertIn("book.description", detail_js)
        self.assertIn("book.publisher", detail_js)
        self.assertIn("book.language", detail_js)
        self.assertIn("book.published_date_precision", detail_js)
        self.assertIn("book.identifiers", detail_js)
        self.assertIn("book.catalog_tags", detail_js)
        self.assertIn("book.file", detail_js)
        self.assertIn("book.series.series_index", detail_js)
        self.assertNotIn("book.summary", detail_js)
        self.assertNotIn("book.subjects", detail_js)
        self.assertNotIn("book.series_index", detail_js)
        self.assertNotIn("book.files", detail_js)
        self.assertNotIn("i.is_primary", detail_js)

    def test_authenticated_book_edit_malformed_id_returns_404(self):
        self.client.force_login(self.user)

        response = self.client.get("/library/books/not-a-uuid/edit/", follow=False)

        self.assertEqual(response.status_code, 404)
