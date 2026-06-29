"""Tests for library book detail and edit pages."""
from uuid import uuid4

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

    def test_authenticated_book_detail_returns_200_and_has_container(self):
        self.client.force_login(self.user)
        book_id = uuid4()
        response = self.client.get(f"/library/books/{book_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="book-detail"')
        self.assertContains(response, f'data-book-id="{book_id}"')
        self.assertContains(response, 'id="book-groups"')
        self.assertContains(response, 'id="book-shelves"')
        self.assertContains(response, 'id="book-edit-link-wrap"')
        self.assertContains(response, 'id="book-download-link"')
        self.assertContains(response, 'id="book-summary-toggle"')
        self.assertContains(response, 'data-tab="shelves"')
        self.assertContains(response, 'data-tab="groups"')
        self.assertContains(response, 'data-tab="metadata"')
        self.assertContains(response, 'data-tab-panel="shelves"')
        self.assertContains(response, 'data-tab-panel="groups"')
        self.assertContains(response, 'data-tab-panel="metadata"')
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

    def test_authenticated_book_edit_returns_200_and_has_form_container(self):
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
        self.assertContains(response, 'data-tab="groups"')
        self.assertContains(response, 'data-tab="shelves"')
        self.assertContains(response, 'data-tab="idents"')
        self.assertContains(response, 'id="tab-metadata"')
        self.assertContains(response, 'id="tab-authors"')
        self.assertContains(response, 'id="tab-groups"')
        self.assertContains(response, 'id="tab-shelves"')
        self.assertContains(response, 'id="tab-idents"')
        self.assertContains(response, 'id="book-edit-form"')
        self.assertContains(response, 'id="book-edit-authors-selected"')
        self.assertContains(response, 'id="book-edit-author-add-select"')
        self.assertContains(response, 'id="book-edit-author-new-name"')
        self.assertContains(response, 'id="book-edit-series-select"')
        self.assertContains(response, 'id="book-edit-series-new-name"')
        self.assertContains(response, 'id="book-edit-series-index"')
        self.assertContains(response, 'step="0.1"')
        self.assertContains(response, 'id="book-edit-identifiers"')
        self.assertContains(response, 'id="book-edit-file-info"')
        self.assertContains(response, 'id="book-edit-groups"')
        self.assertContains(response, 'id="book-edit-groups-add"')
        self.assertContains(response, 'id="book-edit-shelves"')
        self.assertContains(response, 'id="book-edit-shelves-status"')
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
