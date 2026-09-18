import uuid

from django.core.exceptions import ValidationError
from django.test import TestCase

from core import server_settings
from core.models import ServerInstallation
from core.server_installation import get_installation_id


class ServerInstallationTests(TestCase):
    def test_database_has_exactly_one_valid_stable_installation_id(self):
        self.assertEqual(ServerInstallation.objects.count(), 1)

        installation_id = get_installation_id()

        self.assertIsInstance(installation_id, uuid.UUID)
        self.assertEqual(get_installation_id(), installation_id)

    def test_model_rejects_replacement_deletion_and_a_second_row(self):
        installation = ServerInstallation.objects.get()
        installation.installation_id = uuid.uuid4()

        with self.assertRaises(ValidationError):
            installation.save()

        installation.refresh_from_db()
        with self.assertRaises(ValidationError):
            installation.delete()
        with self.assertRaises(ValidationError):
            ServerInstallation.objects.create(id=2)

    def test_normal_server_setting_writes_do_not_change_installation_id(self):
        installation_id = get_installation_id()

        server_settings.set_server_name("Renamed Library")
        server_settings.set_server_description("Updated description.")
        server_settings.set_server_banner_message("Updated banner.")

        self.assertEqual(get_installation_id(), installation_id)
