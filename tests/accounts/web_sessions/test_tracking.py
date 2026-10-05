from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import DatabaseError
from django.test import TestCase

from accounts.models import UserWebSession
from accounts.web_session_tracking import track_web_session


class WebSessionTrackingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="tracked")
        cls.other_user = get_user_model().objects.create_user(username="reassigned")

    def setUp(self):
        self.observed_at = datetime(2026, 10, 5, tzinfo=UTC)
        self.facts = {
            "session_key": "existing-browser-session",
            "user_id": self.user.pk,
            "user_agent": "Browser",
            "ip_address": "203.0.113.10",
        }

    def track(self, *, at=None, **changes):
        with patch("accounts.web_session_tracking.timezone.now", return_value=at or self.observed_at):
            track_web_session(**(self.facts | changes))

    def test_creates_tracking_from_observed_facts_without_creating_auth_session(self):
        with self.assertNumQueries(4):
            self.track()

        tracked = UserWebSession.objects.get(session_key=self.facts["session_key"])
        self.assertEqual(tracked.user_id, self.user.pk)
        self.assertEqual(tracked.user_agent, self.facts["user_agent"])
        self.assertEqual(tracked.ip_address, self.facts["ip_address"])
        self.assertEqual(tracked.created_at, self.observed_at)
        self.assertEqual(tracked.updated_at, self.observed_at)
        self.assertFalse(Session.objects.exists())

    def test_unchanged_session_writes_only_after_strict_sixty_second_interval(self):
        self.track()
        for seconds in (0, 59, 60, 61):
            with self.subTest(seconds=seconds):
                now = self.observed_at + timedelta(seconds=seconds)
                with self.assertNumQueries(1 if seconds <= 60 else 2):
                    self.track(at=now)
                tracked = UserWebSession.objects.get(session_key=self.facts["session_key"])
                self.assertEqual(tracked.updated_at, self.observed_at if seconds <= 60 else now)
                self.assertEqual(tracked.created_at, self.observed_at)

    def test_owner_change_updates_immediately_without_loading_the_user(self):
        self.track()
        now = self.observed_at + timedelta(seconds=10)
        with self.assertNumQueries(2):
            self.track(at=now, user_id=self.other_user.pk)

        tracked = UserWebSession.objects.get(session_key=self.facts["session_key"])
        self.assertEqual(tracked.user_id, self.other_user.pk)
        self.assertEqual(tracked.user_agent, self.facts["user_agent"])
        self.assertEqual(tracked.ip_address, self.facts["ip_address"])
        self.assertEqual(tracked.updated_at, now)
        self.assertEqual(tracked.created_at, self.observed_at)
        self.assertEqual(UserWebSession.objects.count(), 1)

    def test_metadata_changes_bypass_throttle_and_preserve_other_facts(self):
        for index, change in enumerate((
            {"user_agent": "New Browser"},
            {"ip_address": "203.0.113.11"},
            {"ip_address": None},
            {"user_agent": "", "ip_address": None},
        )):
            with self.subTest(change=change):
                key = f"metadata-session-{index}"
                self.track(session_key=key)
                now = self.observed_at + timedelta(seconds=10)
                with self.assertNumQueries(2):
                    self.track(at=now, session_key=key, **change)
                tracked = UserWebSession.objects.get(session_key=key)
                expected = self.facts | change
                self.assertEqual(tracked.user_id, self.user.pk)
                self.assertEqual(tracked.user_agent, expected["user_agent"])
                self.assertEqual(tracked.ip_address, expected["ip_address"])
                self.assertEqual(tracked.updated_at, now)

    def test_unchanged_empty_metadata_does_not_write(self):
        self.track(user_agent="", ip_address=None)
        with self.assertNumQueries(1):
            self.track(user_agent="", ip_address=None)

    def test_persistence_failure_reaches_the_best_effort_caller(self):
        failure = DatabaseError("tracking unavailable")
        with (
            patch("accounts.web_session_tracking.UserWebSession.objects.get_or_create", side_effect=failure),
            self.assertRaises(DatabaseError) as raised,
        ):
            self.track()
        self.assertIs(raised.exception, failure)
