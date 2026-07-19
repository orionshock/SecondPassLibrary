from __future__ import annotations

from contextlib import nullcontext
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TestCase

from accounts.models import UserProfile
from library.cover_services import (
    clear_book_cover,
    replace_book_cover,
    validate_book_cover_upload,
)
from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from tests.library.imports.helpers import image_bytes
from tests.testenv.filesystem import IsolatedMediaRootMixin
from tests.utils.users import set_user_role


class BookCoverApiTests(IsolatedMediaRootMixin, TestCase):
    def setUp(self):
        User = get_user_model()
        self.reader = User.objects.create_user(username="reader", password="pw")
        self.librarian = User.objects.create_user(username="librarian", password="pw")
        self.manager = User.objects.create_user(username="manager", password="pw")
        self.owner = User.objects.create_superuser(username="owner", password="pw")
        set_user_role(self.reader, UserProfile.ROLE_READER)
        set_user_role(self.librarian, UserProfile.ROLE_LIBRARIAN)
        set_user_role(self.manager, UserProfile.ROLE_MANAGER)
        self.group = LibraryGroup.objects.create(name="Visible")
        LibraryGroupMembership.objects.create(user=self.reader, group=self.group)
        self.book = Book.objects.create(
            title="Visible Book",
            description="Keep this metadata",
            checksum="book-checksum",
            file_size=123,
        )
        BookGroupAssignment.objects.create(book=self.book, group=self.group)
        self.url = f"/api/v1/library/books/{self.book.id}/cover/"

    def _login(self, username):
        self.client.logout()
        self.assertTrue(self.client.login(username=username, password="pw"))

    def _upload(self, data, *, name="cover.bin", content_type="application/octet-stream"):
        return self.client.post(
            self.url,
            {"cover": SimpleUploadedFile(name, data, content_type=content_type)},
        )

    def test_librarian_manager_and_owner_can_upload(self):
        for username, image_format, extension in (
            ("librarian", "JPEG", ".jpg"),
            ("manager", "PNG", ".png"),
            ("owner", "WEBP", ".webp"),
        ):
            with self.subTest(username=username):
                self._login(username)
                response = self._upload(image_bytes(image_format))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["cover_url"].endswith(extension))

    def test_content_not_filename_or_mime_controls_validation(self):
        self._login("librarian")
        accepted = self._upload(
            image_bytes("PNG"),
            name="not-an-image.txt",
            content_type="application/pdf",
        )
        rejected = self._upload(
            b"not an image",
            name="cover.jpg",
            content_type="image/jpeg",
        )

        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(accepted.json()["cover_url"].endswith(".png"))
        self.assertEqual(rejected.status_code, 400)
        self.assertIn("JPEG, PNG, or WebP", rejected.json()["cover"][0])

    def test_unsupported_corrupt_byte_and_pixel_limits_are_bounded(self):
        self._login("librarian")
        cases = (
            ("unsupported", image_bytes("GIF"), None),
            ("corrupt", b"not an image", None),
            ("bytes", image_bytes("PNG"), "bytes"),
            ("pixels", image_bytes("PNG"), "pixels"),
        )
        for label, data, limit in cases:
            with self.subTest(label=label):
                if limit == "bytes":
                    context = patch("library.cover_services.MAX_COVER_IMAGE_BYTES", 1)
                elif limit == "pixels":
                    context = patch("library.imports.covers.MAX_COVER_IMAGE_PIXELS", 1)
                else:
                    context = nullcontext()
                with context:
                    response = self._upload(data)
                self.assertEqual(response.status_code, 400)
                message = response.json()["cover"][0]
                self.assertLessEqual(len(message), 160)

    def test_reader_is_denied_and_invisible_book_stays_hidden(self):
        self._login("reader")
        visible = self._upload(image_bytes("PNG"))
        hidden = Book.objects.create(title="Hidden")
        hidden_url = f"/api/v1/library/books/{hidden.id}/cover/"
        invisible = self.client.post(
            hidden_url,
            {"cover": SimpleUploadedFile("cover.png", image_bytes("PNG"))},
        )

        self.assertEqual(visible.status_code, 403)
        self.assertEqual(invisible.status_code, 404)

    def test_successful_replace_changes_only_cover_and_failed_replace_preserves_it(self):
        self._login("manager")
        before = {
            "title": self.book.title,
            "description": self.book.description,
            "checksum": self.book.checksum,
            "file_format": self.book.file_format,
            "file_size": self.book.file_size,
        }
        success = self._upload(image_bytes("PNG"))
        self.book.refresh_from_db()
        stored_cover = self.book.cover_file.name
        failed = self._upload(b"broken", name="cover.png", content_type="image/png")
        self.book.refresh_from_db()

        self.assertEqual(success.status_code, 200)
        self.assertEqual(failed.status_code, 400)
        self.assertEqual(self.book.cover_file.name, stored_cover)
        self.assertEqual(
            {
                "title": self.book.title,
                "description": self.book.description,
                "checksum": self.book.checksum,
                "file_format": self.book.file_format,
                "file_size": self.book.file_size,
            },
            before,
        )

    def test_clear_is_idempotent_and_returns_book_contract(self):
        self._login("manager")
        self._upload(image_bytes("PNG"))

        first = self.client.delete(self.url)
        second = self.client.delete(self.url)
        self.book.refresh_from_db()

        self.assertEqual(first.status_code, 200)
        self.assertIsNone(first.json()["cover_url"])
        self.assertIn("catalog_tags", first.json())
        self.assertIn("identifiers", first.json())
        self.assertIn("groups", first.json())
        self.assertIn("file", first.json())
        self.assertNotIn("tags", first.json())
        self.assertNotIn("file_format", first.json())
        self.assertEqual(second.status_code, 200)
        self.assertIsNone(second.json()["cover_url"])
        self.assertFalse(self.book.cover_file)

    def test_bearer_authentication_is_not_accepted(self):
        self.client.logout()
        response = self.client.post(
            self.url,
            {"cover": SimpleUploadedFile("cover.png", image_bytes("PNG"))},
            HTTP_AUTHORIZATION="Bearer not-a-session-token",
        )

        self.assertEqual(response.status_code, 403)


