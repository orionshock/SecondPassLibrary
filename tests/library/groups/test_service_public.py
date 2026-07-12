from __future__ import annotations

from uuid import uuid4

from django.core.exceptions import ValidationError

from core.server_settings import set_server_setting
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING, get_public_group, is_public_group
from library.groups.services import configure_public_group, delete_library_group
from library.models import LibraryGroup
from tests.library.groups.service_helpers import LibraryGroupServiceTestCase


class LibraryPublicGroupServiceTests(LibraryGroupServiceTestCase):
    def test_public_identity_is_setting_id_based_and_survives_rename(self):
        self.public.name = "Renamed"
        self.public.save(update_fields=["name", "updated_at"])

        self.assertTrue(is_public_group(self.public))
        self.assertEqual(get_public_group().id, self.public.id)

    def test_stale_public_setting_self_heals(self):
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(uuid4()),
            description="Public/Common Room group id.",
        )

        healed = get_public_group()

        self.assertTrue(LibraryGroup.objects.filter(pk=healed.pk).exists())
        self.assertTrue(is_public_group(healed))

    def test_configure_public_group_is_idempotent(self):
        configured = configure_public_group(name="Renamed Public", description="Updated")

        self.assertEqual(configured.id, self.public.id)
        self.assertEqual(LibraryGroup.objects.count(), 1)
        self.assertEqual(configured.name, "Renamed Public")
        self.assertEqual(configured.description, "Updated")
        self.assertTrue(is_public_group(configured))

    def test_renamed_public_group_cannot_be_deleted(self):
        configure_public_group(name="Library Lobby", description="Still public")
        self.public.refresh_from_db()

        with self.assertRaises(ValidationError):
            delete_library_group(group=self.public)

        self.assertTrue(LibraryGroup.objects.filter(pk=self.public.pk).exists())
