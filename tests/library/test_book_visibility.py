from __future__ import annotations

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from library.groups.services import ensure_book_public_assignment
from library.models import BookFile
from library.models import BookGroupAssignment

from tests.library.helpers import (
    create_librarian_user,
    create_manager_user,
    create_owner_user,
    create_reader_user,
)
from tests.library.utils import IsolatedMediaRootMixin, paginated_results
from tests.utils.books import (
    create_file_backed_book,
    create_fileless_book_for_integrity_edge_case,
)
from tests.utils.responses import assert_response


class LibraryVisibilityAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.reader = create_reader_user(username="reader", password="pw")
        self.librarian = create_librarian_user(username="librarian", password="pw")

        self.manager = create_manager_user(username="manager", password="pw")

        self.owner = create_owner_user(
            username="owner", password="pw", email="example@example.com"
        )

        from library.models import LibraryGroup, LibraryGroupMembership
        from library.groups.public_group import get_public_group

        self.public = get_public_group()
        self.group_a = LibraryGroup.objects.create(name="Group A")
        self.group_b = LibraryGroup.objects.create(name="Group B")

        LibraryGroupMembership.objects.create(
            user=self.reader, group=self.group_a, is_curator=False
        )

        self.public_book = create_file_backed_book(
            title="Public Book", assign_public=False
        ).book
        ensure_book_public_assignment(book=self.public_book, added_by=None)

        self.group_a_book = create_file_backed_book(
            title="Group A Book", assign_public=False
        ).book
        BookGroupAssignment.objects.create(book=self.group_a_book, group=self.group_a)

        # Intentionally fileless: this test sets up a BookFile row with a fixed checksum.
        self.group_b_book = create_fileless_book_for_integrity_edge_case(
            title="Group B Book", assign_public=False
        )
        BookGroupAssignment.objects.create(book=self.group_b_book, group=self.group_b)

        uploaded = SimpleUploadedFile(
            "b.epub", b"epub-bytes", content_type="application/epub+zip"
        )
        self.group_b_file = BookFile.objects.create(
            book=self.group_b_book,
            file=uploaded,
            checksum="c" * 64,
            file_size=9,
            source_filename="c.epub",
        )

    def test_reader_can_list_public_books(self):
        self.client.login(username="reader", password="pw")
        response = assert_response(self.client.get("/api/v1/library/books/?q=Public"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [b["title"] for b in paginated_results(response)]
        self.assertIn("Public Book", titles)

    def test_reader_can_list_books_in_group_they_belong_to(self):
        self.client.login(username="reader", password="pw")
        response = assert_response(self.client.get("/api/v1/library/books/?q=Group A"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [b["title"] for b in paginated_results(response)]
        self.assertIn("Group A Book", titles)

    def test_reader_cannot_list_books_in_group_they_do_not_belong_to(self):
        self.client.login(username="reader", password="pw")
        response = assert_response(self.client.get("/api/v1/library/books/?q=Group B"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [b["title"] for b in paginated_results(response)]
        self.assertNotIn("Group B Book", titles)

    def test_reader_cannot_retrieve_inaccessible_book(self):
        self.client.login(username="reader", password="pw")
        response = assert_response(
            self.client.get(f"/api/v1/library/books/{self.group_b_book.id}/")
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_reader_cannot_download_inaccessible_book_file(self):
        self.client.login(username="reader", password="pw")
        response = self.client.get(
            f"/api/v1/library/book-files/{self.group_b_file.id}/download/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_librarian_manager_owner_can_see_all_books(self):
        for username in ["librarian", "manager", "owner"]:
            self.client.logout()
            self.client.login(username=username, password="pw")
            response = assert_response(self.client.get("/api/v1/library/books/"))
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            titles = sorted([b["title"] for b in paginated_results(response)])
            self.assertEqual(titles, ["Group A Book", "Group B Book", "Public Book"])
