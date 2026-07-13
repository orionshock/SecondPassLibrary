"""Tests for My Marginalia session list pages."""
from pathlib import Path

from accounts.services import get_or_create_profile
from accounts.models import UserProfile
from django.contrib.auth import get_user_model
from library.groups.memberships import ensure_user_public_membership
from library.groups.book_assignments import add_book_to_group
from library.models import LibraryGroup, LibraryGroupMembership
from reading.models import ReadingSession
from tests.core.product_ui.css import product_ui_css_text
from tests.core.product_ui.helpers import ProductUiTestCase
from tests.utils.books import create_file_backed_book


User = get_user_model()

class ProductUiReadingSessionsTests(ProductUiTestCase):
    """Test reading sessions, import/export pages."""

    def _create_hidden_owned_session(self, *, name="Hidden pass"):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])
        ensure_user_public_membership(user=self.bootstrap_owner)
        ensure_user_public_membership(user=self.user)

        hidden_group = LibraryGroup.objects.create(name="Hidden")
        other = User.objects.create_user(username="hidden-owner", email="h@example.com")
        LibraryGroupMembership.objects.create(user=other, group=hidden_group)
        book = create_file_backed_book(title="Private Book", assign_public=False).book
        add_book_to_group(actor=self.bootstrap_owner, book=book, group=hidden_group)
        session = ReadingSession.objects.create(user=self.user, book=book, name=name)
        return book, session

    def test_unauthenticated_reading_sessions_all_redirects_to_login(self):
        response = self.client.get("/reading/sessions/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/reading/sessions/")

    def test_authenticated_reading_sessions_empty_state(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        book = create_file_backed_book(title="B1").book

        self.client.force_login(self.user)
        response = self.client.get(f"/reading/sessions/books/{book.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No sessions yet for this book.")

    def test_authenticated_reading_sessions_all_scopes_to_user_and_visible_book_metadata(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        other = User.objects.create_user(username="u2", email="u2@example.com", password="pw")

        book = create_file_backed_book(title="B1").book
        mine = ReadingSession.objects.create(
            user=self.user,
            book=book,
            name="Mine",
            status=ReadingSession.STATUS_COMPLETED,
            is_active=False,
        )
        unnamed = ReadingSession.objects.create(user=self.user, book=book, name="")
        others = ReadingSession.objects.create(user=other, book=book, name="Other user")
        unnamed_suffix = str(unnamed.id)[-8:]

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
        self.assertContains(response, "<title>My Marginalia -", html=False)
        self.assertNotContains(response, 'id="reading-sessions-all-title">Sessions</h1>')
        self.assertNotContains(response, "<title>Reading Sessions", html=False)
        self.assertContains(response, 'id="reading-sessions-subtitle"')
        self.assertContains(response, 'id="reading-sessions-actions"')
        self.assertContains(response, 'href="/reading/import/"')
        self.assertContains(response, 'href="/reading/export/"')
        self.assertContains(
            response,
            '<span class="material-symbols-outlined" aria-hidden="true">upload</span>',
            html=False,
        )
        self.assertContains(
            response,
            '<span class="material-symbols-outlined" aria-hidden="true">download</span>',
            html=False,
        )
        self.assertContains(response, "<span>Import</span>", html=False)
        self.assertContains(response, "<span>Export</span>", html=False)
        markup = response.content.decode()
        self.assertLess(
            markup.index('id="reading-sessions-actions"'),
            markup.index('id="reading-sessions-controls"'),
        )
        self.assertLess(
            markup.index('id="reading-sessions-actions"'),
            markup.index('id="reading-sessions-search-form"'),
        )
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
        self.assertContains(response, "Unnamed session")
        self.assertContains(response, unnamed_suffix)
        # Other user's session not shown.
        self.assertNotContains(response, str(others.id))

        # Selectable card text is separate from explicit session/book links.
        self.assertContains(response, f"/reading/sessions/books/{book.id}/{mine.id}/")
        self.assertContains(response, 'class="card sessions-row sessions-card"')
        self.assertContains(
            response,
            f'data-session-url="/reading/sessions/books/{book.id}/{mine.id}/"',
        )
        self.assertContains(response, 'class="sessions-card__cover-link"')
        self.assertContains(response, 'class="sessions-card__title"')
        self.assertNotContains(response, 'class="muted sessions-row__id"')
        self.assertContains(response, 'aria-label="Open session"')
        self.assertContains(response, 'aria-label="View sessions for this book"')
        self.assertNotContains(response, 'title="Open session"')
        self.assertNotContains(response, ">article<")
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

    def test_authenticated_reading_sessions_all_includes_owned_session_after_book_access_lost(self):
        book, session = self._create_hidden_owned_session()

        self.client.force_login(self.user)
        response = self.client.get("/reading/sessions/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(session.id))
        self.assertContains(response, "Hidden pass")
        self.assertContains(response, "Book unavailable")
        self.assertNotContains(response, "Private Book")
        self.assertContains(response, f"/reading/sessions/books/{book.id}/{session.id}/")
        self.assertNotContains(response, f'href="/reading/sessions/books/{book.id}/"')

    def test_authenticated_reading_session_marginalia_allows_owned_hidden_session(self):
        book, session = self._create_hidden_owned_session()

        self.client.force_login(self.user)
        response = self.client.get(f"/reading/sessions/books/{book.id}/{session.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-book-id="{book.id}"')
        self.assertContains(response, f'data-session-id="{session.id}"')
        self.assertNotContains(response, f'href="/reading/sessions/books/{book.id}/"')

    def test_authenticated_reading_book_sessions_canonical_still_404s_for_hidden_book(self):
        book, _session = self._create_hidden_owned_session()

        self.client.force_login(self.user)
        response = self.client.get(f"/reading/sessions/books/{book.id}/", follow=False)

        self.assertEqual(response.status_code, 404)

    def test_reading_sessions_js_wires_filters_search_page_size_and_book_context(self):
        js = Path("web/static/web/js/reading/sessions.js").read_text(encoding="utf-8")
        main_js = Path("web/static/web/js/main.js").read_text(encoding="utf-8")
        css = product_ui_css_text()

        self.assertIn("const DEFAULT_PAGE_SIZE = 10", js)
        self.assertIn('from "../ui/breadcrumbs.js"', js)
        self.assertIn("function syncSessionsBreadcrumb", js)
        self.assertIn("function sessionsHeading", js)
        self.assertIn('state.view === "book" ? "Marginalia by Book" : "Marginalia by Session"', js)
        self.assertIn("titleEl.textContent = sessionsHeading(state)", js)
        self.assertIn("document.title = sessionsHeading(state)", js)
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
        self.assertIn("Marginalia for ${String(book.title)}", js)
        self.assertIn("sessionCardTitle(session, bookTitle)", js)
        self.assertIn("appendSeparatedParts", js)
        self.assertIn('el("span", "metadata-piece", part)', js)
        self.assertIn('el("div", "card sessions-row sessions-card")', js)
        self.assertIn("card.dataset.sessionUrl = marginaliaHref", js)
        self.assertIn("const canOpen = !!(session && session.can_open)", js)
        self.assertIn('String((book && book.title) || "Book unavailable")', js)
        self.assertIn("if (canOpen)", js)
        self.assertIn('el("a", "sessions-card__cover-link")', js)
        self.assertIn('el("a", "sessions-card__title"', js)
        self.assertIn('`/reading/sessions/books/${encodeURIComponent(bookId)}/`', js)
        self.assertNotIn("function libraryContextLink", js)
        self.assertNotIn('el("a", "context-switch-link")', js)
        self.assertNotIn('`/library/books/${encodeURIComponent(bookId)}/`', js)
        self.assertNotIn('"multiple_stop"', js)
        self.assertNotIn("bindCardInteraction", js)
        self.assertNotIn("window.location.assign", js)
        self.assertNotIn('card.setAttribute("role", "link")', js)
        self.assertNotIn("card.tabIndex", js)
        self.assertIn('label: "View sessions for this book"', js)
        self.assertNotIn('icon: "article"', js)
        self.assertIn('icon: "auto_stories"', js)
        self.assertIn("bookSessionsHref", js)
        self.assertIn("groupSessionsByBook", js)
        self.assertIn("renderBookGroup", js)
        self.assertIn('el("a",', js)
        self.assertIn("group.dataset.bookSessionsUrl = bookSessionsHref", js)
        self.assertIn("function isInteractiveElement", js)
        self.assertIn('element.closest("a, button, input, select, textarea, label, summary, details")', js)
        self.assertIn('source.closest("[data-session-url], [data-book-sessions-url]")', js)
        self.assertIn('card.getAttribute("data-session-url")', js)
        self.assertIn("window.location.href = url", js)
        self.assertIn('el(canOpen ? "a" : "div", "sessions-book-group__title", bookTitle)', js)
        self.assertNotIn('el("div", "book-title-with-action")', js)
        self.assertIn("coverLink.href = bookSessionsHref", js)
        self.assertIn("titleLink.href = bookSessionsHref", js)
        self.assertIn("titleLink.href = marginaliaHref", js)
        self.assertIn('state.view === "book"', js)
        self.assertIn("Unnamed session \\u00b7 ${id.slice(-8)}", js)
        self.assertNotIn('el("div", "muted sessions-row__id", sessionId)', js)
        self.assertIn('session && session.is_active ? "Active" : "Closed"', js)
        self.assertIn("first && first.filtered_book_session_count", js)
        self.assertIn('`${sessionCount} session${sessionCount === 1 ? "" : "s"}`', js)
        self.assertIn(": sessions.length", js)
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
        self.assertNotIn("/library/authors/", js)
        self.assertNotIn("/library/series/", js)
        self.assertIn('import("./reading/sessions.js")', main_js)
        self.assertIn('initExportName: "initReadingSessions"', main_js)
        self.assertIn(".sessions-controls .sessions-status-filters", css)
        self.assertIn("border-bottom: 0", css)
        self.assertIn(".metadata-piece + .metadata-piece::before", css)
        self.assertIn('.meta-item + .meta-item::before', css)
        self.assertIn(r'content: "\00b7"', css)
        self.assertIn(".library-context-row", css)
        self.assertIn(".library-context-action", css)
        self.assertIn("grid-template-columns: minmax(0, 1fr) auto", css)
        self.assertIn("gap: 14px", css)
        self.assertIn("align-items: center", css)
        self.assertIn("white-space: nowrap", css)
        self.assertIn("text-align: right", css)
        self.assertIn(".sessions-view-bar > .sessions-controls__page-size", css)
        self.assertIn("justify-content: flex-end", css)
        self.assertIn(".sessions-card[data-session-url]", css)

    def test_authenticated_reading_sessions_all_empty_state(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        self.client.force_login(self.user)
        response = self.client.get("/reading/sessions/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No reading sessions yet.")
