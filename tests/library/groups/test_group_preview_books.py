from django.contrib.auth import get_user_model
from django.test import TestCase

from library.cover_services import set_book_cover_from_bytes
from library.groups.memberships import add_user_to_group
from library.groups.book_assignments import add_book_to_group
from library.models import LibraryGroup
from tests.testenv.filesystem import IsolatedMediaRootMixin
from tests.utils.books import create_file_backed_book


class LibraryGroupPreviewBooksTests(IsolatedMediaRootMixin, TestCase):
    def setUp(self):
        self.reader = get_user_model().objects.create_user(
            username="reader",
            password="pw",
        )
        self.visible_group = LibraryGroup.objects.create(name="Visible")
        self.hidden_group = LibraryGroup.objects.create(name="Hidden")
        add_user_to_group(user=self.reader, group=self.visible_group)

        self.visible_book = create_file_backed_book(
            title="Visible Book",
            assign_public=False,
        ).book
        set_book_cover_from_bytes(book=self.visible_book, data=b"cover")
        add_book_to_group(book=self.visible_book, group=self.visible_group)

        hidden_book = create_file_backed_book(
            title="Hidden Book",
            assign_public=False,
        ).book
        add_book_to_group(book=hidden_book, group=self.hidden_group)
        self.client.force_login(self.reader)

    def test_group_previews_are_opt_in_and_use_visible_book_contract(self):
        default_response = self.client.get("/api/v1/library/groups/")
        default_row = default_response.json()["results"][0]
        self.assertNotIn("preview_books", default_row)

        response = self.client.get(
            "/api/v1/library/groups/",
            {"include_preview_books": "true"},
        )

        self.assertEqual(response.status_code, 200)
        rows = response.json()["results"]
        self.assertEqual([row["name"] for row in rows], ["Visible"])
        self.assertEqual(
            rows[0]["preview_books"],
            [
                {
                    "id": str(self.visible_book.id),
                    "title": "Visible Book",
                    "cover_url": (
                        f"http://testserver{self.visible_book.cover_file.url}"
                    ),
                }
            ],
        )
