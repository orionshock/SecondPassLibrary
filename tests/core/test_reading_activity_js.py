from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import TestCase


class ReadingActivityJsRenderingTest(TestCase):
    def _read_js(self) -> str:
        js_path = (
            Path(settings.BASE_DIR)
            / "web"
            / "static"
            / "web"
            / "js"
            / "reading"
            / "activity.js"
        )
        return js_path.read_text(encoding="utf-8")

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

        self.assertIn("sessionIsWritable()", text)
        self.assertIn('sessionStatus === "active" && sessionIsActive === true', text)
        self.assertIn("visible(sessionCloseBtn, !!sessionId && sessionIsWritable())", text)
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
