from __future__ import annotations

from django.test import TestCase

from tests.library.helpers import LibraryCatalogApiFixtureMixin


class LibraryTagAxisTests(LibraryCatalogApiFixtureMixin, TestCase):
    def test_detail_visible_succeeds(self):
        response = self.client.get(f"/api/v1/library/tags/{self.fantasy.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"id", "name", "slug", "book_count"})
        self.assertEqual(response.json()["name"], "Fantasy")
        self.assertEqual(response.json()["slug"], "fantasy")
        self.assertEqual(response.json()["book_count"], 2)

    def test_detail_rejects_patch_for_librarian_plus(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/tags/{self.fantasy.id}/",
            data={"name": "Renamed"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 405)
        self.fantasy.refresh_from_db()
        self.assertEqual(self.fantasy.name, "Fantasy")

    def test_list_and_detail_ignore_preview_only_params(self):
        urls = (
            "/api/v1/library/tags/",
            f"/api/v1/library/tags/{self.fantasy.id}/",
        )

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(
                    url,
                    {
                        "include_preview_books": "true",
                        "preview_limit": "invalid",
                    },
                )
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                rows = payload["results"] if "results" in payload else [payload]
                self.assertTrue(rows)
                self.assertTrue(all("preview_books" not in row for row in rows))
