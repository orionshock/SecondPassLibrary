from __future__ import annotations

from typing import Any, cast

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from reading.models import Annotation, ReadingSession
from tests.reading.utils import IsolatedUserdataMixin
from tests.reading.imports.helpers import MarginaliaImportFixtureMixin


User = get_user_model()

class MarginaliaImportApplyApiTests(MarginaliaImportFixtureMixin, IsolatedUserdataMixin, APITestCase):
    def setUp(self):
        self.set_up_import_books()

    def _url(self):
        return "/api/v1/reading/import/apply/"

    def test_apply_with_selection_imports_only_selected_sessions_with_overrides(self):
        payload = self.marginalia_payload()
        second = dict(payload["books"][0]["sessions"][0])
        second["export_session_id"] = "session-2"
        second["name"] = "Skipped"
        payload["books"][0]["sessions"].append(second)
        selection = {
            "books": [
                {
                    "source": payload["books"][0]["source"],
                    "sessions": [
                        {
                            "export_session_id": "session-1",
                            "selected": True,
                            "name": "  Custom import name  ",
                            "notes": "  Custom notes  ",
                        },
                        {"export_session_id": "session-2", "selected": False},
                    ],
                }
            ]
        }

        self.client.force_login(self.user)
        r = cast(Any, self.post_apply_payload(payload, selection=selection))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["summary"]["sessions_created"], 1)
        session = ReadingSession.objects.get()
        self.assertEqual(session.name, "Custom import name")
        self.assertEqual(session.notes, "Custom notes")
        self.assertEqual(Annotation.objects.count(), 3)

    def test_apply_malformed_selection_returns_400_and_no_writes(self):
        self.client.force_login(self.user)
        r = cast(Any, self.post_apply_payload(self.marginalia_payload(), selection="{not-json"))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r.data["applied"])
        self.assertIn("selection", r.data["errors"][0]["path"])
        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(Annotation.objects.count(), 0)

    def test_apply_nonexistent_selected_session_returns_400_and_no_writes(self):
        payload = self.marginalia_payload()
        selection = {
            "books": [
                {
                    "source": payload["books"][0]["source"],
                    "sessions": [{"export_session_id": "missing", "selected": True}],
                }
            ]
        }

        self.client.force_login(self.user)
        r = cast(Any, self.post_apply_payload(payload, selection=selection))

        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r.data["applied"])
        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(Annotation.objects.count(), 0)

    def test_apply_selected_unmatched_book_returns_400_and_no_writes(self):
        payload = self.marginalia_payload(checksum="0" * 64, title="Missing Book")
        selection = {
            "books": [
                {
                    "source": payload["books"][0]["source"],
                    "sessions": [{"export_session_id": "session-1", "selected": True}],
                }
            ]
        }

        self.client.force_login(self.user)
        r = cast(Any, self.post_apply_payload(payload, selection=selection))

        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r.data["applied"])
        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(Annotation.objects.count(), 0)
