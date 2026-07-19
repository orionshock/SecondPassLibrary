from __future__ import annotations

import hashlib
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import AsyncClient, TestCase
from django.utils.http import content_disposition_header
from rest_framework.test import APIClient

from accounts.client_api import hash_client_secret
from accounts.models import UserClientSession, UserProfile
from library.catalog.downloads import DOWNLOAD_FILENAME_MAX_CHARS, book_download_filename
from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from tests.testenv.filesystem import IsolatedMediaRootMixin
from tests.utils.users import set_user_role


class BookDownloadApiTests(IsolatedMediaRootMixin, TestCase):
    visible_bytes = b"visible canonical epub bytes"
    hidden_bytes = b"hidden canonical epub bytes"

    def setUp(self):
        User = get_user_model()
        self.reader = User.objects.create_user(username="reader", password="pw")
        self.manager = User.objects.create_user(username="manager", password="pw")
        set_user_role(self.reader, UserProfile.ROLE_READER)
        set_user_role(self.manager, UserProfile.ROLE_MANAGER)
        self.visible_group = LibraryGroup.objects.create(name="Visible")
        self.hidden_group = LibraryGroup.objects.create(name="Hidden")
        LibraryGroupMembership.objects.create(user=self.reader, group=self.visible_group)
        self.visible_book = self._file_backed_book(
            title="Visible Book",
            data=self.visible_bytes,
            group=self.visible_group,
        )
        self.hidden_book = self._file_backed_book(
            title="Hidden Book",
            data=self.hidden_bytes,
            group=self.hidden_group,
        )
        self.reader_token = self._token(self.reader, "spl_reader_download_token")
        self.manager_token = self._token(self.manager, "spl_manager_download_token")

    def _file_backed_book(self, *, title, data, group):
        checksum = hashlib.sha256(data).hexdigest()
        book = Book.objects.create(
            title=title,
            checksum=checksum,
            file_size=len(data),
        )
        book.book_file.save("import.epub", ContentFile(data), save=True)
        BookGroupAssignment.objects.create(book=book, group=group)
        return book

    @staticmethod
    def _token(user, raw_token):
        UserClientSession.objects.create(
            user=user,
            name="Reader client",
            client_type="reader",
            token_hash=hash_client_secret(raw_token),
        )
        return raw_token

    @staticmethod
    def _url(book):
        return f"/api/v1/library/books/{book.id}/download/"

    @staticmethod
    def _streamed_body(response):
        try:
            return b"".join(response.streaming_content)
        finally:
            response.close()

    def _bearer_get(self, book, token, **extra):
        return APIClient().get(
            self._url(book),
            HTTP_AUTHORIZATION=f"Bearer {token}",
            **extra,
        )

    def test_visible_reader_session_and_bearer_stream_exact_epub(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))
        session_response = self.client.get(self._url(self.visible_book))
        bearer_response = self._bearer_get(self.visible_book, self.reader_token)

        for response in [session_response, bearer_response]:
            with self.subTest(authentication=response.wsgi_request.META.get("HTTP_AUTHORIZATION", "session")):
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.streaming)
                self.assertEqual(response["Content-Type"], "application/epub+zip")
                self.assertEqual(int(response["Content-Length"]), len(self.visible_bytes))
                headers = str(dict(response.items()))
                self.assertNotIn(self.visible_book.book_file.name, headers)
                self.assertNotIn(self.visible_book.checksum, headers)
                body = self._streamed_body(response)
                self.assertEqual(body, self.visible_bytes)
                self.assertNotIn(self.visible_book.book_file.name.encode(), body)

    async def test_asgi_download_uses_async_streaming_iterator(self):
        response = await AsyncClient().get(
            self._url(self.visible_book),
            headers={"authorization": f"Bearer {self.reader_token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_async)
        try:
            body = b"".join([chunk async for chunk in response.streaming_content])
        finally:
            response.close()
        self.assertEqual(body, self.visible_bytes)

    def test_privileged_session_and_bearer_keep_broad_download_visibility(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))
        session_response = self.client.get(self._url(self.hidden_book))
        bearer_response = self._bearer_get(self.hidden_book, self.manager_token)

        self.assertEqual(self._streamed_body(session_response), self.hidden_bytes)
        self.assertEqual(self._streamed_body(bearer_response), self.hidden_bytes)

    def test_hidden_and_unknown_books_have_the_same_404_contract(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))
        session_hidden = self.client.get(self._url(self.hidden_book))
        bearer_hidden = self._bearer_get(self.hidden_book, self.reader_token)
        unknown = self.client.get(
            f"/api/v1/library/books/{uuid4()}/download/"
        )

        self.assertEqual(session_hidden.status_code, 404)
        self.assertEqual(bearer_hidden.status_code, 404)
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(session_hidden.json(), unknown.json())

    def test_anonymous_and_unsafe_methods_are_denied(self):
        url = self._url(self.visible_book)
        anonymous = self.client.get(url)
        bearer = APIClient()
        headers = {"HTTP_AUTHORIZATION": f"Bearer {self.manager_token}"}

        self.assertEqual(anonymous.status_code, 403)
        for method in [bearer.post, bearer.patch, bearer.delete]:
            with self.subTest(method=method.__name__):
                self.assertEqual(method(url, {}, format="json", **headers).status_code, 405)

    def test_content_disposition_is_generated_from_sanitized_unicode_title(self):
        self.visible_book.title = '../Mañana\\"Book\r\n.epub'
        self.visible_book.save(update_fields=["title", "updated_at"])
        response = self._bearer_get(self.visible_book, self.reader_token)
        expected_filename = book_download_filename(self.visible_book.title)
        internal_name = self.visible_book.book_file.name

        self.assertEqual(
            response["Content-Disposition"],
            content_disposition_header(True, expected_filename),
        )
        self.assertNotIn("\r", response["Content-Disposition"])
        self.assertNotIn("\n", response["Content-Disposition"])
        self.assertNotIn(internal_name, response["Content-Disposition"])
        self.assertNotIn(self.visible_book.checksum, response["Content-Disposition"])
        self._streamed_body(response)

    def test_generated_filename_is_bounded_and_has_no_path_or_control_characters(self):
        filename = book_download_filename("../" + ("Ü" * 400) + "\\bad\x00\r\n.epub")

        self.assertLessEqual(len(filename), DOWNLOAD_FILENAME_MAX_CHARS)
        self.assertTrue(filename.endswith(".epub"))
        self.assertFalse(any(character in filename for character in '/\\\x00\r\n"'))

    def test_detail_exposes_download_url_without_storage_identity(self):
        response = APIClient().get(
            f"/api/v1/library/books/{self.visible_book.id}/",
            HTTP_AUTHORIZATION=f"Bearer {self.reader_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["file"]["download_url"],
            f"http://testserver{self._url(self.visible_book)}",
        )
        self.assertNotIn(self.visible_book.book_file.name, str(response.json()))

    def test_fileless_and_non_epub_books_return_bounded_conflict(self):
        fileless = Book.objects.create(title="Fileless")
        BookGroupAssignment.objects.create(book=fileless, group=self.visible_group)
        self.visible_book.file_format = "pdf"
        self.visible_book.save(update_fields=["file_format", "updated_at"])

        for book in [fileless, self.visible_book]:
            with self.subTest(book=book.title):
                response = self._bearer_get(book, self.reader_token)
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.json()["error"]["code"], "BOOK_FILE_UNAVAILABLE")
                self.assertNotIn("books/", str(response.json()))

    def test_missing_and_unreadable_storage_return_bounded_503_and_safe_log(self):
        internal_name = self.visible_book.book_file.name
        storage = self.visible_book.book_file.storage
        storage.delete(internal_name)

        with self.assertLogs("library.catalog.download_views", level="WARNING") as missing_logs:
            missing = self._bearer_get(self.visible_book, self.reader_token)
        with patch.object(storage, "open", side_effect=PermissionError("C:/private/secret.epub")):
            with self.assertLogs("library.catalog.download_views", level="WARNING") as unreadable_logs:
                unreadable = self._bearer_get(self.visible_book, self.reader_token)

        for response in [missing, unreadable]:
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["error"]["code"], "BOOK_FILE_UNAVAILABLE")
            self.assertNotIn("private", str(response.json()).casefold())
            self.assertNotIn(internal_name, str(response.json()))
        combined_logs = " ".join(missing_logs.output + unreadable_logs.output)
        self.assertIn("Visible Book", combined_logs)
        self.assertIn("reader", combined_logs)
        self.assertIn("PermissionError", combined_logs)
        self.assertNotIn(internal_name, combined_logs)
        self.assertNotIn("C:/private", combined_logs)

    def test_response_close_closes_the_storage_file_handle(self):
        storage = self.visible_book.book_file.storage
        real_open = storage.open
        opened = []

        def tracked_open(*args, **kwargs):
            handle = real_open(*args, **kwargs)
            opened.append(handle)
            return handle

        with patch.object(storage, "open", side_effect=tracked_open):
            response = self._bearer_get(self.visible_book, self.reader_token)
            self.assertEqual(self._streamed_body(response), self.visible_bytes)

        self.assertEqual(len(opened), 1)
        self.assertTrue(opened[0].closed)

    def test_range_header_deliberately_returns_complete_file(self):
        response = self._bearer_get(
            self.visible_book,
            self.reader_token,
            HTTP_RANGE="bytes=0-3",
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Content-Range", response)
        self.assertEqual(self._streamed_body(response), self.visible_bytes)
