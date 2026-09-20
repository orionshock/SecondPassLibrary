import uuid

from django.core.exceptions import ValidationError
from django.test import TestCase

from core import server_settings
from core.models import ServerIdentity
from core.server_identity import get_server_id


class ServerIdentityTests(TestCase):
    def test_database_has_exactly_one_valid_stable_server_id(self):
        self.assertEqual(ServerIdentity.objects.count(), 1)

        server_id = get_server_id()

        self.assertIsInstance(server_id, uuid.UUID)
        self.assertEqual(get_server_id(), server_id)
        self.assertNotIn("installation_id", [field.name for field in ServerIdentity._meta.fields])

    def test_model_rejects_replacement_deletion_and_a_second_row(self):
        identity = ServerIdentity.objects.get()
        identity.server_id = uuid.uuid4()

        with self.assertRaises(ValidationError):
            identity.save()

        identity.refresh_from_db()
        with self.assertRaises(ValidationError):
            identity.delete()
        with self.assertRaises(ValidationError):
            ServerIdentity.objects.create(id=2)

    def test_normal_server_setting_writes_do_not_change_server_id(self):
        server_id = get_server_id()

        server_settings.set_server_name("Renamed Library")
        server_settings.set_server_description("Updated description.")
        server_settings.set_server_banner_message("Updated banner.")

        self.assertEqual(get_server_id(), server_id)
