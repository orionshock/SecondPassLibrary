from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from maintenance.models import (
    MaintenanceFrequency,
    MaintenanceTaskConfig,
    MaintenanceTaskRun,
)
from maintenance.services import dispatch_due_tasks


class MaintenanceSchedulingTests(TestCase):
    def setUp(self):
        self.configuration = MaintenanceTaskConfig.objects.get(
            task_key="cleanup_client_pairing_requests"
        )

    def test_due_enabled_task_enqueues_once_and_advances_without_catchup(self):
        now = timezone.now()
        MaintenanceTaskConfig.objects.filter(pk=self.configuration.pk).update(
            enabled=True,
            frequency=MaintenanceFrequency.HOURLY,
            next_due_at=now - timedelta(days=4),
        )

        with (
            patch("maintenance.services.enqueue_run") as enqueue,
            self.captureOnCommitCallbacks(execute=True),
        ):
            first = dispatch_due_tasks(now=now)
            second = dispatch_due_tasks(now=now)

        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(MaintenanceTaskRun.objects.count(), 1)
        enqueue.assert_called_once()
        self.configuration.refresh_from_db()
        self.assertEqual(self.configuration.next_due_at, now + timedelta(hours=1))

    def test_active_run_suppresses_duplicate_dispatch_and_advances_schedule(self):
        now = timezone.now()
        MaintenanceTaskConfig.objects.filter(pk=self.configuration.pk).update(
            enabled=True,
            frequency=MaintenanceFrequency.HOURLY,
            next_due_at=now - timedelta(minutes=1),
        )
        MaintenanceTaskRun.objects.create(
            configuration=self.configuration,
            task_key=self.configuration.task_key,
            trigger=MaintenanceTaskRun.Trigger.ADMIN,
            status=MaintenanceTaskRun.Status.RUNNING,
        )

        with patch("maintenance.services.enqueue_run") as enqueue:
            self.assertEqual(dispatch_due_tasks(now=now), 0)

        enqueue.assert_not_called()
        self.assertEqual(MaintenanceTaskRun.objects.count(), 1)
        self.configuration.refresh_from_db()
        self.assertEqual(self.configuration.next_due_at, now + timedelta(hours=1))

    def test_disabled_manual_and_not_yet_due_tasks_are_skipped(self):
        now = timezone.now()
        cases = (
            (False, MaintenanceFrequency.HOURLY, now - timedelta(minutes=1)),
            (True, MaintenanceFrequency.MANUAL, None),
            (True, MaintenanceFrequency.HOURLY, now + timedelta(minutes=1)),
        )
        for enabled, frequency, next_due_at in cases:
            with self.subTest(enabled=enabled, frequency=frequency):
                MaintenanceTaskConfig.objects.filter(pk=self.configuration.pk).update(
                    enabled=enabled,
                    frequency=frequency,
                    next_due_at=next_due_at,
                )
                self.assertEqual(dispatch_due_tasks(now=now), 0)

    def test_one_active_run_per_task_is_database_enforced(self):
        MaintenanceTaskRun.objects.create(
            configuration=self.configuration,
            task_key=self.configuration.task_key,
            trigger=MaintenanceTaskRun.Trigger.ADMIN,
        )

        with self.assertRaises(IntegrityError):
            MaintenanceTaskRun.objects.create(
                configuration=self.configuration,
                task_key=self.configuration.task_key,
                trigger=MaintenanceTaskRun.Trigger.SCHEDULED,
            )

    def test_frequency_intervals_are_bounded(self):
        self.assertIsNone(MaintenanceFrequency.MANUAL.interval)
        self.assertEqual(MaintenanceFrequency.HOURLY.interval, timedelta(hours=1))
        self.assertEqual(MaintenanceFrequency.SIX_HOURS.interval, timedelta(hours=6))
        self.assertEqual(
            MaintenanceFrequency.TWELVE_HOURS.interval,
            timedelta(hours=12),
        )
        self.assertEqual(MaintenanceFrequency.DAILY.interval, timedelta(days=1))
        self.assertEqual(MaintenanceFrequency.WEEKLY.interval, timedelta(days=7))
        self.assertIsNone(MaintenanceFrequency.MONTHLY.interval)

    def test_monthly_frequency_advances_by_calendar_month(self):
        september = datetime(2026, 9, 1, 8, 30, tzinfo=UTC)
        january_end = datetime(2026, 1, 31, 8, 30, tzinfo=UTC)

        self.assertEqual(
            MaintenanceFrequency.MONTHLY.next_after(september),
            datetime(2026, 10, 1, 8, 30, tzinfo=UTC),
        )
        self.assertEqual(
            MaintenanceFrequency.MONTHLY.next_after(january_end),
            datetime(2026, 2, 28, 8, 30, tzinfo=UTC),
        )

    def test_monthly_dispatch_advances_from_current_run_without_catchup(self):
        now = datetime(2026, 10, 31, 8, 30, tzinfo=UTC)
        MaintenanceTaskConfig.objects.exclude(pk=self.configuration.pk).update(
            enabled=False,
            next_due_at=None,
        )
        MaintenanceTaskConfig.objects.filter(pk=self.configuration.pk).update(
            enabled=True,
            frequency=MaintenanceFrequency.MONTHLY,
            next_due_at=datetime(2026, 8, 31, 8, 30, tzinfo=UTC),
        )

        with patch("maintenance.services.enqueue_run"):
            self.assertEqual(dispatch_due_tasks(now=now), 1)

        self.configuration.refresh_from_db()
        self.assertEqual(
            self.configuration.next_due_at,
            datetime(2026, 11, 30, 8, 30, tzinfo=UTC),
        )

    def test_dispatcher_automatic_retention_keeps_90_days_and_active_runs(self):
        now = timezone.now()
        expired = MaintenanceTaskRun.objects.create(
            configuration=self.configuration,
            task_key=self.configuration.task_key,
            trigger=MaintenanceTaskRun.Trigger.SCHEDULED,
            status=MaintenanceTaskRun.Status.SUCCEEDED,
            completed_at=now - timedelta(days=91),
        )
        retained = MaintenanceTaskRun.objects.create(
            configuration=self.configuration,
            task_key=self.configuration.task_key,
            trigger=MaintenanceTaskRun.Trigger.SCHEDULED,
            status=MaintenanceTaskRun.Status.SUCCEEDED,
            completed_at=now - timedelta(days=8),
        )
        active = MaintenanceTaskRun.objects.create(
            configuration=self.configuration,
            task_key=self.configuration.task_key,
            trigger=MaintenanceTaskRun.Trigger.ADMIN,
        )

        dispatch_due_tasks(now=now)

        self.assertFalse(MaintenanceTaskRun.objects.filter(pk=expired.pk).exists())
        self.assertTrue(MaintenanceTaskRun.objects.filter(pk=retained.pk).exists())
        self.assertTrue(MaintenanceTaskRun.objects.filter(pk=active.pk).exists())
