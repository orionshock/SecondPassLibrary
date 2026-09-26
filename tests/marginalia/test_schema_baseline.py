from django.db import connection
from django.test import TestCase

from core.models import ServerIdentity
from maintenance.models import MaintenanceTaskConfig
from maintenance.registry import TASK_DEFINITIONS


class FreshInstallBaselineTests(TestCase):
    def test_required_database_birth_state_and_location_columns(self):
        self.assertEqual(ServerIdentity.objects.count(), 1)
        self.assertSetEqual(
            set(MaintenanceTaskConfig.objects.values_list("task_key", flat=True)),
            {definition.key for definition in TASK_DEFINITIONS},
        )

        with connection.cursor() as cursor:
            session_columns = {
                column.name
                for column in connection.introspection.get_table_description(
                    cursor, "marginalia_readingsession"
                )
            }
            annotation_columns = {
                column.name
                for column in connection.introspection.get_table_description(
                    cursor, "marginalia_annotation"
                )
            }

        self.assertIn("progress_location", session_columns)
        self.assertIn("location", annotation_columns)
