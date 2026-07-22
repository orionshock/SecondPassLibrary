from __future__ import annotations

from library.models import Book, BookIdentifier
from tests.library.imports.helpers import metadata_xml, minimal_epub_bytes, zip_bytes
from tests.library.imports.upload_api_helpers import (
    LibraryImportUploadApiTestCase,
    upload_file,
)
from tests.testenv.filesystem import IsolatedMediaRootMixin


class LibraryImportUploadResultTests(
    IsolatedMediaRootMixin,
    LibraryImportUploadApiTestCase,
):
    def test_epub_upload_returns_imported_result(self):
        self.login_librarian()

        response = self.client.post(
            self.url,
            {"file": upload_file("sample.epub", minimal_epub_bytes())},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source_type"], "epub")
        self.assertEqual(payload["counts"]["imported"], 1)
        self.assertEqual(payload["items"][0]["status"], "imported")
        self.assertEqual(payload["items"][0]["source_label"], "sample.epub")
        self.assertTrue(payload["items"][0]["book_id"])
        self.assertEqual(payload["items"][0]["title"], "Sample EPUB")
        self.assertEqual(payload["items"][0]["authors"], ["Sample Author"])
        self.assertNotIn("series", payload["items"][0])
        self.assertNotIn("series_index", payload["items"][0])

    def test_imported_result_includes_ordered_authors_and_series(self):
        self.login_librarian()
        epub = minimal_epub_bytes(metadata_xml="""
            <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
              <dc:title>The Butlerian Jihad</dc:title>
              <dc:creator>Brian Herbert</dc:creator>
              <dc:creator>Kevin J. Anderson</dc:creator>
              <dc:language>en</dc:language>
              <meta name="calibre:series" content="Legends of Dune"/>
              <meta name="calibre:series_index" content="1"/>
            </metadata>
        """)

        response = self.client.post(self.url, {"file": upload_file("book.epub", epub)})

        self.assertEqual(response.status_code, 200)
        item = response.json()["items"][0]
        self.assertEqual(item["title"], "The Butlerian Jihad")
        self.assertEqual(item["authors"], ["Brian Herbert", "Kevin J. Anderson"])
        self.assertEqual(item["series"], "Legends of Dune")
        self.assertEqual(item["series_index"], "1.00")

    def test_zip_upload_returns_batch_result(self):
        self.login_librarian()

        response = self.client.post(
            self.url,
            {
                "file": upload_file(
                    "books.zip",
                    zip_bytes(("sample.epub", minimal_epub_bytes())).getvalue(),
                )
            },
        )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["source_type"], "zip")
        self.assertEqual(payload["counts"]["imported"], 1)
        self.assertEqual(payload["items"][0]["source_label"], "sample.epub")

    def test_empty_epub_upload_returns_failed_item(self):
        self.login_librarian()

        response = self.client.post(
            self.url,
            {"file": upload_file("empty.epub", b"")},
        )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["counts"]["failed"], 1)
        self.assertEqual(payload["items"][0]["status"], "failed")
        self.assertNotIn("book_id", payload["items"][0])

    def test_duplicate_epub_returns_duplicate_item(self):
        self.login_librarian()
        data = minimal_epub_bytes()
        self.client.post(self.url, {"file": upload_file("first.epub", data)})

        response = self.client.post(self.url, {"file": upload_file("second.epub", data)})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["counts"]["duplicate"], 1)
        self.assertEqual(payload["items"][0]["status"], "duplicate")
        self.assertEqual(payload["items"][0]["title"], "Sample EPUB")
        self.assertEqual(payload["items"][0]["authors"], ["Sample Author"])

    def test_zip_partial_failure_returns_item_level_failure(self):
        self.login_librarian()

        response = self.client.post(
            self.url,
            {
                "file": upload_file(
                    "mixed.zip",
                    zip_bytes(
                        ("bad.epub", b"not an epub"),
                        ("good.epub", minimal_epub_bytes(metadata_xml=metadata_xml("Good"))),
                    ).getvalue(),
                )
            },
        )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["counts"]["failed"], 1)
        self.assertEqual(payload["counts"]["imported"], 1)
        self.assertEqual([item["status"] for item in payload["items"]], ["failed", "imported"])
        self.assertNotIn("book_id", payload["items"][0])
        self.assertNotIn("title", payload["items"][0])
        self.assertNotIn("authors", payload["items"][0])
        self.assertTrue(payload["items"][1]["book_id"])

    def test_identifier_conflict_returns_conflict_item(self):
        self.login_librarian()
        existing_book = Book.objects.create(title="Existing", checksum="existing")
        BookIdentifier.objects.create(
            book=existing_book,
            scheme=BookIdentifier.SCHEME_ISBN_13,
            value="9780000000011",
            normalized_value="9780000000011",
        )
        epub = minimal_epub_bytes(
            metadata_xml="""
            <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"
                      xmlns:opf="http://www.idpf.org/2007/opf">
              <dc:title>Conflict</dc:title>
              <dc:identifier opf:scheme="ISBN">978-0-00-000001-1</dc:identifier>
            </metadata>
            """
        )

        response = self.client.post(
            self.url,
            {"file": upload_file("conflict.epub", epub)},
        )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["counts"]["conflict"], 1)
        self.assertEqual(payload["items"][0]["status"], "conflict")
        self.assertEqual(payload["items"][0]["source_label"], "conflict.epub")
        self.assertEqual(
            payload["items"][0]["safe_message"],
            "An identifier from this import already belongs to another book.",
        )
        self.assertEqual(payload["items"][0]["title"], "Existing")
        self.assertNotIn("checksum", payload["items"][0])
