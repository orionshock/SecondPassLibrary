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
        self.assertIn("[All Sessions]", text)
