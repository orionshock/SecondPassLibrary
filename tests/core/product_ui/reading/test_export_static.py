"""Tests for Export Marginalia Product UI."""
from pathlib import Path

from accounts.services import get_or_create_profile
from accounts.models import UserProfile
from django.contrib.auth import get_user_model
from library.group_services import add_book_to_group, ensure_user_public_membership
from library.models import LibraryGroup, LibraryGroupMembership
from reading.models import ReadingSession
from tests.core.product_ui.helpers import ProductUiTestCase
from tests.utils.books import create_file_backed_book


User = get_user_model()

class ProductUiExportMarginaliaTests(ProductUiTestCase):
    """Test reading sessions, import/export pages."""

    def _create_hidden_owned_session(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])
        ensure_user_public_membership(user=self.bootstrap_owner)
        ensure_user_public_membership(user=self.user)

        hidden_group = LibraryGroup.objects.create(name="Hidden")
        other = User.objects.create_user(username="hidden-owner", email="h@example.com")
        LibraryGroupMembership.objects.create(user=other, group=hidden_group)
        book = create_file_backed_book(title="Private Export Book", assign_public=False).book
        add_book_to_group(actor=self.bootstrap_owner, book=book, group=hidden_group)
        session = ReadingSession.objects.create(user=self.user, book=book, name="Recovered hidden")
        return book, session

    def test_unauthenticated_reading_export_redirects_to_login(self):
        response = self.client.get("/reading/export/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/reading/export/")

    def test_authenticated_reading_export_returns_200(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        book = create_file_backed_book(title="B1").book
        session = ReadingSession.objects.create(user=self.user, book=book, name="Mine")

        self.client.force_login(self.user)
        response = self.client.get("/reading/export/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(
            response,
            '<a class="breadcrumbs__link" href="/reading/sessions/">My Marginalia</a>',
            html=False,
        )
        self.assertContains(response, 'aria-current="page">Export Marginalia</li>', html=False)
        self.assertContains(response, "Export Marginalia")
        self.assertContains(response, "native SPL JSON")
        self.assertContains(response, "Exports can be previewed and restored")
        self.assertContains(response, "Server-side import/export only handles native SPL JSON")
        self.assertContains(response, "Imports from other services are handled")
        self.assertContains(response, "SecondPass Reading Client")
        self.assertContains(response, 'href="/reading/import/"')
        self.assertContains(response, "Import Marginalia")
        self.assertContains(response, "Complete archive")
        self.assertContains(
            response,
            "Export all marginalia you own, including sessions for books you can no longer view.",
        )
        self.assertContains(response, 'href="/api/v1/reading/export/"')
        self.assertContains(response, "Export all marginalia")
        self.assertContains(response, "Selective archive")
        self.assertContains(response, "Select a book or individual sessions")
        self.assertContains(response, "Export selected")
        self.assertContains(response, "disabled>Export selected</button>", html=False)
        self.assertContains(response, 'class="export-selection-bar"')
        self.assertContains(response, 'id="reading-export-selection-summary"')
        self.assertContains(response, 'id="reading-export-selection-status"')
        self.assertContains(response, "No selection")
        self.assertContains(response, 'id="reading-export-select-all"')
        self.assertContains(response, "Select all")
        self.assertContains(response, 'id="reading-export-clear"')
        self.assertContains(response, "Clear Selection")
        self.assertNotContains(response, "Import preview")
        self.assertContains(response, 'class="sessions-cover"')
        self.assertContains(response, "Cover")
        self.assertContains(response, 'class="export-book-row"')
        self.assertContains(response, 'class="export-book-select"')
        self.assertContains(response, f'data-book-id="{book.id}"')
        self.assertContains(response, 'class="export-session-list"')
        self.assertContains(response, 'class="export-session-row"')
        self.assertContains(response, 'class="export-session-select"')
        self.assertContains(response, f'data-session-id="{session.id}"')
        self.assertContains(response, "Show sessions")
        self.assertContains(response, "Mine")
        self.assertContains(response, 'class="meta-list"')
        self.assertContains(response, 'class="meta-item"')
        self.assertNotContains(response, "Books with reading data")
        self.assertNotContains(response, "Export by book")
        self.assertNotContains(response, "Export book marginalia")
        self.assertNotContains(response, "Open marginalia")
        self.assertNotContains(response, "Export all sessions")
        self.assertNotContains(response, "View sessions")
        self.assertNotContains(response, 'class="reading-session-select"')

    def test_authenticated_reading_export_includes_owned_hidden_book_sessions(self):
        book, session = self._create_hidden_owned_session()

        self.client.force_login(self.user)
        response = self.client.get("/reading/export/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recovered hidden")
        self.assertContains(response, "Book unavailable")
        self.assertNotContains(response, "Private Export Book")
        self.assertContains(response, f'data-book-id="{book.id}"')
        self.assertContains(response, f'data-session-id="{session.id}"')

    def test_reading_export_js_wires_selection_workflow(self):
        main_js = Path("web/static/web/js/main.js").read_text(encoding="utf-8")
        export_js = Path("web/static/web/js/reading/export.js").read_text(encoding="utf-8")

        self.assertIn('"reading-export"', main_js)
        self.assertIn('import("./reading/export.js")', main_js)
        self.assertIn("initReadingExport", export_js)
        self.assertIn("clearSelection", export_js)
        self.assertIn("selectedSummary", export_js)
        self.assertIn("reading-export-selection-summary", export_js)
        self.assertIn("reading-export-select-all", export_js)
        self.assertIn("reading-export-clear", export_js)
        self.assertIn("selectAll", export_js)
        self.assertIn("selected from ${rows.length} ${bookNoun}", export_js)
        self.assertIn("bookBox.indeterminate", export_js)
        self.assertIn("reading-export-selected", export_js)
        self.assertIn('fetch("/api/v1/reading/export/"', export_js)
        self.assertIn("JSON.stringify(body)", export_js)
        self.assertIn("selectedExportBody", export_js)
        self.assertIn('? "all"', export_js)
        self.assertIn("URL.createObjectURL", export_js)
        self.assertNotIn("Export selected currently supports one book at a time.", export_js)
        self.assertNotIn("window.location.assign(url)", export_js)
        self.assertNotIn("URLSearchParams", export_js)
        self.assertIn("Show sessions", export_js)
        self.assertIn("Hide sessions", export_js)
        self.assertNotIn("history.back", export_js)
        self.assertNotIn("&middot;", export_js)
        self.assertNotIn("&#183;", export_js)
