from __future__ import annotations

from django.contrib.auth import get_user_model

from accounts.models import UserProfile
from library.models import Book
from tests.core.product_ui.helpers import ProductUiTestCase
from tests.utils.users import set_user_role


class BookCoverProductUiRouteTests(ProductUiTestCase):
    def setUp(self):
        super().setUp()
        self.book = Book.objects.create(title="Cover UI")

    def test_reader_does_not_receive_cover_editor(self):
        self.client.force_login(self.user)

        response = self.client.get(f"/library/books/{self.book.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="book-cover-edit"')
        self.assertNotContains(response, 'id="book-cover-modal"')

    def test_librarian_manager_and_owner_receive_cover_editor(self):
        User = get_user_model()
        librarian = User.objects.create_user(username="cover-librarian", password="pw")
        manager = User.objects.create_user(username="cover-manager", password="pw")
        set_user_role(librarian, UserProfile.ROLE_LIBRARIAN)
        set_user_role(manager, UserProfile.ROLE_MANAGER)

        for user in (librarian, manager, self.bootstrap_owner):
            with self.subTest(username=user.username):
                self.client.force_login(user)
                response = self.client.get(f"/library/books/{self.book.id}/")
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="book-cover-edit"')
                self.assertContains(response, 'id="book-cover-modal"')
