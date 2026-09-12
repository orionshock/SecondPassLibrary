from dataclasses import replace
from unittest.mock import Mock, patch

from django.test import TestCase

from maintenance.models import MaintenanceTaskConfig, MaintenanceTaskRun
from maintenance.registry import TASK_REGISTRY
from maintenance.results import MaintenanceOperationError, MaintenanceResult
from maintenance.services import enqueue_run, execute_run


class MaintenanceExecutionTests(TestCase):
    def setUp(self):
        self.configuration = MaintenanceTaskConfig.objects.get(
            task_key="cleanup_client_pairing_requests"
        )

    def create_run(self, *, task_key=None):
        return MaintenanceTaskRun.objects.create(
            configuration=self.configuration,
            task_key=task_key or self.configuration.task_key,
            trigger=MaintenanceTaskRun.Trigger.ADMIN,
        )

    def test_success_persists_bounded_result_and_logs_lifecycle(self):
        run = self.create_run()
        definition = TASK_REGISTRY[run.task_key]
        executor = Mock(
            return_value=MaintenanceResult(
                summary="x" * 2000,
                counts={f"count_{index}": index for index in range(20)},
            )
        )

        with (
            patch.dict(
                TASK_REGISTRY,
                {run.task_key: replace(definition, execute=executor)},
            ),
            self.assertLogs("maintenance.services", level="INFO") as logs,
        ):
            execute_run(run.pk)

        run.refresh_from_db()
        self.assertEqual(run.status, MaintenanceTaskRun.Status.SUCCEEDED)
        self.assertEqual(len(run.result_summary), 1000)
        self.assertEqual(len(run.result_counts), 12)
        self.assertIsNotNone(run.started_at)
        self.assertIsNotNone(run.completed_at)
        executor.assert_called_once_with()
        self.assertIn("Maintenance task started", "\n".join(logs.output))
        self.assertIn("Maintenance task succeeded", "\n".join(logs.output))

    def test_unexpected_failure_is_bounded_and_retryable(self):
        run = self.create_run()
        definition = TASK_REGISTRY[run.task_key]
        executor = Mock(side_effect=RuntimeError("internal secret detail"))

        with (
            patch.dict(
                TASK_REGISTRY,
                {run.task_key: replace(definition, execute=executor)},
            ),
            self.assertLogs("maintenance.services", level="ERROR"),
        ):
            execute_run(run.pk)

        run.refresh_from_db()
        self.assertEqual(run.status, MaintenanceTaskRun.Status.FAILED)
        self.assertNotIn("internal secret detail", run.failure_summary)
        self.assertIsNotNone(run.completed_at)
        retry = self.create_run()
        self.assertEqual(retry.status, MaintenanceTaskRun.Status.QUEUED)

    def test_unknown_retired_key_cannot_execute(self):
        run = self.create_run(task_key="retired.dotted.callable")

        execute_run(run.pk)

        run.refresh_from_db()
        self.assertEqual(run.status, MaintenanceTaskRun.Status.FAILED)
        self.assertIn("no longer available", run.failure_summary)

    def test_expected_operation_failure_keeps_bounded_operator_summary(self):
        run = self.create_run()
        definition = TASK_REGISTRY[run.task_key]
        executor = Mock(
            side_effect=MaintenanceOperationError(
                "Cleanup completed with failures.",
                result=MaintenanceResult(summary="failures=2"),
            )
        )

        with (
            patch.dict(
                TASK_REGISTRY,
                {run.task_key: replace(definition, execute=executor)},
            ),
            self.assertLogs("maintenance.services", level="WARNING") as captured,
        ):
            execute_run(run.pk)

        run.refresh_from_db()
        self.assertEqual(run.status, MaintenanceTaskRun.Status.FAILED)
        self.assertEqual(
            run.failure_summary,
            "Cleanup completed with failures. failures=2",
        )
        self.assertIn("operational failure", captured.output[0])
        self.assertIn("retry_safety=inspect_task_result_before_retry", captured.output[0])

    def test_enqueue_failure_marks_only_the_still_queued_run_failed(self):
        queued = self.create_run()
        running = self.create_run(task_key="other-task")
        MaintenanceTaskRun.objects.filter(pk=running.pk).update(
            status=MaintenanceTaskRun.Status.RUNNING
        )

        with (
            patch(
                "maintenance.tasks.execute_maintenance_run",
                side_effect=RuntimeError("broker unavailable"),
            ),
            self.assertLogs("maintenance.services", level="ERROR"),
        ):
            enqueue_run(queued.pk)
            enqueue_run(running.pk)

        queued.refresh_from_db()
        running.refresh_from_db()
        self.assertEqual(queued.status, MaintenanceTaskRun.Status.FAILED)
        self.assertEqual(running.status, MaintenanceTaskRun.Status.RUNNING)
        self.assertNotIn("broker unavailable", queued.failure_summary)

    def test_running_run_cannot_execute_twice(self):
        run = self.create_run()
        MaintenanceTaskRun.objects.filter(pk=run.pk).update(
            status=MaintenanceTaskRun.Status.RUNNING
        )
        definition = TASK_REGISTRY[run.task_key]
        executor = Mock()

        with patch.dict(
            TASK_REGISTRY,
            {run.task_key: replace(definition, execute=executor)},
        ):
            execute_run(run.pk)

        executor.assert_not_called()
