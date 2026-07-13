from __future__ import annotations

from uuid import uuid4

from django.core.exceptions import ValidationError

from core.models import ServerSetting
from core.server_settings import set_server_setting
from library.groups.public_group import (
    DEFAULT_PUBLIC_GROUP_NAME,
    PUBLIC_GROUP_ID_SETTING,
    RECOVERED_PUBLIC_GROUP_DESCRIPTION,
    get_public_group,
    is_public_group,
)
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

    def test_configure_public_group_normalizes_name_and_description(self):
        configured = configure_public_group(
            name="  Trimmed Room  ",
            description="  Trimmed description  ",
        )

        self.assertEqual(configured.name, "Trimmed Room")
        self.assertEqual(configured.description, "Trimmed description")

        configured = configure_public_group(name="   ", description="   ")

        self.assertEqual(configured.name, DEFAULT_PUBLIC_GROUP_NAME)
        self.assertEqual(configured.description, "")

    def test_configure_public_group_preserves_explicit_blank_description(self):
        configured = configure_public_group(
            name=None,
            description="",
        )

        self.assertEqual(configured.name, DEFAULT_PUBLIC_GROUP_NAME)
        self.assertEqual(configured.description, "")

    def test_configure_public_group_noop_does_not_save_group_or_rewrite_setting(self):
        configured = configure_public_group(name="Stable Public", description="")
        setting = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        group_updated_at = configured.updated_at
        setting_updated_at = setting.updated_at

        same = configure_public_group(name="  Stable Public  ", description="   ")
        setting.refresh_from_db()

        self.assertEqual(same.pk, configured.pk)
        self.assertEqual(same.updated_at, group_updated_at)
        self.assertEqual(setting.updated_at, setting_updated_at)

    def test_configure_public_group_changed_values_persist(self):
        configured = configure_public_group(name="Before", description="")
        original_updated_at = configured.updated_at

        changed = configure_public_group(name="After", description="New description")

        self.assertEqual(changed.pk, configured.pk)
        self.assertEqual(changed.name, "After")
        self.assertEqual(changed.description, "New description")
        self.assertGreater(changed.updated_at, original_updated_at)

    def test_setup_configuration_and_corruption_recovery_descriptions_remain_distinct(self):
        configured = configure_public_group(name="Setup Room", description="")

        self.assertEqual(configured.description, "")

        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(uuid4()),
            description="Public/Common Room group id.",
        )
        recovered = get_public_group()

        self.assertEqual(recovered.description, RECOVERED_PUBLIC_GROUP_DESCRIPTION)

    def test_renamed_public_group_cannot_be_deleted(self):
        configure_public_group(name="Library Lobby", description="Still public")
        self.public.refresh_from_db()

        with self.assertRaises(ValidationError):
            delete_library_group(group=self.public)

        self.assertTrue(LibraryGroup.objects.filter(pk=self.public.pk).exists())
