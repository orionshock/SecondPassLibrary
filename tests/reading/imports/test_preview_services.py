from __future__ import annotations

import json
from copy import deepcopy

from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.test import APITestCase

from reading.models import Annotation, ReadingSession
from tests.testenv.filesystem import IsolatedUserdataMixin
from tests.reading.imports.helpers import MarginaliaImportFixtureMixin
from tests.utils.responses import assert_response


User = get_user_model()


class MarginaliaImportPreviewApiTests(
    MarginaliaImportFixtureMixin, IsolatedUserdataMixin, APITestCase
):
    def setUp(self):
        self.set_up_import_books()

    def _url(self):
        return "/api/v1/reading/import/preview/"

    def test_valid_export_returns_summary_counts_and_file_hash_match(self):
        self.client.force_login(self.user)
        r = assert_response(
            self.post_preview_payload(self.preview_marginalia_payload())
        )

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data["valid"])
        self.assertRegex(r.data["import_token"], r"^[A-Za-z0-9_-]{32,128}$")
        self.assertEqual(r.data["unmatched_entries"], 0)
        self.assertNotIn("unmatched_download_url", r.data)
        self.assertTrue(r.data["can_apply"])
        self.assertEqual(r.data["schema_version"], "0.1.0")
        self.assertEqual(r.data["scope"]["type"], "book")
        self.assertEqual(
            r.data["summary"], {"books": 1, "sessions": 1, "annotations": 3}
        )
        self.assertEqual(
            r.data["apply_plan"],
            {
                "matched_books": 1,
                "skipped_books": 0,
                "sessions_to_create": 1,
                "annotations_to_create": 3,
                "bookmarks_to_create": 1,
                "highlights_to_create": 2,
                "commented_highlights_to_create": 1,
                "active_sessions_will_import_as_historical": 0,
                "possible_duplicate_sessions": 0,
            },
        )

        book = r.data["books"][0]
        self.assertEqual(book["session_count"], 1)
        self.assertEqual(book["annotation_count"], 3)
        self.assertEqual(book["bookmark_count"], 1)
        self.assertEqual(book["highlight_count"], 2)
        self.assertEqual(book["commented_highlight_count"], 1)
        self.assertEqual(book["match"]["status"], "matched")
        self.assertEqual(book["match"]["method"], "file_hash")
        self.assertEqual(book["match"]["book_title"], "Visible Match")
        self.assertTrue(book["will_import"])
        self.assertIsNone(book["skip_reason"])
        self.assertEqual(len(book["sessions"]), 1)
        session = book["sessions"][0]
        self.assertEqual(session["export_session_id"], "session-1")
        self.assertEqual(session["name"], "Imported session")
        self.assertEqual(session["notes"], "")
        self.assertEqual(session["status"], "completed")
        self.assertEqual(session["annotation_count"], 3)
        self.assertEqual(session["bookmark_count"], 1)
        self.assertEqual(session["highlight_count"], 2)
        self.assertEqual(session["commented_highlight_count"], 1)
        self.assertTrue(session["will_import"])
        self.assertFalse(session["active_will_import_as_historical"])

    def test_preview_does_not_create_sessions_or_annotations(self):
        self.client.force_login(self.user)
        before_sessions = ReadingSession.objects.count()
        before_annotations = Annotation.objects.count()

        r = self.post_preview_payload(self.preview_marginalia_payload())

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(ReadingSession.objects.count(), before_sessions)
        self.assertEqual(Annotation.objects.count(), before_annotations)

    def test_matching_only_uses_visible_books(self):
        self.client.force_login(self.user)
        r = assert_response(
            self.post_preview_payload(
                self.preview_marginalia_payload(
                    file_hash=self.hidden.file.checksum, title="Hidden Match"
                )
            ),
        )

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["books"][0]["match"]["status"], "unmatched")
        self.assertIsNone(r.data["books"][0]["match"]["book_title"])

    def test_unmatched_book_reported(self):
        self.client.force_login(self.user)
        payload = self.preview_marginalia_payload(
            file_hash="0" * 64, title="Missing Book", authors=["Nobody"]
        )

        r = assert_response(self.post_preview_payload(payload))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertFalse(r.data["can_apply"])
        self.assertEqual(r.data["apply_plan"]["matched_books"], 0)
        self.assertEqual(r.data["apply_plan"]["skipped_books"], 1)
        self.assertEqual(r.data["apply_plan"]["sessions_to_create"], 0)
        self.assertEqual(r.data["books"][0]["match"]["status"], "unmatched")
        self.assertFalse(r.data["books"][0]["will_import"])
        self.assertEqual(r.data["books"][0]["skip_reason"], "unmatched_book")
        self.assertFalse(r.data["books"][0]["sessions"][0]["will_import"])
        self.assertIn("No visible local book matched", r.data["books"][0]["warning"])
        self.assertEqual(
            r.data["warnings"],
            [
                "1 export book did not match by file hash. "
                "It can be downloaded for Reader-assisted import."
            ],
        )
        self.assertEqual(r.data["unmatched_entries"], 1)
        self.assertIn(
            "/api/v1/reading/import/unmatched/?import_token=",
            r.data["unmatched_download_url"],
        )

    def test_multiple_unmatched_books_have_one_summary_warning(self):
        self.client.force_login(self.user)
        payload = self.preview_marginalia_payload(session_status="active")
        first_unmatched = deepcopy(payload["books"][0])
        first_unmatched.update(
            {
                "title": "Missing One",
                "authors": ["Missing Author One"],
                "isbn": "",
                "source": "book:sha256:" + ("1" * 64),
                "file_hash": "sha256:" + ("1" * 64),
            }
        )
        second_unmatched = deepcopy(payload["books"][0])
        second_unmatched.update(
            {
                "title": "Missing Two",
                "authors": ["Missing Author Two"],
                "isbn": "",
                "source": "book:sha256:" + ("2" * 64),
                "file_hash": "sha256:" + ("2" * 64),
            }
        )
        payload["books"].extend([first_unmatched, second_unmatched])

        r = assert_response(self.post_preview_payload(payload))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["apply_plan"]["matched_books"], 1)
        self.assertEqual(r.data["apply_plan"]["skipped_books"], 2)
        self.assertEqual(r.data["unmatched_entries"], 2)
        self.assertIn(
            "/api/v1/reading/import/unmatched/?import_token=",
            r.data["unmatched_download_url"],
        )
        self.assertEqual(
            r.data["warnings"].count(
                "2 export books did not match by file hash. "
                "They can be downloaded for Reader-assisted import."
            ),
            1,
        )
        self.assertEqual(
            sum(
                1
                for warning in r.data["warnings"]
                if "No visible local book matched this export book" in warning
            ),
            0,
        )
        self.assertIn(
            "Active exported sessions will be imported as historical sessions, not active sessions.",
            r.data["warnings"],
        )

    def test_bad_file_hash_does_not_match_by_title_author(self):
        self.client.force_login(self.user)
        payload = self.preview_marginalia_payload(file_hash="1" * 64)
        payload["books"][0]["source"] = "book:sha256:" + ("1" * 64)
        payload["books"][0]["file_hash"] = "sha256:" + ("1" * 64)

        r = assert_response(self.post_preview_payload(payload))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["books"][0]["match"]["status"], "unmatched")
        self.assertEqual(r.data["unmatched_books"], 1)

    def test_bad_file_hash_does_not_match_by_isbn(self):
        self.visible.isbn = "9780345816023"
        self.visible.save(update_fields=["isbn", "updated_at"])
        self.client.force_login(self.user)
        payload = self.preview_marginalia_payload(
            file_hash="1" * 64, title="Different Title", authors=["Other"]
        )
        payload["books"][0]["isbn"] = "9780345816023"

        r = assert_response(self.post_preview_payload(payload))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["books"][0]["match"]["status"], "unmatched")
        self.assertEqual(r.data["unmatched_books"], 1)

    def test_matched_book_with_malformed_cfi_session_needs_reader(self):
        self.client.force_login(self.user)
        payload = self.preview_marginalia_payload()
        invalid = deepcopy(payload["books"][0]["sessions"][0])
        invalid["export_session_id"] = "session-bad"
        invalid["name"] = "Bad locator"
        invalid["annotations"][0]["target"]["selector"]["value"] = "not-a-cfi"
        payload["books"][0]["sessions"].append(invalid)

        r = assert_response(self.post_preview_payload(payload))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data["can_apply"])
        self.assertEqual(r.data["apply_plan"]["matched_books"], 1)
        self.assertEqual(r.data["apply_plan"]["skipped_books"], 0)
        self.assertEqual(r.data["apply_plan"]["sessions_to_create"], 1)
        self.assertEqual(r.data["unmatched_books"], 0)
        self.assertEqual(r.data["unmatched_sessions"], 1)
        sessions = r.data["books"][0]["sessions"]
        self.assertTrue(sessions[0]["will_import"])
        self.assertFalse(sessions[0]["needs_reader"])
        self.assertFalse(sessions[1]["will_import"])
        self.assertTrue(sessions[1]["needs_reader"])
        self.assertEqual(
            sessions[1]["warning"], "Malformed EPUB CFI locator. Needs Reader."
        )
        self.assertIn(
            "1 session has malformed locators and needs Reader-assisted import.",
            r.data["warnings"],
        )
        unmatched = json.loads(
            self.client.get(r.data["unmatched_download_url"]).content.decode("utf-8")
        )
        self.assertEqual(
            [book["title"] for book in unmatched["books"]], ["Visible Match"]
        )
        self.assertEqual(
            [
                session["export_session_id"]
                for session in unmatched["books"][0]["sessions"]
            ],
            ["session-bad"],
        )

    def test_matched_book_with_malformed_progress_cfi_session_needs_reader(self):
        self.client.force_login(self.user)
        payload = self.preview_marginalia_payload()
        payload["books"][0]["sessions"][0]["progress"] = {
            "current_location": {"cfi": "not-a-cfi"},
            "progression": 0.5,
            "profile_version": "0.1.0",
            "updated_at": "2026-06-01T12:00:00+00:00",
        }

        r = assert_response(self.post_preview_payload(payload))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertFalse(r.data["can_apply"])
        self.assertEqual(r.data["apply_plan"]["sessions_to_create"], 0)
        self.assertEqual(r.data["unmatched_sessions"], 1)
        self.assertFalse(r.data["books"][0]["sessions"][0]["will_import"])
        self.assertTrue(r.data["books"][0]["sessions"][0]["needs_reader"])
        unmatched = json.loads(
            self.client.get(r.data["unmatched_download_url"]).content.decode("utf-8")
        )
        self.assertEqual(
            unmatched["books"][0]["sessions"][0]["progress"]["current_location"]["cfi"],
            "not-a-cfi",
        )
        self.assertEqual(
            [book["title"] for book in unmatched["books"]], ["Visible Match"]
        )
        self.assertEqual(
            [
                session["export_session_id"]
                for session in unmatched["books"][0]["sessions"]
            ],
            ["session-1"],
        )

    def test_empty_session_without_locators_remains_importable(self):
        self.client.force_login(self.user)
        payload = self.preview_marginalia_payload()
        payload["books"][0]["sessions"][0]["progress"] = None
        payload["books"][0]["sessions"][0]["annotations"] = []

        r = assert_response(self.post_preview_payload(payload))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data["books"][0]["sessions"][0]["will_import"])
        self.assertFalse(r.data["books"][0]["sessions"][0]["needs_reader"])

    def test_active_exported_sessions_warn_but_can_apply(self):
        self.client.force_login(self.user)
        payload = self.preview_marginalia_payload(session_status="active")

        r = assert_response(self.post_preview_payload(payload))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data["can_apply"])
        self.assertEqual(
            r.data["apply_plan"]["active_sessions_will_import_as_historical"], 1
        )
        self.assertEqual(
            r.data["books"][0]["active_sessions_will_import_as_historical"], 1
        )
        self.assertIn("not active sessions", r.data["warnings"][0])

    def test_possible_duplicate_warning_does_not_block_apply(self):
        session = ReadingSession.objects.create(
            user=self.user,
            book=self.visible,
            name="Imported session",
            status=ReadingSession.STATUS_COMPLETED,
            completed_at=parse_datetime("2026-06-02T12:00:00+00:00"),
            is_active=False,
        )
        started_at = parse_datetime("2026-06-01T12:00:00+00:00")
        assert started_at is not None
        session.started_at = started_at
        session.save(update_fields=["started_at", "updated_at"])

        self.client.force_login(self.user)
        r = assert_response(
            self.post_preview_payload(self.preview_marginalia_payload())
        )

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data["can_apply"])
        self.assertEqual(r.data["apply_plan"]["possible_duplicate_sessions"], 1)
        self.assertEqual(r.data["books"][0]["possible_duplicate_sessions"], 1)
        self.assertIn("Possible duplicate sessions", r.data["warnings"][0])
