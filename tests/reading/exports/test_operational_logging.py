from __future__ import annotations

from rest_framework.test import APITestCase

from tests.reading.exports.helpers import (
    book_selection,
    selected_export_payload,
    session_selection,
    AllExportFixtureMixin,
    SelectedExportFixtureMixin,
)
from tests.utils.responses import assert_response


class MarginaliaExportOperationalLoggingTests(
    AllExportFixtureMixin,
    SelectedExportFixtureMixin,
    APITestCase,
):
    def test_successful_all_scope_export_logs_safe_info_summary(self):
        self.set_up_all_export_world()
        self.client.force_login(self.user)

        with self.assertLogs("reading.exports.services", level="INFO") as logs:
            with self.captureOnCommitCallbacks(execute=True):
                response = assert_response(self.client.get("/api/v1/reading/export/"))

        output = logs.output[0]
        self.assertEqual(response.status_code, 200)
        self.assertIn("Marginalia export completed", output)
        self.assertIn(str(self.user.profile.pk), output)
        self.assertIn("scope=all", output)
        self.assertIn("books=2", output)
        self.assertIn("sessions=2", output)
        self.assertIn("annotations=1", output)
        self.assertNotIn("Alpha Book", output)
        self.assertNotIn("Alpha session", output)
        self.assertNotIn("alpha quote", output)
        self.assertNotIn("epubcfi", output)
        self.assertNotIn(self.book1.checksum, output)

    def test_successful_selected_scope_export_logs_safe_info_summary(self):
        self.set_up_selected_export_world()
        self.client.force_login(self.user)

        with self.assertLogs("reading.exports.services", level="INFO") as logs:
            with self.captureOnCommitCallbacks(execute=True):
                response = assert_response(
                    self.client.post(
                        "/api/v1/reading/export/",
                        selected_export_payload(
                            session_selection(self.book, self.session2),
                            book_selection(self.other_book, "all"),
                        ),
                        format="json",
                    )
                )

        output = logs.output[0]
        self.assertEqual(response.status_code, 200)
        self.assertIn("scope=selected", output)
        self.assertIn("books=2", output)
        self.assertIn("sessions=2", output)
        self.assertIn("annotations=1", output)
        self.assertNotIn("Selected Export", output)
        self.assertNotIn("Second", output)
        self.assertNotIn("epubcfi", output)
        self.assertNotIn(self.book.checksum, output)
