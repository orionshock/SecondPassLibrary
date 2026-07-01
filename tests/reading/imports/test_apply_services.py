from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, cast
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.client_api import hash_client_secret
from accounts.models import UserClientSession
from reading.import_apply_services import apply_marginalia_import
from reading.import_services import preview_marginalia_import
from reading.import_staging import stage_marginalia_import, staged_import_path
from reading.models import Annotation, ReadingSession
from tests.reading.utils import IsolatedUserdataMixin
from tests.reading.imports.helpers import MarginaliaImportFixtureMixin
from tests.utils.books import create_file_backed_book


User = get_user_model()

class MarginaliaImportApplyApiTests(MarginaliaImportFixtureMixin, IsolatedUserdataMixin, APITestCase):
    def setUp(self):
        self.set_up_import_books()

    def _url(self):
        return "/api/v1/reading/import/apply/"

    def test_apply_creates_sessions_and_annotations_for_matched_books(self):
        self.client.force_login(self.user)
        r = cast(Any, self.post_apply_payload(self.marginalia_payload()))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(
            r.data["summary"],
            {
                "books_matched": 1,
                "books_skipped": 0,
                "sessions_created": 1,
                "annotations_created": 3,
                "bookmarks_created": 1,
                "highlights_created": 2,
                "commented_highlights_created": 1,
            },
        )

        session = ReadingSession.objects.get()
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.book, self.visible)
        self.assertEqual(session.name, "Imported session")
        self.assertEqual(session.notes, "session notes")
        self.assertEqual(session.status, ReadingSession.STATUS_COMPLETED)
        self.assertFalse(session.is_active)

        bookmark = Annotation.objects.get(anchor_kind=Annotation.ANCHOR_KIND_BOOKMARK)
        self.assertEqual(bookmark.selector_value, "epubcfi(/6/2)")
        self.assertEqual(bookmark.highlight_text, "")

        highlight = Annotation.objects.get(highlight_text="plain highlight")
        self.assertEqual(highlight.highlight_color, "green")
        self.assertEqual(highlight.quote_prefix, "before ")
        self.assertEqual(highlight.quote_suffix, " after")

        commented = Annotation.objects.get(comment_text="note")
        self.assertEqual(commented.highlight_text, "commented highlight")

    def test_apply_summary_matches_preview_plan_counts(self):
        payload = self.marginalia_payload()
        preview = preview_marginalia_import(user=self.user, payload=payload)

        self.client.force_login(self.user)
        r = cast(Any, self.post_apply_payload(payload))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["summary"]["books_matched"], preview["apply_plan"]["matched_books"])
        self.assertEqual(r.data["summary"]["books_skipped"], preview["apply_plan"]["skipped_books"])
        self.assertEqual(
            r.data["summary"]["sessions_created"],
            preview["apply_plan"]["sessions_to_create"],
        )
        self.assertEqual(
            r.data["summary"]["annotations_created"],
            preview["apply_plan"]["annotations_to_create"],
        )

    def test_apply_skips_malformed_locator_sessions(self):
        self.client.force_login(self.user)
        payload = self.marginalia_payload()
        invalid = json.loads(json.dumps(payload["books"][0]["sessions"][0]))
        invalid["export_session_id"] = "session-bad"
        invalid["name"] = "Bad locator"
        invalid["annotations"][0]["target"]["selector"]["value"] = "not-a-cfi"
        payload["books"][0]["sessions"].append(invalid)

        r = cast(Any, self.post_apply_payload(payload))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["summary"]["sessions_created"], 1)
        self.assertEqual(ReadingSession.objects.filter(user=self.user).count(), 1)
        self.assertFalse(ReadingSession.objects.filter(user=self.user, name="Bad locator").exists())

    def test_apply_rolls_back_if_annotation_write_fails(self):
        payload = self.marginalia_payload()

        with patch("reading.import_apply_services.Annotation.objects.create") as create:
            create.side_effect = RuntimeError("simulated annotation write failure")
            with self.assertRaises(RuntimeError):
                apply_marginalia_import(user=self.user, payload=payload)

        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(Annotation.objects.count(), 0)

    def test_apply_skips_unmatched_books(self):
        self.client.force_login(self.user)
        payload = self.marginalia_payload(checksum="0" * 64, title="Missing Book")
        r = cast(Any, self.post_apply_payload(payload))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["summary"]["books_matched"], 0)
        self.assertEqual(r.data["summary"]["books_skipped"], 1)
        self.assertTrue(r.data["books"][0]["skipped"])
        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(Annotation.objects.count(), 0)

    def test_apply_active_exported_session_imports_historical(self):
        self.client.force_login(self.user)
        r = cast(Any, self.post_apply_payload(self.marginalia_payload(status_value="active")))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        session = ReadingSession.objects.get()
        self.assertEqual(session.status, ReadingSession.STATUS_COMPLETED)
        self.assertFalse(session.is_active)
        self.assertIsNotNone(session.completed_at)

    def test_apply_duplicate_looking_sessions_are_not_blocked(self):
        ReadingSession.objects.create(
            user=self.user,
            book=self.visible,
            name="Imported session",
            status=ReadingSession.STATUS_COMPLETED,
            is_active=False,
        )
        self.client.force_login(self.user)
        r = cast(Any, self.post_apply_payload(self.marginalia_payload()))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["summary"]["sessions_created"], 1)
        self.assertEqual(ReadingSession.objects.count(), 2)
