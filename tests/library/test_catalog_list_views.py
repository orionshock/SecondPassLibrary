from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any, cast

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from library.groups.services import ensure_book_public_assignment
from library.models import Author, BookFile, Series
from library.models import BookIdentifier

from tests.library.helpers import (
    create_reader_user,
)
from tests.library.utils import IsolatedMediaRootMixin, paginated_results
from tests.utils.books import create_file_backed_book, create_fileless_book_for_integrity_edge_case

class BookBrowseFiltersAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.user = create_reader_user(username="testuser", password="testpass")
        self.client.login(username="testuser", password="testpass")

        self.author_a = Author.objects.create(name="Alice Author")
        self.author_b = Author.objects.create(name="Bob Writer")
        self.series_s = Series.objects.create(name="Saga Series")

        # Intentionally fileless: this test suite exercises has_files filtering.
        self.book1 = create_fileless_book_for_integrity_edge_case(
            title="Alpha",
            assign_public=False,
            book_fields={"language": "en", "series": self.series_s},
        )
        self.book1.authors.add(self.author_a)
        ensure_book_public_assignment(book=self.book1, added_by=None)
        BookIdentifier.objects.create(book=self.book1, scheme="other", value="ID-XYZ", source="epub")

        # Intentionally fileless: this test sets up a BookFile row with a fixed checksum.
        self.book2 = create_fileless_book_for_integrity_edge_case(
            title="Beta",
            assign_public=False,
            book_fields={"language": "fr"},
        )
        self.book2.authors.add(self.author_b)
        ensure_book_public_assignment(book=self.book2, added_by=None)

        uploaded = SimpleUploadedFile("ignored.epub", b"epub-bytes", content_type="application/epub+zip")
        BookFile.objects.create(
            book=self.book2,
            file=uploaded,
            checksum="b" * 64,
            file_size=9,
            source_filename="b.epub",
        )

    def _titles(self, response: Response):
        data = paginated_results(response)
        return sorted([b["title"] for b in data])

    def _titles_in_order(self, response: Response):
        data = paginated_results(response)
        return [b["title"] for b in data]

    def test_q_matches_title(self):
        response = cast(Response, self.client.get("/api/v1/library/books/?q=Alp"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._titles(response), ["Alpha"])

    def test_q_matches_author(self):
        response = cast(Response, self.client.get("/api/v1/library/books/?q=bob"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._titles(response), ["Beta"])

    def test_q_matches_identifier_value(self):
        response = cast(Response, self.client.get("/api/v1/library/books/?q=xyz"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._titles(response), ["Alpha"])

    def test_filter_by_author(self):
        response = cast(
            Response,
            self.client.get(f"/api/v1/library/books/?author={self.author_a.id}"),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._titles(response), ["Alpha"])

    def test_filter_by_series(self):
        response = cast(
            Response,
            self.client.get(f"/api/v1/library/books/?series={self.series_s.id}"),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._titles(response), ["Alpha"])

    def test_ordering_series_index_on_series_filtered_list(self):
        self.book1.series_index = Decimal("0")
        self.book1.save(update_fields=["series_index", "updated_at"])

        b2 = create_file_backed_book(
            title="Gamma",
            assign_public=False,
            book_fields={"series": self.series_s, "series_index": 2},
        ).book
        ensure_book_public_assignment(book=b2, added_by=None)
        b0 = create_file_backed_book(
            title="Zero",
            assign_public=False,
            book_fields={"series": self.series_s, "series_index": 1},
        ).book
        ensure_book_public_assignment(book=b0, added_by=None)

        response = cast(
            Response,
            self.client.get(
                f"/api/v1/library/books/?series={self.series_s.id}&ordering=series_index"
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._titles_in_order(response), ["Alpha", "Zero", "Gamma"])

    def test_filter_by_language(self):
        response = cast(Response, self.client.get("/api/v1/library/books/?language=en"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._titles(response), ["Alpha"])

    def test_filter_has_files_true(self):
        response = cast(Response, self.client.get("/api/v1/library/books/?has_files=true"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._titles(response), ["Beta"])
        data = paginated_results(response)
        file0 = data[0]["file"]
        self.assertIsNotNone(file0)
        self.assertIn("download_url", file0)
        self.assertNotIn("file", file0)
        self.assertNotIn("books/", str(file0))

class PaginationBasicsAPITest(APITestCase):
    def setUp(self):
        self.user = create_reader_user(username="reader", password="pw")
        self.client.login(username="reader", password="pw")

        for i in range(51):
            book = create_file_backed_book(title=f"Book {i:03d}", assign_public=False).book
            ensure_book_public_assignment(book=book, added_by=None)

    def test_books_list_is_paginated_with_standard_shape(self):
        response = cast(Response, self.client.get("/api/v1/library/books/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data)
        payload = cast(Mapping[str, Any], response.data)
        self.assertIn("count", payload)
        self.assertIn("next", payload)
        self.assertIn("previous", payload)
        self.assertIn("results", payload)

    def test_default_page_size_applies(self):
        response = cast(Response, self.client.get("/api/v1/library/books/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = cast(Mapping[str, Any], response.data)
        self.assertEqual(payload["count"], 51)
        results = cast(list[Any], payload["results"])
        self.assertEqual(len(results), 50)

    def test_page_size_param_and_max_cap(self):
        r10 = cast(Response, self.client.get("/api/v1/library/books/?page_size=10"))
        self.assertEqual(r10.status_code, status.HTTP_200_OK)
        p10 = cast(Mapping[str, Any], r10.data)
        self.assertEqual(len(cast(list[Any], p10["results"])), 10)

        for i in range(51, 256):
            book = create_file_backed_book(title=f"Book {i:03d}", assign_public=False).book
            ensure_book_public_assignment(book=book, added_by=None)

        rmax = cast(Response, self.client.get("/api/v1/library/books/?page_size=9999"))
        self.assertEqual(rmax.status_code, status.HTTP_200_OK)
        pmax = cast(Mapping[str, Any], rmax.data)
        self.assertEqual(pmax["count"], 256)
        self.assertEqual(len(cast(list[Any], pmax["results"])), 200)
