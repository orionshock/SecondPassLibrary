from __future__ import annotations

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from library.groups.services import ensure_book_public_assignment
from library.models import Author, BookFile, Series
from library.models import BookIdentifier

from tests.library.helpers import (
    create_reader_user,
)
from tests.testenv.filesystem import IsolatedMediaRootMixin
from tests.utils.responses import paginated_results
from tests.utils.books import (
    create_file_backed_book,
    create_fileless_book_for_integrity_edge_case,
)
from tests.utils.responses import assert_response, payload_dict, response_data_dict


class BookListErgonomicsAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.user = create_reader_user(username="testuser", password="testpass")
        self.client.login(username="testuser", password="testpass")

        self.author = Author.objects.create(name="A Author")
        self.series = Series.objects.create(name="S Series")
        # Intentionally fileless: this test sets up a BookFile row with a fixed checksum.
        self.book = create_fileless_book_for_integrity_edge_case(
            title="T",
            assign_public=False,
            book_fields={"series": self.series, "series_index": 1},
        )
        self.book.authors.add(self.author)
        ensure_book_public_assignment(book=self.book, added_by=None)
        BookIdentifier.objects.create(
            book=self.book,
            scheme=BookIdentifier.SCHEME_ISBN_13,
            value="9780123456472",
            source="epub",
            is_primary=True,
        )
        uploaded = SimpleUploadedFile(
            "ignored.epub",
            b"epub-bytes",
            content_type="application/epub+zip",
        )
        BookFile.objects.create(
            book=self.book,
            file=uploaded,
            checksum="a" * 64,
            file_size=9,
            source_filename="SOURCE_NAME.epub",
        )

    def test_book_list_includes_nested_summaries_and_no_raw_file_paths(self):
        response = assert_response(self.client.get("/api/v1/library/books/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = paginated_results(response)
        self.assertEqual(len(data), 1)
        book = data[0]

        self.assertIsInstance(book["authors"], list)
        self.assertEqual(book["authors"][0]["id"], str(self.author.id))
        self.assertEqual(book["authors"][0]["name"], "A Author")

        self.assertIsInstance(book["series"], dict)
        self.assertEqual(book["series"]["id"], str(self.series.id))
        self.assertEqual(book["series"]["name"], "S Series")

        self.assertIsInstance(book["identifiers"], list)
        self.assertEqual(book["identifiers"][0]["scheme"], "isbn_13")
        self.assertEqual(book["identifiers"][0]["source"], "epub")

        self.assertIn("file", book)
        self.assertIsInstance(book["file"], dict)
        file0 = payload_dict(book, "file")
        self.assertIn("download_url", file0)
        self.assertNotIn("file", file0)
        self.assertNotIn("books/", str(file0))
        self.assertNotIn("files", book)


class BookCoverUrlAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.user = create_reader_user(username="testuser", password="testpass")
        self.client.login(username="testuser", password="testpass")

    def test_cover_url_null_when_no_cover(self):
        book = create_file_backed_book(title="No Cover", assign_public=False).book
        ensure_book_public_assignment(book=book, added_by=None)

        r = assert_response(self.client.get(f"/api/v1/library/books/{book.id}/"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        payload = response_data_dict(r)
        self.assertIn("cover_url", payload)
        self.assertEqual(payload["cover_url"], None)

    def test_cover_url_present_when_cover_exists(self):
        from io import BytesIO
        from PIL import Image
        from library.cover_services import set_book_cover_from_bytes

        book = create_file_backed_book(title="Has Cover", assign_public=False).book
        ensure_book_public_assignment(book=book, added_by=None)

        img = Image.new("RGB", (10, 12), color=(9, 9, 9))
        bio = BytesIO()
        img.save(bio, format="PNG")
        set_book_cover_from_bytes(book=book, data=bio.getvalue(), source="manual")

        r_list = assert_response(self.client.get("/api/v1/library/books/"))
        self.assertEqual(r_list.status_code, status.HTTP_200_OK)
        books = paginated_results(r_list)
        self.assertEqual(len(books), 1)
        self.assertIsInstance(books[0]["cover_url"], str)
        self.assertTrue(str(books[0]["cover_url"]).startswith("http://testserver/"))

        r_detail = assert_response(self.client.get(f"/api/v1/library/books/{book.id}/"))
        self.assertEqual(r_detail.status_code, status.HTTP_200_OK)
        detail = response_data_dict(r_detail)
        self.assertIsInstance(detail["cover_url"], str)
        self.assertTrue(str(detail["cover_url"]).startswith("http://testserver/"))
