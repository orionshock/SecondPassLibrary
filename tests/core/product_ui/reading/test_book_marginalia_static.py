"""Tests for My Marginalia book and session detail pages."""
from pathlib import Path

from accounts.services import get_or_create_profile
from accounts.models import UserProfile
from django.conf import settings
from django.contrib.auth import get_user_model
from library.models import Author, Series
from reading.models import ReadingSession
from django.test import TestCase
from tests.core.product_ui.helpers import ProductUiTestCase
from tests.utils.books import create_file_backed_book
from uuid import uuid4


User = get_user_model()

class ProductUiBookMarginaliaTests(ProductUiTestCase):
    """Test reading sessions, import/export pages."""

    def test_unauthenticated_reading_sessions_redirects_to_login(self):
        book_id = uuid4()
        response = self.client.get(f"/reading/sessions/books/{book_id}/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            f"/api-auth/login/?next=/reading/sessions/books/{book_id}/",
        )

    def test_authenticated_reading_sessions_scopes_to_user_and_book(self):
        # Make the user a librarian so book visibility is not dependent on group membership setup.
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        other = User.objects.create_user(
            username="u2", email="u2@example.com", password="pw"
        )

        book = create_file_backed_book(title="B1").book
        author = Author.objects.create(name="Author One")
        series = Series.objects.create(name="Series One")
        book.authors.add(author)
        book.series = series
        book.save(update_fields=["series", "updated_at"])
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
        self.assertContains(response, f"<title>Marginalia for {book.title} -", html=False)
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
        self.assertContains(response, 'class="sessions-card__title"')
        self.assertContains(response, 'class="pill sessions-card__status"')
        self.assertContains(response, "Mine")
        self.assertContains(response, "Unnamed session")
        self.assertContains(response, unnamed_suffix)
        self.assertContains(response, f"Unnamed session, {unnamed_suffix}", html=False)
        self.assertContains(response, 'class="muted sessions-card__metadata"')
        self.assertContains(response, 'class="meta-list"')
        self.assertContains(response, 'class="meta-item"')
        self.assertContains(response, "Started ")
        self.assertContains(response, "Closed")
        self.assertContains(response, "Active")
        self.assertContains(response, "0 annotations")
        self.assertNotContains(response, "Started:")
        self.assertNotContains(response, "Closed:")
        self.assertNotContains(response, "Updated:")
        self.assertNotContains(response, "Progression:")
        self.assertNotContains(response, "Progression: Not available")
        self.assertNotContains(response, "Annotations:")
        self.assertNotContains(response, "&#183;")
        self.assertNotContains(response, "&middot;")
        self.assertNotContains(response, f">{unnamed.id}<")
        self.assertNotContains(response, f"Session ID: {unnamed.id}")
        self.assertNotContains(response, "Session ID:")
        self.assertContains(response, f'href="/library/books/{book.id}/"')
        self.assertContains(response, 'class="library-context-row"')
        self.assertContains(response, 'class="library-context-action"')
        self.assertContains(response, "View book in Library")
        self.assertContains(response, f"View {book.title} in Library")
        self.assertContains(response, f'href="/library/?view=author&amp;author={author.id}"', html=False)
        self.assertContains(response, "View author in Library")
        self.assertContains(response, f"View {author.name} in Library")
        self.assertContains(response, f'href="/library/?view=series&amp;series={series.id}"', html=False)
        self.assertContains(response, "View series in Library")
        self.assertContains(response, f"View {series.name} in Library")
        self.assertNotContains(response, 'class="context-switch-link"')
        self.assertNotContains(response, "multiple_stop")
        self.assertNotContains(response, "Book details")
        self.assertNotContains(response, 'href="/library/authors/')
        self.assertNotContains(response, 'href="/library/series/')
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
        rendering_js = Path("web/static/web/js/reading/activity_rendering.js").read_text(
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
        self.assertIn("function contextRow", rendering_js)
        self.assertIn("function contextAction", rendering_js)
        self.assertIn('el("a", "library-context-action", label)', rendering_js)
        self.assertIn('el("div", "library-context-row")', rendering_js)
        self.assertIn('`/library/books/${encodeURIComponent(bookId)}/`', rendering_js)
        self.assertIn('"View book in Library"', rendering_js)
        self.assertIn("`View ${title} in Library`", rendering_js)
        self.assertIn('/library/?view=author&author=${encodeURIComponent(String(primaryAuthor.id))}', rendering_js)
        self.assertIn('"View author in Library"', rendering_js)
        self.assertIn('/library/?view=series&series=${encodeURIComponent(seriesId)}', rendering_js)
        self.assertIn('"View series in Library"', rendering_js)
        self.assertNotIn('"multiple_stop"', rendering_js)
        self.assertNotIn("/library/authors/", rendering_js)
        self.assertNotIn("/library/series/", rendering_js)

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
        self.assertContains(response, "<title>Session Marginalia -", html=False)
        self.assertNotContains(response, "<title>Reading activity", html=False)
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
        self.assertNotContains(response, "Book details")
        self.assertNotContains(response, 'id="reading-activity-book-link"')
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


class ReadingActivityJsRenderingTest(TestCase):
    """Test reading activity JavaScript rendering contracts."""

    def _read_js(self) -> str:
        js_dir = (
            Path(settings.BASE_DIR)
            / "web"
            / "static"
            / "web"
            / "js"
            / "reading"
        )
        return "\n".join(
            [
                (js_dir / "activity.js").read_text(encoding="utf-8"),
                (js_dir / "activity_actions.js").read_text(encoding="utf-8"),
                (js_dir / "activity_rendering.js").read_text(encoding="utf-8"),
            ]
        )

    def test_annotation_cards_do_not_render_session_id(self):
        text = self._read_js()

        # The per-annotation card should not include "Session <uuid>" metadata.
        # Session context remains visible in the page header/Session section.
        self.assertNotIn("metaBits.push(`Session", text)

    def test_session_edit_is_guarded_by_session_active_status(self):
        text = self._read_js()

        # Closed sessions are historical/fixed; the UI should not show the edit affordance.
        self.assertIn("session.status", text)
        self.assertIn("session.is_active", text)
        self.assertIn("canEditSessionMetadata", text)

    def test_close_session_action_is_guarded_and_posts_to_close_endpoint(self):
        text = self._read_js()

        self.assertIn("sessionIsWritable(state)", text)
        self.assertIn('state.sessionStatus === "active" && state.sessionIsActive === true', text)
        self.assertIn("visible(sessionCloseBtn, !!state.sessionId && sessionIsWritable(state))", text)
        self.assertIn("visible(sessionCloseBtn, false)", text)
        self.assertIn("/api/v1/reading/sessions/${encodeURIComponent(String(sessionId))}/close/", text)
        self.assertIn("method: \"POST\"", text)

    def test_close_session_confirm_warnings_are_present(self):
        text = self._read_js()

        self.assertIn("This session has no name. Closed sessions cannot be renamed later. Close anyway?", text)
        self.assertIn("Close this reading session? Closed sessions cannot be edited.", text)

    def test_canonical_session_marginalia_is_session_scoped(self):
        text = self._read_js()

        # The canonical page should not attempt to guess/fallback to an "active session" per book.
        self.assertNotIn("/api/v1/reading/books/", text)

        # Annotations should be scoped to the selected session id, not book-wide.
        self.assertIn("/api/v1/reading/annotations/?session_id=", text)
        self.assertNotIn("book_id=", text)

    def test_annotation_quote_and_note_use_purpose_not_order(self):
        text = self._read_js()

        self.assertIn('b.purpose === "describing"', text)
        self.assertIn('b.purpose === "commenting"', text)
        self.assertNotIn('b.purpose === "highlighting"', text)

    def test_annotation_quote_renders_before_note_and_uses_color_token_class(self):
        text = self._read_js()

        # Quote-first then note.
        self.assertIn("if (quoteText)", text)
        self.assertIn("if (noteText)", text)

        # Token is applied only via CSS class, not inline styles.
        self.assertIn("annotation-quote--${token}", text)
        self.assertNotIn(".style.", text)
        self.assertNotIn("style=", text)

    def test_bookmark_only_annotation_uses_friendly_text(self):
        text = self._read_js()

        self.assertIn('const isBookmarkOnly = motivation === "bookmarking" && !hasQuote && !hasNote', text)
        self.assertIn('"Bookmark"', text)
        self.assertIn('"Saved location"', text)
        self.assertIn('titleEl.setAttribute("title", selectorValue)', text)
        self.assertIn('locationEl.setAttribute("title", selectorValue)', text)
        self.assertIn("} else if (!quoteText && !noteText) {", text)

    def test_annotation_icons_match_reader_client_semantics(self):
        text = self._read_js()

        self.assertIn('kindIcon = "bookmark"', text)
        self.assertIn('kindIcon = "border_color"', text)
        self.assertIn('kindIcon = "chat_bubble"', text)
        self.assertIn('kindIcon = "edit_note"', text)
        self.assertNotIn("ink_highlighter", text)
        self.assertNotIn("sticky_note_2", text)
