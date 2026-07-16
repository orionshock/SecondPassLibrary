from __future__ import annotations

from library.models import Book
from tests.core.product_ui.helpers import ProductUiTestCase


class BookCoverProductUiRouteTests(ProductUiTestCase):
    def setUp(self):
        super().setUp()
        self.book = Book.objects.create(title="Cover UI")

    def test_book_detail_and_edit_controls_start_hidden(self):
        self.client.force_login(self.user)

        detail = self.client.get(f"/library/books/{self.book.id}/")
        edit = self.client.get(f"/library/books/{self.book.id}/edit/")

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(edit.status_code, 200)
        self.assertNotContains(detail, 'id="book-cover-edit"')
        self.assertNotContains(detail, 'id="book-cover-modal"')
        self.assertContains(detail, 'id="book-edit-link-wrap" class="is-hidden"')
        self.assertContains(
            edit,
            'id="book-edit-cover-editor" class="book-cover-editor is-hidden"',
        )
