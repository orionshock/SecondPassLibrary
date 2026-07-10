from __future__ import annotations

from tests.library.groups.book_assignment_helpers import LibraryGroupBookAssignmentApiTestCase


class LibraryReWrite2607GroupBookAssignmentReadRegressionTests(
    LibraryGroupBookAssignmentApiTestCase
):
    def test_group_books_get_still_returns_group_scoped_books(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))

        response = self.client.get(self.group_books_url())

        self.assertEqual(response.status_code, 200)
        titles = [row["title"] for row in response.json()["results"]]
        self.assertEqual(titles, ["Club Book"])
