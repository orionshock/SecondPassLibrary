from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.client_sessions import maintenance as pairing_maintenance
from accounts.management.commands import cleanup_client_pairing_requests
from marginalia.imports import maintenance as import_stage_maintenance
from marginalia.management.commands import cleanup_marginalia_import_stages
from maintenance.models import MaintenanceFrequency, MaintenanceTaskConfig
from maintenance.registry import TASK_DEFINITIONS, get_task_definition
from maintenance.services import synchronize_task_configurations
from shelves import maintenance as shelf_maintenance
from shelves.management.commands import cleanup_shelves


class MaintenanceRegistryTests(TestCase):
    def test_registry_is_fixed_and_synchronizes_code_defined_defaults(self):
        MaintenanceTaskConfig.objects.all().delete()

        synchronize_task_configurations()

        configurations = {
            item.task_key: item for item in MaintenanceTaskConfig.objects.all()
        }
        self.assertEqual(set(configurations), {item.key for item in TASK_DEFINITIONS})
        for definition in TASK_DEFINITIONS:
            configuration = configurations[definition.key]
            self.assertEqual(configuration.frequency, definition.default_frequency)
            self.assertEqual(configuration.enabled, definition.default_enabled)
            self.assertEqual(
                get_task_definition(configuration.task_key).name,
                definition.name,
            )

    def test_frequency_is_limited_to_bounded_choices(self):
        configuration = MaintenanceTaskConfig(
            task_key="invalid-frequency",
            frequency="*/5 * * * *",
        )

        with self.assertRaises(ValidationError):
            configuration.full_clean()

    def test_disabled_and_manual_configurations_have_no_due_time(self):
        disabled = MaintenanceTaskConfig.objects.create(
            task_key="disabled-test",
            enabled=False,
            frequency=MaintenanceFrequency.HOURLY,
        )
        manual = MaintenanceTaskConfig.objects.create(
            task_key="manual-test",
            enabled=True,
            frequency=MaintenanceFrequency.MANUAL,
        )

        self.assertIsNone(disabled.next_due_at)
        self.assertIsNone(manual.next_due_at)

    def test_unknown_key_has_no_executable_definition(self):
        self.assertIsNone(get_task_definition("not-a-registered-task"))

    def test_cli_and_huey_registry_share_the_same_executors(self):
        cases = (
            (
                "cleanup_client_pairing_requests",
                pairing_maintenance.execute_pairing_request_cleanup,
                cleanup_client_pairing_requests.execute_pairing_request_cleanup,
            ),
            (
                "cleanup_marginalia_import_stages",
                import_stage_maintenance.execute_import_stage_cleanup,
                cleanup_marginalia_import_stages.execute_import_stage_cleanup,
            ),
            (
                "cleanup_unavailable_shelf_items",
                shelf_maintenance.execute_unavailable_shelf_item_cleanup,
                cleanup_shelves.execute_unavailable_shelf_item_cleanup,
            ),
        )
        for key, shared_executor, command_executor in cases:
            with self.subTest(key=key):
                self.assertIs(get_task_definition(key).execute, shared_executor)
                self.assertIs(command_executor, shared_executor)
