from __future__ import annotations

from tests.library.bearer.helpers import LibraryBearerApiTestCase


class LibraryBearerCatalogMutationBoundaryTests(LibraryBearerApiTestCase):
    def setUp(self):
        super().setUp()
        self.use_manager_bearer()

    def test_privileged_bearer_cannot_patch_or_put_book_metadata_or_tags(self):
        url = f"/api/v1/library/books/{self.visible_one.id}/"
        headers = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

        patched = self.bearer.patch(
            url,
            {"title": "Bearer changed", "catalog_tags": []},
            format="json",
            **headers,
        )
        replaced = self.bearer.put(url, {"title": "Bearer replaced"}, format="json", **headers)

        self.assertEqual(patched.status_code, 403)
        self.assertEqual(replaced.status_code, 403)
        self.visible_one.refresh_from_db()
        self.assertEqual(self.visible_one.title, "Visible One")
        self.assertTrue(self.visible_one.book_catalog_tags.filter(catalog_tag=self.fantasy).exists())

    def test_unimplemented_book_and_tag_mutations_remain_unavailable(self):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

        created = self.bearer.post(
            "/api/v1/library/books/", {"title": "Not created"}, format="json", **headers
        )
        deleted = self.bearer.delete(
            f"/api/v1/library/books/{self.visible_one.id}/", **headers
        )
        tag_patch = self.bearer.patch(
            f"/api/v1/library/tags/{self.fantasy.id}/",
            {"name": "Not changed"},
            format="json",
            **headers,
        )

        self.assertEqual(created.status_code, 405)
        self.assertEqual(deleted.status_code, 405)
        self.assertEqual(tag_patch.status_code, 405)

    def test_privileged_bearer_cannot_patch_author_or_series(self):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}
        cases = [
            (f"/api/v1/library/authors/{self.alpha.id}/", self.alpha, "Alpha Author"),
            (f"/api/v1/library/series/{self.first_series.id}/", self.first_series, "First Series"),
        ]

        for url, instance, original_name in cases:
            with self.subTest(url=url):
                response = self.bearer.patch(url, {"name": "Bearer changed"}, format="json", **headers)
                self.assertEqual(response.status_code, 403)
                instance.refresh_from_db()
                self.assertEqual(instance.name, original_name)

    def test_privileged_bearer_cannot_create_author(self):
        response = self.bearer.post(
            "/api/v1/library/authors/",
            {"name": "Bearer Writer"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 403)

    def test_privileged_bearer_cannot_create_or_delete_series(self):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}
        created = self.bearer.post(
            "/api/v1/library/series/", {"name": "Bearer Series"}, format="json", **headers
        )
        deleted = self.bearer.delete(
            f"/api/v1/library/series/{self.first_series.id}/", **headers
        )

        self.assertEqual(created.status_code, 403)
        self.assertEqual(deleted.status_code, 403)

    def test_cover_and_import_mutations_remain_session_only(self):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}
        cover_url = f"/api/v1/library/books/{self.visible_one.id}/cover/"

        self.assertEqual(self.bearer.post(cover_url, {}, format="multipart", **headers).status_code, 403)
        self.assertEqual(self.bearer.delete(cover_url, **headers).status_code, 403)
        self.assertEqual(self.bearer.post("/api/v1/library/imports/", {}, format="multipart", **headers).status_code, 403)
