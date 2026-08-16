from dataclasses import replace
from unittest.mock import Mock, patch

from django.test import TestCase

from maintenance.models import MaintenanceTaskConfig, MaintenanceTaskRun
from maintenance.registry import TASK_REGISTRY
from maintenance.results import MaintenanceOperationError, MaintenanceResult
from maintenance.services import execute_run


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
            self.assertLogs("maintenance.services", level="ERROR"),
        ):
            execute_run(run.pk)

        run.refresh_from_db()
        self.assertEqual(run.status, MaintenanceTaskRun.Status.FAILED)
        self.assertEqual(
            run.failure_summary,
            "Cleanup completed with failures. failures=2",
        )
