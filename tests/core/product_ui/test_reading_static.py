"""Tests for reading sessions, import, and export pages."""
from pathlib import Path

from accounts.services import get_or_create_profile
from accounts.models import UserProfile
from django.contrib.auth import get_user_model
from reading.models import ReadingSession
from tests.core.product_ui.helpers import ProductUiTestCase
from tests.utils.books import create_file_backed_book
from uuid import uuid4


User = get_user_model()


class ProductUiReadingTests(ProductUiTestCase):
    """Test reading sessions, import/export pages."""

    def test_unauthenticated_reading_sessions_redirects_to_login(self):
        book_id = uuid4()
        response = self.client.get(f"/reading/sessions/books/{book_id}/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            f"/api-auth/login/?next=/reading/sessions/books/{book_id}/",
        )

    def test_unauthenticated_reading_sessions_all_redirects_to_login(self):
        response = self.client.get("/reading/sessions/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/reading/sessions/")

    def test_unauthenticated_reading_export_redirects_to_login(self):
        response = self.client.get("/reading/export/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/reading/export/")

    def test_unauthenticated_reading_import_redirects_to_login(self):
        response = self.client.get("/reading/import/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/reading/import/")

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
        self.assertContains(response, "Export all marginalia for books currently visible to you.")
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

    def test_authenticated_reading_import_returns_200(self):
        self.client.force_login(self.user)
        response = self.client.get("/reading/import/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(
            response,
            '<a class="breadcrumbs__link" href="/reading/sessions/">My Marginalia</a>',
            html=False,
        )
        self.assertContains(response, 'aria-current="page">Import Marginalia</li>', html=False)
        self.assertContains(response, "Import Marginalia")
        self.assertContains(response, "Preview and import SPL native marginalia exports.")
        self.assertContains(response, "SPL native marginalia export")
        self.assertContains(response, "Foreign annotation formats")
        self.assertContains(response, 'id="reading-import-preview-form"')
        self.assertContains(response, 'id="reading-import-file"')
        self.assertContains(response, 'id="reading-import-apply-controls"')
        self.assertContains(response, 'id="reading-import-apply-results"')
        self.assertContains(response, 'id="reading-import-session-modal"')
        self.assertContains(response, 'id="reading-import-session-modal-name"')
        self.assertContains(response, 'id="reading-import-session-modal-notes"')
        self.assertContains(response, 'href="/reading/export/"')
        self.assertContains(response, "Export Marginalia")
        self.assertNotContains(response, "Browse by Session")
        self.assertNotContains(response, "Export center")
        self.assertNotContains(response, "Reading sessions")

    def test_reading_import_js_wires_apply_after_preview(self):
        js = Path("web/static/web/js/reading/import_preview.js").read_text()
        rendering_js = Path("web/static/web/js/reading/import_rendering.js").read_text()
        selection_js = Path("web/static/web/js/reading/import_selection.js").read_text()
        modal_js = Path("web/static/web/js/reading/import_edit_modal.js").read_text()
        self.assertIn("renderApplyControls", js)
        self.assertIn("Apply import", rendering_js)
        self.assertIn("Select all", rendering_js)
        self.assertIn("Select none", rendering_js)
        self.assertIn("reading-import-select-all-top", rendering_js)
        self.assertIn("import-book-select", rendering_js)
        self.assertIn("import-book-select--large", rendering_js)
        self.assertIn("import-session-select", rendering_js)
        self.assertIn("import-session-edit", rendering_js)
        self.assertIn("Matched to", rendering_js)
        self.assertIn("bookMetadataParts", rendering_js)
        self.assertIn("matchLine", rendering_js)
        self.assertIn("humanizeMatchMethod", rendering_js)
        self.assertIn("countText", rendering_js)
        self.assertIn("formatDate", rendering_js)
        self.assertIn("Possible duplicate sessions found.", rendering_js)
        self.assertIn("suppressedSessionWarning", rendering_js)
        self.assertIn("renderMetaList", rendering_js)
        self.assertIn('class="meta-item"', rendering_js)
        self.assertIn("Matched to ${title}", rendering_js)
        self.assertIn('replace(/_/g, " ")', rendering_js)
        self.assertNotIn("&middot;", rendering_js)
        self.assertNotIn("&#183;", rendering_js)
        self.assertNotIn('"Matched to", title', rendering_js)
        self.assertNotIn("Match: <span", rendering_js)
        self.assertNotIn("Method:", rendering_js)
        self.assertNotIn("annotation(s), ${escapeHtml(session.bookmark_count)}", rendering_js)
        self.assertIn("reading-import-session-modal", js)
        self.assertIn("bookBox.indeterminate", selection_js)
        self.assertIn("No matched local books can be imported.", rendering_js)
        self.assertIn("import-session-name", modal_js)
        self.assertIn("/api/v1/reading/import/apply/", js)
        self.assertIn('formData.append("import_token", currentImportToken)', js)
        self.assertIn('formData.append("selection"', js)
        self.assertIn("buildSelection", js)
        self.assertIn("clearImportData", js)
        self.assertIn('input.value = ""', js)
        self.assertIn("currentPreview = null", js)
        self.assertIn("target.disabled = true", js)
        self.assertIn("renderApplyResult", js)
        self.assertIn("sessions_created", rendering_js)
        self.assertIn("bookmarks_created", rendering_js)
        self.assertIn("commented_highlights_created", rendering_js)

    def test_authenticated_reading_sessions_scopes_to_user_and_book(self):
        # Make the user a librarian so book visibility is not dependent on group membership setup.
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        other = User.objects.create_user(
            username="u2", email="u2@example.com", password="pw"
        )

        book = create_file_backed_book(title="B1").book
        other_book = create_file_backed_book(title="B2").book

        mine = ReadingSession.objects.create(
            user=self.user,
            book=book,
            name="Mine",
            status=ReadingSession.STATUS_COMPLETED,
            is_active=False,
        )
        unnamed = ReadingSession.objects.create(user=self.user, book=book, name="")
        ReadingSession.objects.create(user=self.user, book=other_book, name="Other book")
        others = ReadingSession.objects.create(user=other, book=book, name="Other user")
        unnamed_suffix = str(unnamed.id)[-8:]

        self.client.force_login(self.user)
        response = self.client.get(f"/reading/sessions/books/{book.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(
            response,
            '<a class="breadcrumbs__link" href="/reading/sessions/">My Marginalia</a>',
            html=False,
        )
        self.assertContains(
            response,
            '<a class="breadcrumbs__link" href="/reading/sessions/?view=book">Browse by Book</a>',
            html=False,
        )
        self.assertContains(response, f'aria-current="page">{book.title}</li>', html=False)
        self.assertNotContains(response, "Back to Dashboard")
        self.assertContains(response, f'data-book-id="{book.id}"')
        self.assertContains(response, f"Marginalia for {book.title}")
        self.assertContains(response, "No sessions yet for this book.", count=0)

        # Only the current user's sessions for this book appear.
        self.assertContains(response, str(mine.id))
        self.assertContains(response, str(unnamed.id))
        self.assertNotContains(response, str(others.id))

        # Sessions link to their canonical marginalia records.
        self.assertContains(
            response,
            f"/reading/sessions/books/{book.id}/{mine.id}/",
        )
        self.assertContains(
            response,
            f"/reading/sessions/books/{book.id}/{unnamed.id}/",
        )
        self.assertContains(response, 'class="card sessions-row sessions-row--link"')
        self.assertContains(response, "Mine")
        self.assertContains(response, "Unnamed session")
        self.assertContains(response, unnamed_suffix)
        self.assertContains(response, f"Unnamed session, {unnamed_suffix}", html=False)
        self.assertContains(response, 'class="meta-list"')
        self.assertContains(response, 'class="meta-item"')
        self.assertNotContains(response, "&#183;")
        self.assertNotContains(response, "&middot;")
        self.assertNotContains(response, f">{unnamed.id}<")
        self.assertNotContains(response, f"Session ID: {unnamed.id}")
        self.assertNotContains(response, "Session ID:")
        self.assertContains(response, 'href="/library/books/')
        self.assertContains(response, "Book details")
        self.assertNotContains(response, f"/api/v1/reading/export/books/{book.id}/")
        self.assertNotContains(response, "Export all sessions")
        self.assertNotContains(response, 'id="reading-sessions-export-selected"')
        self.assertNotContains(response, "Export selected")
        self.assertNotContains(response, "Select sessions to export a subset.")
        self.assertNotContains(response, 'class="reading-session-select"')

    def test_reading_book_sessions_page_has_no_inline_export_module(self):
        main_js = Path("web/static/web/js/main.js").read_text(encoding="utf-8")
        self.assertNotIn('import("./reading/book_sessions.js")', main_js)
        self.assertNotIn("initReadingBookSessions", main_js)
        self.assertFalse(Path("web/static/web/js/reading/book_sessions.js").exists())

    def test_reading_activity_js_updates_breadcrumbs_from_loaded_context(self):
        js = Path("web/static/web/js/reading/activity.js").read_text(encoding="utf-8")
        actions_js = Path("web/static/web/js/reading/activity_actions.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('from "../ui/breadcrumbs.js"', js)
        self.assertIn("function syncActivityBreadcrumb", js)
        self.assertIn("sessionDisplayLabel", js)
        self.assertIn("sessionDisplayLabel(state)", actions_js)
        self.assertIn('Unnamed session \\u00b7 ${id.slice(-8)}', actions_js)
        self.assertIn('const label = state && state.sessionIsActive ? "Active" : "Closed"', actions_js)
        self.assertIn("Marginalia session \\u00b7 ${label}", actions_js)
        self.assertNotIn('Session: "${sessionDisplayName}"', actions_js)
        self.assertIn('{ label: "My Marginalia", href: "/reading/sessions/" }', js)
        self.assertIn('{ label: "Browse by Book", href: "/reading/sessions/?view=book" }', js)
        self.assertIn('href: `/reading/sessions/books/${encodeURIComponent(String(bookId))}/`', js)
        self.assertIn("sessionBreadcrumbLabel(sessionState)", js)
        self.assertIn("titleEl.textContent = sessionDisplayLabel(sessionState)", js)
        self.assertNotIn("Marginalia: ${sessionDisplayLabel(sessionState)}", js)
        self.assertIn('sessionIdEl.textContent = ""', js)
        self.assertNotIn("Session ID: ${sessionState.sessionId}", js)
        self.assertIn("onSessionChanged", js)
        self.assertIn("onSessionChanged", actions_js)

    def test_authenticated_reading_sessions_empty_state(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        book = create_file_backed_book(title="B1").book

        self.client.force_login(self.user)
        response = self.client.get(f"/reading/sessions/books/{book.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No sessions yet for this book.")

    def test_authenticated_reading_sessions_all_scopes_to_user_and_visible_books(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        other = User.objects.create_user(username="u2", email="u2@example.com", password="pw")

        book = create_file_backed_book(title="B1").book
        mine = ReadingSession.objects.create(user=self.user, book=book, name="Mine")
        others = ReadingSession.objects.create(user=other, book=book, name="Other user")

        self.client.force_login(self.user)
        response = self.client.get("/reading/sessions/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(
            response,
            '<a class="breadcrumbs__link" href="/reading/sessions/">My Marginalia</a>',
            html=False,
        )
        self.assertContains(response, 'aria-current="page">Browse by Session</li>', html=False)
        self.assertContains(
            response,
            'id="reading-sessions-all-title">Marginalia by Session</h1>',
        )
        self.assertNotContains(response, 'id="reading-sessions-all-title">Sessions</h1>')
        self.assertContains(response, 'id="reading-sessions-subtitle"')
        self.assertContains(response, 'class="sessions-controls"')
        self.assertContains(response, 'id="reading-sessions-controls"')
        self.assertContains(response, 'class="tabs sessions-controls__group sessions-status-filters"')
        self.assertContains(response, 'id="reading-sessions-status-filters"')
        self.assertContains(response, 'data-status-filter="all"')
        self.assertContains(response, 'aria-pressed="true"')
        self.assertContains(response, 'data-status-filter="active"')
        self.assertContains(response, 'data-status-filter="closed"')
        self.assertContains(response, 'id="reading-sessions-search-form"')
        self.assertContains(response, 'id="reading-sessions-search"')
        self.assertContains(
            response,
            '<label class="sr-only" for="reading-sessions-search">Search sessions</label>',
        )
        self.assertNotContains(
            response,
            '<label class="search__label" for="reading-sessions-search">Search</label>',
        )
        self.assertContains(
            response,
            'placeholder="Session name, notes, or visible book metadata..."',
        )
        self.assertContains(response, 'id="reading-sessions-search-button"')
        self.assertContains(
            response,
            'id="reading-sessions-search-button" class="button" type="submit">Search</button>',
        )
        self.assertContains(response, 'class="sessions-controls__group sessions-controls__page-size"')
        self.assertContains(response, 'id="reading-sessions-page-size"')
        self.assertContains(response, '<option value="10" selected>10</option>')
        self.assertContains(response, 'id="reading-sessions-results"')
        self.assertContains(response, 'id="reading-sessions-view-toggle"')
        self.assertContains(response, 'data-view-mode="session"')
        self.assertContains(response, 'data-view-mode="book"')
        self.assertContains(response, 'class="sessions-view-bar"')
        self.assertContains(
            response,
            'data-view-mode="session" aria-pressed="true">By Session</button>',
        )
        self.assertContains(response, 'id="reading-sessions-page-size"')
        self.assertContains(response, 'id="reading-sessions-page-size-bottom"')
        self.assertContains(response, 'class="reading-sessions-page-size"')
        self.assertContains(response, 'class="button reading-sessions-prev"')
        self.assertContains(response, 'class="button reading-sessions-next"')
        self.assertContains(response, 'id="reading-sessions-view-note"')
        self.assertContains(response, 'id="reading-sessions-status"')
        self.assertContains(response, 'class="pager sessions-pager"')
        self.assertContains(response, 'id="reading-sessions-prev"')
        self.assertContains(response, 'id="reading-sessions-next"')

        # Current user's session is present.
        self.assertContains(response, str(mine.id))
        # Other user's session not shown.
        self.assertNotContains(response, str(others.id))

        # Selectable card text is separate from explicit session/book links.
        self.assertContains(response, f"/reading/sessions/books/{book.id}/{mine.id}/")
        self.assertContains(response, 'class="card sessions-row sessions-card"')
        self.assertContains(response, 'class="sessions-card__cover-link"')
        self.assertContains(response, 'class="sessions-card__title"')
        self.assertContains(response, 'aria-label="Open session"')
        self.assertContains(response, 'aria-label="View sessions for this book"')
        self.assertContains(response, "article")
        self.assertContains(response, "auto_stories")
        self.assertContains(response, f"/reading/sessions/books/{book.id}/")
        self.assertNotContains(response, f"/reading/sessions/?book={book.id}")
        self.assertNotContains(
            response,
            '<a class="card sessions-row sessions-card"',
        )
        self.assertNotContains(response, 'role="link"')
        self.assertNotContains(response, 'tabindex="0"')
        self.assertNotContains(response, "View session marginalia")
        self.assertNotContains(response, ">View book sessions</")
        self.assertContains(response, "Active")

    def test_reading_sessions_js_wires_filters_search_page_size_and_book_context(self):
        js = Path("web/static/web/js/reading/sessions.js").read_text(encoding="utf-8")
        main_js = Path("web/static/web/js/main.js").read_text(encoding="utf-8")
        css = Path("web/static/web/app.css").read_text(encoding="utf-8")

        self.assertIn("const DEFAULT_PAGE_SIZE = 10", js)
        self.assertIn('from "../ui/breadcrumbs.js"', js)
        self.assertIn("function syncSessionsBreadcrumb", js)
        self.assertIn("function sessionsHeading", js)
        self.assertIn('state.view === "book" ? "Marginalia by Book" : "Marginalia by Session"', js)
        self.assertIn("titleEl.textContent = sessionsHeading(state)", js)
        self.assertIn('{ label: "My Marginalia", href: "/reading/sessions/" }', js)
        self.assertIn('state.view === "book" ? "Browse by Book" : "Browse by Session"', js)
        self.assertIn("syncSessionsBreadcrumb(state)", js)
        self.assertIn('params.get("book")', js)
        self.assertIn('params.get("q")', js)
        self.assertIn('params.get("page")', js)
        self.assertIn('params.get("status")', js)
        self.assertIn('params.get("page_size")', js)
        self.assertIn('params.get("view")', js)
        self.assertIn('document.querySelectorAll(".reading-sessions-page-size")', js)
        self.assertIn('url.searchParams.set("q", state.q)', js)
        self.assertIn('url.searchParams.set("is_active", "true")', js)
        self.assertIn('url.searchParams.set("is_active", "false")', js)
        self.assertIn('url.searchParams.set("page", String(state.page))', js)
        self.assertIn('url.searchParams.set("page_size", String(state.pageSize))', js)
        self.assertIn('if (state.page > 1) params.set("page", String(state.page))', js)
        self.assertIn('if (state.status !== "all") params.set("status", state.status)', js)
        self.assertIn('if (state.pageSize !== DEFAULT_PAGE_SIZE) params.set("page_size", String(state.pageSize))', js)
        self.assertNotIn('params.set("status", "all")', js)
        self.assertIn("state = { ...state, page: 1 }", js)
        self.assertIn("state = { ...state, page: Math.max(1, state.page - 1) }", js)
        self.assertIn("state = { ...state, page: state.page + 1 }", js)
        self.assertIn('url.searchParams.set("book", state.book)', js)
        self.assertIn('params.set("view", state.view)', js)
        self.assertIn("writeQueryState", js)
        self.assertIn('document.querySelectorAll(".reading-sessions-prev")', js)
        self.assertIn('document.querySelectorAll(".reading-sessions-next")', js)
        self.assertIn("function syncPaginationButtons", js)
        self.assertIn("prevBtns.forEach", js)
        self.assertIn("nextBtns.forEach", js)
        self.assertIn('button.setAttribute("aria-pressed", active ? "true" : "false")', js)
        self.assertIn("Reading sessions for ${String(book.title)}", js)
        self.assertIn("sessionCardTitle(session, bookTitle)", js)
        self.assertIn("appendSeparatedParts", js)
        self.assertIn('el("span", "metadata-piece", part)', js)
        self.assertIn('el("div", "card sessions-row sessions-card")', js)
        self.assertIn('el("a", "sessions-card__cover-link")', js)
        self.assertIn('el("a", "sessions-card__title"', js)
        self.assertIn('`/reading/sessions/books/${encodeURIComponent(bookId)}/`', js)
        self.assertNotIn("bindCardInteraction", js)
        self.assertNotIn("window.location.assign", js)
        self.assertNotIn('card.setAttribute("role", "link")', js)
        self.assertNotIn("card.tabIndex", js)
        self.assertIn('label: "Open session"', js)
        self.assertIn('label: "View sessions for this book"', js)
        self.assertIn('icon: "article"', js)
        self.assertIn('icon: "auto_stories"', js)
        self.assertIn("bookSessionsHref", js)
        self.assertIn("groupSessionsByBook", js)
        self.assertIn("renderBookGroup", js)
        self.assertIn('el("a",', js)
        self.assertIn("group.dataset.bookSessionsUrl = bookSessionsHref", js)
        self.assertIn("function isInteractiveElement", js)
        self.assertIn('element.closest("a, button, input, select, textarea, label, summary, details")', js)
        self.assertIn('source.closest("[data-book-sessions-url]")', js)
        self.assertIn("window.location.href = url", js)
        self.assertIn('el("a", "sessions-book-group__title", bookTitle)', js)
        self.assertIn("coverLink.href = bookSessionsHref", js)
        self.assertIn("titleLink.href = bookSessionsHref", js)
        self.assertIn("titleLink.href = marginaliaHref", js)
        self.assertIn('state.view === "book"', js)
        self.assertIn('el("div", "muted sessions-row__id", sessionId)', js)
        self.assertIn('session && session.is_active ? "Active" : "Closed"', js)
        self.assertIn('`${sessions.length} session${sessions.length === 1 ? "" : "s"}`', js)
        self.assertNotIn("Grouped by book for this page of results.", js)
        self.assertNotIn("on this page", js)
        self.assertNotIn("renderCompactSessionRow", js)
        self.assertNotIn("sessions-book-group__session-title", js)
        self.assertNotIn("sessions-book-group__sessions", js)
        self.assertNotIn("sessions-book-group__session-main", js)
        self.assertNotIn("/reading/sessions/?book=", js)
        self.assertNotIn("View session marginalia", js)
        self.assertNotIn(">View book sessions</", js)
        self.assertIn("No reading sessions for ${String(book.title)} yet.", js)
        self.assertNotIn("/api/v1/library/books/", js)
        self.assertIn('import("./reading/sessions.js")', main_js)
        self.assertIn('initExportName: "initReadingSessions"', main_js)
        self.assertIn(".sessions-controls .sessions-status-filters", css)
        self.assertIn("border-bottom: 0", css)
        self.assertIn(".metadata-piece + .metadata-piece::before", css)
        self.assertIn(".sessions-view-bar > .sessions-controls__page-size", css)
        self.assertIn("justify-content: flex-end", css)

    def test_authenticated_reading_sessions_all_empty_state(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        self.client.force_login(self.user)
        response = self.client.get("/reading/sessions/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No reading sessions yet.")

    def test_authenticated_session_marginalia_returns_200_and_has_containers(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        book = create_file_backed_book(title="B1").book
        session = ReadingSession.objects.create(user=self.user, book=book, name="Mine")

        self.client.force_login(self.user)
        response = self.client.get(f"/reading/sessions/books/{book.id}/{session.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(
            response,
            '<a class="breadcrumbs__link" href="/reading/sessions/">My Marginalia</a>',
            html=False,
        )
        self.assertContains(
            response,
            '<a class="breadcrumbs__link" href="/reading/sessions/?view=book">Browse by Book</a>',
            html=False,
        )
        self.assertContains(
            response,
            f'<a class="breadcrumbs__link" href="/reading/sessions/books/{book.id}/">Book</a>',
            html=False,
        )
        self.assertContains(response, 'aria-current="page">Session</li>', html=False)
        self.assertNotContains(response, "Back to Dashboard")
        self.assertContains(response, f'data-book-id="{book.id}"')
        self.assertContains(response, f'data-session-id="{session.id}"')
        self.assertContains(response, 'id="reading-activity-status"')
        self.assertContains(response, 'id="reading-activity-error"')
        self.assertContains(response, 'id="reading-activity-cover"')
        self.assertContains(response, 'id="reading-activity-book-meta"')
        self.assertContains(response, 'id="reading-activity-session-context"')
        self.assertContains(response, 'id="reading-activity-session-display"')
        self.assertContains(response, 'id="reading-activity-session-edit"')
        self.assertContains(response, 'class="material-symbols-outlined"')
        self.assertContains(response, 'id="reading-activity-session-edit-form"')
        self.assertContains(response, 'id="reading-activity-session-cancel"')
        self.assertContains(response, 'id="reading-activity-session-close"')
        self.assertContains(response, 'id="reading-activity-session-close-status"')
        self.assertContains(response, "Close session")
        self.assertContains(response, 'id="reading-activity-session"')
        self.assertContains(response, 'id="reading-activity-progress"')
        self.assertContains(response, 'id="reading-activity-annotations"')
        self.assertContains(response, f"/reading/sessions/books/{book.id}/")
        self.assertNotContains(
            response,
            f"/api/v1/reading/export/books/{book.id}/{session.id}/",
        )
        self.assertNotContains(response, "Export this session")

    def test_session_marginalia_404s_for_other_users_session(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        other = User.objects.create_user(username="u2", email="u2@example.com", password="pw")
        book = create_file_backed_book(title="B1").book
        session = ReadingSession.objects.create(user=other, book=book, name="Other")

        self.client.force_login(self.user)
        response = self.client.get(f"/reading/sessions/books/{book.id}/{session.id}/", follow=False)
        self.assertEqual(response.status_code, 404)

    def test_session_marginalia_404s_when_book_id_does_not_match(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        book = create_file_backed_book(title="B1").book
        other_book = create_file_backed_book(title="B2").book
        session = ReadingSession.objects.create(user=self.user, book=book, name="Mine")

        self.client.force_login(self.user)
        response = self.client.get(f"/reading/sessions/books/{other_book.id}/{session.id}/", follow=False)
        self.assertEqual(response.status_code, 404)
