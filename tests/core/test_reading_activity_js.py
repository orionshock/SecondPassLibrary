from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import TestCase


class ReadingActivityJsRenderingTest(TestCase):
    def test_annotation_cards_do_not_render_session_id(self):
        js_path = (
            Path(settings.BASE_DIR)
            / "web"
            / "static"
            / "web"
            / "js"
            / "reading_book_activity.js"
        )
        text = js_path.read_text(encoding="utf-8")

        # The per-annotation card should not include "Session <uuid>" metadata.
        # Session context remains visible in the page header/Session section.
        self.assertNotIn("metaBits.push(`Session", text)

