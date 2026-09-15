from django.contrib.auth import get_user_model
from django.test import TestCase

from core.server_settings import set_advanced_library_groups_enabled
from library.groups.memberships import add_user_to_group
from library.groups.book_assignments import add_book_to_group
from library.models import Book, LibraryGroup
from library.queries import invalidate_visible_books_cache
from tests.testenv.filesystem import IsolatedMediaRootMixin
from tests.utils.books import attach_test_cover, create_file_backed_book


class LibraryGroupPreviewBooksTests(IsolatedMediaRootMixin, TestCase):
    def setUp(self):
        set_advanced_library_groups_enabled(True)
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
        attach_test_cover(book=self.visible_book)
        add_book_to_group(book=self.visible_book, group=self.visible_group)

        hidden_book = create_file_backed_book(
            title="Hidden Book",
            assign_public=False,
        ).book
        add_book_to_group(book=hidden_book, group=self.hidden_group)
        invalidate_visible_books_cache()
        self.client.force_login(self.reader)

    def _add_preview_books(self, count=25):
        for index in range(count):
            book = Book.objects.create(title=f"Preview {index:02d}")
            add_book_to_group(book=book, group=self.visible_group)

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

    def test_group_preview_limit_contract_applies_to_list_and_detail(self):
        self._add_preview_books()
        list_url = "/api/v1/library/groups/"
        detail_url = f"/api/v1/library/groups/{self.visible_group.id}/"

        default = self.client.get(list_url, {"include_preview_books": "true"})
        self.assertEqual(default.status_code, 200)
        self.assertEqual(len(default.json()["results"][0]["preview_books"]), 6)

        for limit in (1, 6, 12, 24):
            with self.subTest(limit=limit):
                response = self.client.get(list_url, {"preview_limit": str(limit)})
                self.assertEqual(response.status_code, 200)
                row = response.json()["results"][0]
                self.assertEqual(len(row["preview_books"]), limit)
                self.assertEqual(
                    [book["title"] for book in row["preview_books"]],
                    sorted(book["title"] for book in row["preview_books"]),
                )

        detail = self.client.get(detail_url, {"preview_limit": "12"})
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.json()["preview_books"]), 12)

        for url in (list_url, detail_url):
            with self.subTest(url=url):
                disabled = self.client.get(url, {"preview_limit": "0"})
                self.assertEqual(disabled.status_code, 200)
                payload = disabled.json()
                row = payload["results"][0] if "results" in payload else payload
                self.assertNotIn("preview_books", row)

    def test_group_preview_limit_rejects_invalid_queries(self):
        url = "/api/v1/library/groups/"
        for value in ("-1", "invalid", "25", "01", "+1"):
            with self.subTest(value=value):
                response = self.client.get(url, {"preview_limit": value})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(set(response.json()), {"preview_limit"})

        repeated = self.client.get(f"{url}?preview_limit=1&preview_limit=2")
        contradictory = self.client.get(
            url,
            {"include_preview_books": "false", "preview_limit": "1"},
        )
        self.assertEqual(repeated.status_code, 400)
        self.assertEqual(set(repeated.json()), {"preview_limit"})
        self.assertEqual(contradictory.status_code, 400)
        self.assertEqual(set(contradictory.json()), {"preview_limit"})

    def test_group_preview_limit_does_not_change_parent_pagination(self):
        second_group = LibraryGroup.objects.create(name="Visible Two")
        add_user_to_group(user=self.reader, group=second_group)

        response = self.client.get(
            "/api/v1/library/groups/",
            {"preview_limit": "1", "page_size": "1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)
        self.assertEqual(len(response.json()["results"]), 1)
