from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from library.groups.services import ensure_book_public_assignment
from library.models import Author, Series
from library.models import BookGroupAssignment

from tests.library.helpers import (
    create_librarian_user,
    create_reader_user,
)
from tests.library.utils import IsolatedMediaRootMixin, paginated_results
from tests.utils.books import create_file_backed_book

class AuthorSeriesVisibilityAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.reader = create_reader_user(username="reader", password="pw")
        self.client.login(username="reader", password="pw")

        from library.models import LibraryGroup, LibraryGroupMembership

        self.group_x = LibraryGroup.objects.create(name="X")
        LibraryGroupMembership.objects.create(
            user=self.reader, group=self.group_x, is_curator=False
        )
        self.group_y = LibraryGroup.objects.create(name="Y")

        self.author_public = Author.objects.create(name="Public Author")
        self.series_public = Series.objects.create(name="Public Series")
        self.book_public = create_file_backed_book(
            title="PB",
            assign_public=False,
            book_fields={"series": self.series_public},
        ).book
        self.book_public.authors.add(self.author_public)
        ensure_book_public_assignment(book=self.book_public, added_by=None)

        self.author_x = Author.objects.create(name="X Author")
        self.series_x = Series.objects.create(name="X Series")
        self.book_x = create_file_backed_book(
            title="XB",
            assign_public=False,
            book_fields={"series": self.series_x},
        ).book
        self.book_x.authors.add(self.author_x)
        BookGroupAssignment.objects.create(book=self.book_x, group=self.group_x)

        self.author_hidden = Author.objects.create(name="Hidden Author")
        self.series_hidden = Series.objects.create(name="Hidden Series")
        self.book_hidden = create_file_backed_book(
            title="HB",
            assign_public=False,
            book_fields={"series": self.series_hidden},
        ).book
        self.book_hidden.authors.add(self.author_hidden)
        BookGroupAssignment.objects.create(book=self.book_hidden, group=self.group_y)

    def test_reader_author_list_filtered(self):
        response = cast(Response, self.client.get("/api/v1/library/authors/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = sorted([a["name"] for a in paginated_results(response)])
        self.assertEqual(names, ["Public Author", "X Author"])

    def test_reader_author_retrieve_404_for_inaccessible_only(self):
        response = self.client.get(f"/api/v1/library/authors/{self.author_hidden.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_reader_series_list_filtered(self):
        response = cast(Response, self.client.get("/api/v1/library/series/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = sorted([s["name"] for s in paginated_results(response)])
        self.assertEqual(names, ["Public Series", "X Series"])

    def test_reader_series_retrieve_404_for_inaccessible_only(self):
        response = self.client.get(f"/api/v1/library/series/{self.series_hidden.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

class AuthorSeriesCreatePermissionsAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.reader = create_reader_user(username="reader2", password="pw")

        self.librarian = create_librarian_user(username="librarian2", password="pw")

    def test_reader_cannot_create_author_or_series(self):
        self.client.login(username="reader2", password="pw")
        r1 = cast(Response, self.client.post("/api/v1/library/authors/", data={"name": "Nope"}, format="json"))
        r2 = cast(Response, self.client.post("/api/v1/library/series/", data={"name": "Nope"}, format="json"))
        self.assertEqual(r1.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(r2.status_code, status.HTTP_403_FORBIDDEN)

    def test_librarian_can_create_author_and_series(self):
        self.client.login(username="librarian2", password="pw")
        r1 = cast(Response, self.client.post("/api/v1/library/authors/", data={"name": "New Author"}, format="json"))
        r2 = cast(Response, self.client.post("/api/v1/library/series/", data={"name": "New Series"}, format="json"))
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", cast(Mapping[str, Any], r1.data))
        self.assertIn("id", cast(Mapping[str, Any], r2.data))

    def test_book_patch_accepts_authors_and_series_ids(self):
        self.client.login(username="librarian2", password="pw")
        author = cast(dict[str, Any], cast(Response, self.client.post("/api/v1/library/authors/", data={"name": "A"}, format="json")).data)
        series = cast(dict[str, Any], cast(Response, self.client.post("/api/v1/library/series/", data={"name": "S"}, format="json")).data)

        book = create_file_backed_book(title="T", assign_public=False).book
        ensure_book_public_assignment(book=book, added_by=None)

        resp = cast(
            Response,
            self.client.patch(
                f"/api/v1/library/books/{book.id}/",
                data={"authors": [author["id"]], "series": series["id"], "series_index": 1},
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = cast(Mapping[str, Any], resp.data)
        self.assertEqual([a["id"] for a in payload["authors"]], [author["id"]])
        self.assertEqual(payload["series"]["id"], series["id"])
