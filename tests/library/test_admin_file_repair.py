from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import path, reverse

from library.admin import BookAdmin
from library.file_repair import StoredEpubRepairError
from library.models import Book
from tests.library.imports.helpers import minimal_epub_bytes
from tests.testenv.filesystem import IsolatedMediaRootMixin
from tests.utils.books import create_file_backed_book


urlpatterns = [path("admin/", admin.site.urls)]


def epub_bytes(title: str) -> bytes:
    return minimal_epub_bytes(
        metadata_xml=f"""
        <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
          <dc:title>{title}</dc:title>
          <dc:language>en</dc:language>
        </metadata>
        """
    )


@override_settings(ROOT_URLCONF=__name__)
class StoredEpubRepairAdminTests(IsolatedMediaRootMixin, TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_superuser(username="owner", password="pw")
        self.staff = User.objects.create_user(
            username="staff",
            password="pw",
            is_staff=True,
        )
        self.original_data = epub_bytes("Original")
        self.book = create_file_backed_book(
            title="Repair Target",
            epub_bytes=self.original_data,
            source_filename="original.epub",
            assign_public=False,
        ).book
        self.change_url = reverse("admin:library_book_change", args=[self.book.pk])
        self.repair_url = reverse(
            "admin:library_book_repair_stored_epub",
            args=[self.book.pk],
        )

    def _login_owner(self):
        self.assertTrue(self.client.login(username="owner", password="pw"))

    @staticmethod
    def _upload(data):
        return SimpleUploadedFile(
            "replacement.epub",
            data,
            content_type="application/epub+zip",
        )

    def test_superuser_sees_repair_action(self):
        self._login_owner()

        response = self.client.get(self.change_url)

        self.assertContains(response, "Repair stored EPUB")
        self.assertContains(response, self.repair_url)

    def test_non_superuser_is_denied(self):
        self.assertTrue(self.client.login(username="staff", password="pw"))

        response = self.client.get(self.repair_url)

        self.assertEqual(response.status_code, 403)

    def test_generic_file_fields_are_read_only(self):
        model_admin = BookAdmin(Book, admin.site)

        self.assertTrue(
            {"book_file", "file_format", "checksum", "file_size"}.issubset(
                model_admin.readonly_fields
            )
        )

    def test_get_renders_current_state_warnings_and_preservation_scope(self):
        self._login_owner()

        response = self.client.get(self.repair_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Repair stored EPUB")
        self.assertContains(response, "Target Book:")
        self.assertContains(response, "Physical stored file:")
        self.assertContains(response, "Present")
        self.assertContains(response, "Replacement EPUB")
        self.assertContains(response, "Replace existing stored file")
        self.assertContains(response, "Allow different checksum")
        self.assertContains(response, "EPUB CFI anchors")
        self.assertContains(response, "reading sessions, progress, or annotations")
        self.assertNotContains(response, "source_filename")
        self.assertNotContains(response, "Source filename")

    def test_missing_upload_is_rejected(self):
        self._login_owner()

        response = self.client.post(self.repair_url, {})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")

    def test_existing_file_replacement_requires_confirmation(self):
        self._login_owner()

        response = self.client.post(
            self.repair_url,
            {"replacement_epub": self._upload(self.original_data)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Confirm replacement of the existing stored EPUB",
        )

    def test_checksum_change_requires_explicit_confirmation(self):
        self._login_owner()

        response = self.client.post(
            self.repair_url,
            {
                "replacement_epub": self._upload(epub_bytes("Changed")),
                "replace_existing": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirm the different checksum")
        self.assertContains(response, "EPUB CFI anchors may no longer match")

    def test_successful_same_checksum_repair_redirects_with_success_message(self):
        self._login_owner()

        response = self.client.post(
            self.repair_url,
            {
                "replacement_epub": self._upload(self.original_data),
                "replace_existing": "on",
            },
            follow=True,
        )

        self.assertRedirects(response, self.change_url)
        self.assertContains(response, "Stored EPUB repaired successfully.")

    def test_confirmed_checksum_change_succeeds_and_warns(self):
        self._login_owner()

        response = self.client.post(
            self.repair_url,
            {
                "replacement_epub": self._upload(epub_bytes("Changed")),
                "replace_existing": "on",
                "allow_checksum_change": "on",
            },
            follow=True,
        )

        self.assertRedirects(response, self.change_url)
        self.assertContains(response, "Stored EPUB repaired successfully.")
        self.assertContains(response, "Existing EPUB CFI anchors may no longer match.")

    @patch("library.admin.repair_stored_epub")
    def test_service_errors_are_bounded(self, repair_stored_epub):
        repair_stored_epub.side_effect = StoredEpubRepairError(
            r"C:\private\library\secret.epub failed with deadbeef"
        )
        self._login_owner()

        response = self.client.post(
            self.repair_url,
            {
                "replacement_epub": self._upload(self.original_data),
                "replace_existing": "on",
            },
        )

        self.assertContains(response, "Stored EPUB repair could not be completed.")
        self.assertNotContains(response, "private")
        self.assertNotContains(response, "deadbeef")

    def test_cancel_returns_to_book_change_page(self):
        self._login_owner()

        response = self.client.get(self.repair_url)

        self.assertContains(response, f'href="{self.change_url}">Cancel</a>', html=False)