class BookCoverServiceTests(IsolatedMediaRootMixin, TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(username="coveradmin", password="pw")
        self.book = Book.objects.create(title="Service Book")

    def _cover(self, image_format="PNG"):
        upload = SimpleUploadedFile("ignored.bin", image_bytes(image_format))
        return validate_book_cover_upload(upload)

    def test_old_unreferenced_cover_is_deleted_only_after_commit(self):
        replace_book_cover(book=self.book, cover=self._cover("PNG"), actor=self.actor)
        old_name = self.book.cover_file.name
        storage = self.book.cover_file.storage

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            replace_book_cover(book=self.book, cover=self._cover("JPEG"), actor=self.actor)
            self.assertTrue(storage.exists(old_name))

        for callback in callbacks:
            callback()
        self.assertFalse(storage.exists(old_name))

    def test_shared_cover_is_not_deleted_while_referenced(self):
        replace_book_cover(book=self.book, cover=self._cover(), actor=self.actor)
        shared_name = self.book.cover_file.name
        other = Book.objects.create(title="Other", cover_file=shared_name)
        storage = self.book.cover_file.storage

        with self.captureOnCommitCallbacks(execute=True):
            self.client.force_login(self.actor)
            set_user_role(self.actor, UserProfile.ROLE_LIBRARIAN)
            group = LibraryGroup.objects.create(name="Service Group")
            BookGroupAssignment.objects.create(book=self.book, group=group)
            response = self.client.delete(f"/api/v1/library/books/{self.book.id}/cover/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(storage.exists(shared_name))
        other.refresh_from_db()
        self.assertEqual(other.cover_file.name, shared_name)

    def test_storage_failure_leaves_previous_cover_intact(self):
        replace_book_cover(book=self.book, cover=self._cover("PNG"), actor=self.actor)
        old_name = self.book.cover_file.name
        storage = self.book.cover_file.storage

        with patch.object(storage, "exists", return_value=False), patch.object(
            storage, "save", side_effect=OSError("storage unavailable")
        ):
            with self.assertRaises(OSError):
                replace_book_cover(book=self.book, cover=self._cover("JPEG"), actor=self.actor)

        self.book.refresh_from_db()
        self.assertEqual(self.book.cover_file.name, old_name)

    def test_success_logs_readable_values_without_sensitive_data(self):
        with self.assertLogs("library.cover_services", level="INFO") as captured:
            with self.captureOnCommitCallbacks(execute=True):
                replace_book_cover(book=self.book, cover=self._cover(), actor=self.actor)
            with self.captureOnCommitCallbacks(execute=True):
                clear_book_cover(book=self.book, actor=self.actor)

        output = " ".join(captured.output)
        self.assertIn("Service Book", output)
        self.assertIn("coveradmin", output)
        self.assertIn("replaced", output)
        self.assertIn("cleared", output)
        for sensitive in ("ignored.bin", "covers/", "sha256", "image/png", "payload"):
            self.assertNotIn(sensitive, output)

    def test_rolled_back_change_emits_no_success_log(self):
        with self.assertNoLogs("library.cover_services", level="INFO"):
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    replace_book_cover(book=self.book, cover=self._cover(), actor=self.actor)
                    raise RuntimeError("roll back")
