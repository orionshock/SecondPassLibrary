from __future__ import annotations

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.models import ServerSetting
from core.server_settings import (
    MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
    MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
    SERVER_SETTINGS_CACHE_KEY,
    clear_server_settings_cache,
    set_server_setting,
)
from library.models import Book
from marginalia.annotations.maintenance import execute_deleted_annotation_cleanup
from marginalia.annotations.services import soft_delete_annotations
from marginalia.models import Annotation, ReadingSession
from maintenance.results import MaintenanceResult


User = get_user_model()


class DeletedAnnotationCleanupTests(TestCase):
    def setUp(self):
        clear_server_settings_cache()
        self.now = timezone.now()
        self.user = User.objects.create_user(username="cleanup-reader")
        self.active_session = self._session("Active Book")
        self.closed_session = self._session(
            "Closed Book", status=ReadingSession.STATUS_CLOSED
        )

    def tearDown(self):
        clear_server_settings_cache()

    def test_retention_is_session_aware_and_never_touches_live_or_unknown_age_rows(
        self,
    ):
        active_old = self._tombstone(self.active_session, "active-old", days_old=29)
        active_young = self._tombstone(self.active_session, "active-young", days_old=27)
        closed_old = self._tombstone(self.closed_session, "closed-old", days_old=8)
        closed_young = self._tombstone(self.closed_session, "closed-young", days_old=6)
        live = self._annotation(self.closed_session, "live")
        unknown_age = self._annotation(self.closed_session, "legacy", is_deleted=True)

        result = execute_deleted_annotation_cleanup(now=self.now)

        self.assertFalse(Annotation.objects.filter(pk=active_old.pk).exists())
        self.assertFalse(Annotation.objects.filter(pk=closed_old.pk).exists())
        self.assertTrue(Annotation.objects.filter(pk=active_young.pk).exists())
        self.assertTrue(Annotation.objects.filter(pk=closed_young.pk).exists())
        self.assertTrue(Annotation.objects.filter(pk=live.pk).exists())
        self.assertTrue(Annotation.objects.filter(pk=unknown_age.pk).exists())
        self.assertTrue(
            ReadingSession.objects.filter(pk=self.active_session.pk).exists()
        )
        self.assertTrue(
            ReadingSession.objects.filter(pk=self.closed_session.pk).exists()
        )
        self.assertTrue(Book.objects.filter(pk=self.active_session.book_id).exists())
        self.assertEqual(result.counts["active_candidates"], 1)
        self.assertEqual(result.counts["closed_candidates"], 1)
        self.assertEqual(result.counts["active_deleted"], 1)
        self.assertEqual(result.counts["closed_deleted"], 1)
        self.assertEqual(result.counts["total_deleted"], 2)
        self.assertEqual(result.counts["active_retention_days"], 28)
        self.assertEqual(result.counts["closed_retention_days"], 7)

    def test_closing_session_immediately_applies_closed_retention_to_tombstone_age(
        self,
    ):
        tombstone = self._tombstone(self.active_session, "ten-days", days_old=10)
        first = execute_deleted_annotation_cleanup(now=self.now)
        self.assertEqual(first.counts["total_deleted"], 0)

        ReadingSession.objects.filter(pk=self.active_session.pk).update(
            status=ReadingSession.STATUS_CLOSED,
            closed_at=self.now,
        )
        second = execute_deleted_annotation_cleanup(now=self.now)

        self.assertEqual(second.counts["closed_deleted"], 1)
        self.assertFalse(Annotation.objects.filter(pk=tombstone.pk).exists())

    def test_custom_thresholds_dry_run_and_bounded_rerun_are_safe(self):
        set_server_setting(
            key=MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
            value=2,
        )
        set_server_setting(
            key=MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
            value=3,
        )
        first = self._tombstone(self.active_session, "first", days_old=4)
        second = self._tombstone(self.closed_session, "second", days_old=4)

        preview = execute_deleted_annotation_cleanup(
            dry_run=True,
            limit=1,
            now=self.now,
        )
        self.assertEqual(preview.counts["active_retention_days"], 2)
        self.assertEqual(preview.counts["closed_retention_days"], 3)
        self.assertEqual(
            preview.counts["active_selected"] + preview.counts["closed_selected"], 1
        )
        self.assertEqual(preview.counts["deferred_by_limit"], 1)
        self.assertEqual(preview.counts["total_deleted"], 0)
        self.assertEqual(
            Annotation.objects.filter(pk__in=[first.pk, second.pk]).count(), 2
        )

        execute_deleted_annotation_cleanup(limit=1, now=self.now)
        self.assertEqual(
            Annotation.objects.filter(pk__in=[first.pk, second.pk]).count(), 1
        )
        execute_deleted_annotation_cleanup(limit=1, now=self.now)
        self.assertFalse(
            Annotation.objects.filter(pk__in=[first.pk, second.pk]).exists()
        )
        rerun = execute_deleted_annotation_cleanup(limit=1, now=self.now)
        self.assertEqual(rerun.counts["total_deleted"], 0)

    def test_each_cleanup_run_reads_current_committed_retention(self):
        set_server_setting(
            key=MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
            value=28,
        )
        set_server_setting(
            key=MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
            value=7,
        )
        cache.set(
            SERVER_SETTINGS_CACHE_KEY,
            {
                MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING: 28,
                MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING: 7,
            },
            timeout=None,
        )
        tombstone = self._tombstone(self.active_session, "fresh-policy", days_old=3)

        # Simulate the web process committing while this worker cache stays stale.
        ServerSetting.objects.filter(
            key=MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING
        ).update(value=2)
        result = execute_deleted_annotation_cleanup(now=self.now)

        self.assertEqual(result.counts["active_retention_days"], 2)
        self.assertFalse(Annotation.objects.filter(pk=tombstone.pk).exists())

    def test_invalid_policy_and_limit_are_rejected(self):
        for invalid in (-1, True, "7"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                execute_deleted_annotation_cleanup(
                    now=self.now,
                    active_retention_days=invalid,
                )
        with self.assertRaises(ValueError):
            execute_deleted_annotation_cleanup(now=self.now, limit=0)

    def test_explicit_retention_overrides_do_not_read_overridden_storage(self):
        set_server_setting(
            key=MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
            value="invalid",
        )
        set_server_setting(
            key=MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
            value="invalid",
        )

        result = execute_deleted_annotation_cleanup(
            dry_run=True,
            now=self.now,
            active_retention_days=2,
            closed_retention_days=3,
        )

        self.assertEqual(result.counts["active_retention_days"], 2)
        self.assertEqual(result.counts["closed_retention_days"], 3)

    def test_soft_delete_sets_clock_once_and_normal_edits_do_not_change_it(self):
        annotation = self._annotation(self.active_session, "lifecycle")
        self.assertIsNone(annotation.deleted_at)

        self.assertEqual(
            soft_delete_annotations(
                session=self.active_session,
                annotation_ids=[annotation.pk],
            ),
            1,
        )
        annotation.refresh_from_db()
        deleted_at = annotation.deleted_at
        self.assertIsNotNone(deleted_at)
        self.assertEqual(
            soft_delete_annotations(
                session=self.active_session,
                annotation_ids=[annotation.pk],
            ),
            0,
        )
        annotation.location_label = "Chapter 2"
        annotation.save(update_fields=["location_label", "updated_at"])
        annotation.refresh_from_db()
        self.assertEqual(annotation.deleted_at, deleted_at)

    def test_cli_uses_shared_cleanup_and_redirected_output_has_no_ansi(self):
        self._tombstone(self.closed_session, "cli", days_old=8)
        output = StringIO()

        call_command("cleanup_deleted_annotations", stdout=output)

        self.assertFalse(Annotation.objects.filter(client_id="cli").exists())
        self.assertNotIn("\x1b[", output.getvalue())

    def test_cli_passes_structured_result_to_maintenance_presenter(self):
        result = MaintenanceResult(summary="complete", counts={"total_deleted": 2})

        with (
            patch(
                "marginalia.management.commands.cleanup_deleted_annotations."
                "execute_deleted_annotation_cleanup",
                return_value=result,
            ),
            patch(
                "marginalia.management.commands.cleanup_deleted_annotations."
                "MaintenanceCliPresenter"
            ) as presenter_class,
        ):
            call_command("cleanup_deleted_annotations")

        presenter_class.return_value.result.assert_called_once_with(
            result,
            status="Succeeded",
        )

    def test_cleanup_logs_policy_and_bounded_counts_without_annotation_identity(self):
        client_id = "private-client-identity"
        self._tombstone(self.closed_session, client_id, days_old=8)

        with self.assertLogs(
            "marginalia.annotations.maintenance", level="INFO"
        ) as logs:
            execute_deleted_annotation_cleanup(now=self.now)

        joined = "\n".join(logs.output)
        self.assertIn("active_retention_days=28", joined)
        self.assertIn("closed_retention_days=7", joined)
        self.assertNotIn(client_id, joined)

    def _session(self, title, *, status=ReadingSession.STATUS_ACTIVE):
        values = {
            "user": self.user,
            "book": Book.objects.create(title=title),
            "status": status,
        }
        if status == ReadingSession.STATUS_CLOSED:
            values["closed_at"] = self.now
        return ReadingSession.objects.create(**values)

    def _annotation(self, session, client_id, *, is_deleted=False):
        return Annotation.objects.create(
            session=session,
            client_id=client_id,
            kind=Annotation.KIND_BOOKMARK,
            location=f"epubcfi(/6/{Annotation.objects.count() + 2})",
            is_deleted=is_deleted,
        )

    def _tombstone(self, session, client_id, *, days_old):
        annotation = self._annotation(session, client_id, is_deleted=True)
        Annotation.objects.filter(pk=annotation.pk).update(
            deleted_at=self.now - timedelta(days=days_old)
        )
        annotation.refresh_from_db()
        return annotation
