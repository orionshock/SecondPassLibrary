from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import TestCase


class DashboardRecentLinkTargetTest(TestCase):
    def test_dashboard_recent_reading_links_to_activity_page(self):
        js_path = (
            Path(settings.BASE_DIR)
            / "web"
            / "static"
            / "web"
            / "js"
            / "dashboard"
            / "main.js"
        )
        text = js_path.read_text(encoding="utf-8")
        self.assertIn("/reading/sessions/books/", text)
        self.assertIn("View all sessions", text)
        self.assertIn("/api/v1/reading/sessions/?page_size=10", text)
        self.assertNotIn("/api/v1/reading/sessions/recent/?limit=10", text)
