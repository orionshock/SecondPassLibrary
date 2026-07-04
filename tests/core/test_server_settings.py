from __future__ import annotations

import uuid

from django.core.cache import cache
from django.test import TestCase

from core.models import ServerSetting
from core.server_settings import (
    clear_server_settings_cache,
    get_server_banner_message,
    get_server_setting,
    get_server_settings_map,
    set_server_banner_message,
    set_server_setting,
)
from library.models import LibraryGroup
from library.groups.public_group import (
    DEFAULT_PUBLIC_GROUP_NAME,
    PUBLIC_GROUP_ID_SETTING,
    get_public_group,
    is_public_group,
)


class ServerSettingsServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        clear_server_settings_cache()

    def test_get_set_roundtrip(self):
        self.assertIsNone(get_server_setting("example", default=None))
        set_server_setting(key="example", value={"a": 1}, description="d")
        self.assertEqual(get_server_setting("example", default=None), {"a": 1})

    def test_server_banner_message_is_optional_and_trimmed(self):
        self.assertEqual(get_server_banner_message(), "")

        set_server_banner_message("  Server maintenance tonight.  ")
        self.assertEqual(get_server_banner_message(), "Server maintenance tonight.")

        set_server_banner_message("   ")
        self.assertEqual(get_server_banner_message(), "")

    def test_server_banner_message_rejects_overlong_value(self):
        with self.assertRaises(ValueError):
            set_server_banner_message("x" * 501)

    def test_settings_are_cached_until_cleared(self):
        ServerSetting.objects.create(key="k", value="v1", description="")
        self.assertEqual(get_server_setting("k", default=None), "v1")

        # Direct DB update should not be visible until cache invalidation.
        ServerSetting.objects.filter(key="k").update(value="v2")
        self.assertEqual(get_server_setting("k", default=None), "v1")

        clear_server_settings_cache()
        self.assertEqual(get_server_setting("k", default=None), "v2")

    def test_set_invalidates_cache(self):
        ServerSetting.objects.create(key="k", value="v1", description="")
        _ = get_server_settings_map()

        set_server_setting(key="k", value="v2", description="")
        self.assertEqual(get_server_setting("k", default=None), "v2")

    def test_direct_model_save_invalidates_cache(self):
        obj = ServerSetting.objects.create(key="k", value="v1", description="")
        _ = get_server_settings_map()

        obj.value = "v2"
        obj.save(update_fields=["value", "updated_at"])
        self.assertEqual(get_server_setting("k", default=None), "v2")

    def test_direct_model_delete_invalidates_cache(self):
        obj = ServerSetting.objects.create(key="k", value="v1", description="")
        _ = get_server_settings_map()

        obj.delete()
        self.assertEqual(get_server_setting("k", default="missing"), "missing")

    def test_get_public_group_missing_setting_creates_new_default_group(self):
        ordinary = LibraryGroup.objects.create(name="Existing Room")
        clear_server_settings_cache()

        public = get_public_group()
        self.assertNotEqual(public.id, ordinary.id)
        self.assertEqual(public.name, DEFAULT_PUBLIC_GROUP_NAME)

        setting = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        self.assertEqual(setting.value, str(public.id))

    def test_get_public_group_repairs_missing_group_by_creating_new_default(self):
        missing_id = str(uuid.uuid4())
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=missing_id,
            description="",
        )
        clear_server_settings_cache()

        public = get_public_group()
        self.assertEqual(public.name, DEFAULT_PUBLIC_GROUP_NAME)
        setting = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        self.assertEqual(setting.value, str(public.id))

    def test_get_public_group_repairs_invalid_string_setting_to_new_default(self):
        existing = LibraryGroup.objects.create(name=DEFAULT_PUBLIC_GROUP_NAME)
        set_server_setting(key=PUBLIC_GROUP_ID_SETTING, value="not-a-uuid", description="")
        clear_server_settings_cache()

        repaired = get_public_group()
        self.assertNotEqual(repaired.id, existing.id)
        self.assertEqual(repaired.name, DEFAULT_PUBLIC_GROUP_NAME)
        self.assertEqual(ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING).value, str(repaired.id))

    def test_get_public_group_repairs_invalid_type_setting_to_new_default(self):
        existing = LibraryGroup.objects.create(name="Public")
        set_server_setting(key=PUBLIC_GROUP_ID_SETTING, value=["not-a-uuid"], description="")
        clear_server_settings_cache()

        repaired = get_public_group()
        self.assertNotEqual(repaired.id, existing.id)
        self.assertEqual(repaired.name, DEFAULT_PUBLIC_GROUP_NAME)
        self.assertEqual(ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING).value, str(repaired.id))

    def test_get_public_group_does_not_adopt_group_named_public_when_setting_missing(self):
        ordinary = LibraryGroup.objects.create(name="Public")

        public = get_public_group()

        self.assertNotEqual(public.id, ordinary.id)
        self.assertEqual(public.name, DEFAULT_PUBLIC_GROUP_NAME)
        self.assertEqual(ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING).value, str(public.id))

    def test_get_public_group_does_not_adopt_group_named_default_when_setting_missing(self):
        ordinary = LibraryGroup.objects.create(name=DEFAULT_PUBLIC_GROUP_NAME)

        public = get_public_group()

        self.assertNotEqual(public.id, ordinary.id)
        self.assertEqual(public.name, DEFAULT_PUBLIC_GROUP_NAME)
        self.assertEqual(ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING).value, str(public.id))

    def test_get_public_group_preserves_configured_display_name(self):
        group = get_public_group()
        group.name = "Shared"
        group.save(update_fields=["name", "updated_at"])

        repaired = get_public_group()
        self.assertEqual(repaired.id, group.id)
        repaired.refresh_from_db()
        self.assertEqual(repaired.name, "Shared")

    def test_renamed_configured_public_group_is_still_public_by_id(self):
        public = get_public_group()
        public.name = "Renamed Room"
        public.save(update_fields=["name", "updated_at"])
        ordinary = LibraryGroup.objects.create(name=DEFAULT_PUBLIC_GROUP_NAME)

        self.assertTrue(is_public_group(public))
        self.assertFalse(is_public_group(ordinary))

    def test_public_group_setting_save_triggers_repair_invalid_string(self):
        public = get_public_group()
        setting = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        setting.value = "0"
        setting.save(update_fields=["value", "updated_at"])

        setting.refresh_from_db()
        self.assertNotEqual(setting.value, str(public.id))
        repaired = LibraryGroup.objects.get(pk=setting.value)
        self.assertEqual(repaired.name, DEFAULT_PUBLIC_GROUP_NAME)

    def test_public_group_setting_save_triggers_repair_invalid_type(self):
        public = get_public_group()
        setting = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        setting.value = 0
        setting.save(update_fields=["value", "updated_at"])

        setting.refresh_from_db()
        self.assertNotEqual(setting.value, str(public.id))
        repaired = LibraryGroup.objects.get(pk=setting.value)
        self.assertEqual(repaired.name, DEFAULT_PUBLIC_GROUP_NAME)

    def test_public_group_setting_delete_triggers_repair(self):
        public = get_public_group()
        ServerSetting.objects.filter(key=PUBLIC_GROUP_ID_SETTING).delete()

        repaired = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        self.assertNotEqual(repaired.value, str(public.id))
        repaired_group = LibraryGroup.objects.get(pk=repaired.value)
        self.assertEqual(repaired_group.name, DEFAULT_PUBLIC_GROUP_NAME)

    def test_is_public_group_repairs_corrupted_setting(self):
        public = get_public_group()
        other = LibraryGroup.objects.create(name="Other")

        setting = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        setting.value = []
        setting.save(update_fields=["value", "updated_at"])
        setting.refresh_from_db()
        repaired = LibraryGroup.objects.get(pk=setting.value)

        self.assertFalse(is_public_group(public))
        self.assertTrue(is_public_group(repaired))
        self.assertFalse(is_public_group(other))
