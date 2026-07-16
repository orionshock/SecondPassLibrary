from __future__ import annotations

from tests.library.bearer.helpers import LibraryBearerApiTestCase


class LibraryBearerGroupReadTests(LibraryBearerApiTestCase):
    def test_lists_and_retrieves_only_visible_groups(self):
        listed = self.bearer_get("/api/v1/library/groups/")
        visible = self.bearer_get(f"/api/v1/library/groups/{self.public.id}/")
        hidden = self.bearer_get(f"/api/v1/library/groups/{self.hidden.id}/")

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(
            {row["id"] for row in listed.json()["results"]},
            {str(self.public.id)},
        )
        self.assertEqual(visible.status_code, 200)
        self.assertEqual(hidden.status_code, 404)

    def test_group_scoped_catalog_axes_are_bearer_readable(self):
        base = f"/api/v1/library/groups/{self.public.id}/"
        for axis in ["books", "authors", "series", "tags"]:
            with self.subTest(axis=axis):
                response = self.bearer_get(f"{base}{axis}/", {"page_size": 1})
                self.assertEqual(response.status_code, 200)
                self.assertGreater(response.json()["count"], 0)
                self.assertEqual(len(response.json()["results"]), 1)

    def test_inaccessible_group_axes_are_404(self):
        base = f"/api/v1/library/groups/{self.hidden.id}/"
        for axis in ["books", "authors", "series", "tags"]:
            with self.subTest(axis=axis):
                self.assertEqual(self.bearer_get(f"{base}{axis}/").status_code, 404)
