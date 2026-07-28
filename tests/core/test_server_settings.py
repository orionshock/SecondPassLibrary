from __future__ import annotations

import uuid

from django.core.cache import cache
from django.test import TestCase, override_settings

from core.checks import reading_client_base_url_check
from core.models import ServerSetting
from core.server_settings import (
    advanced_library_groups_enabled,
    clear_server_settings_cache,
    enable_advanced_library_groups,
    get_server_banner_message,
    get_reading_client_base_url,
    get_server_setting,
    get_server_settings_map,
    ensure_editable_server_settings,
    set_advanced_library_groups_enabled,
    set_server_banner_message,
    set_reading_client_base_url,
    set_server_setting,
)
from library.models import LibraryGroup
from library.groups.public_group import (
    DEFAULT_PUBLIC_GROUP_NAME,
    PUBLIC_GROUP_ID_SETTING,
    RECOVERED_PUBLIC_GROUP_DESCRIPTION,
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

    def test_reading_client_url_is_optional_and_normalized(self):
        self.assertEqual(get_reading_client_base_url(), "")

        set_reading_client_base_url("  http://localhost:5173/  ")

        self.assertEqual(get_reading_client_base_url(), "http://localhost:5173")

    def test_reading_client_url_rejects_non_root_or_unsafe_values(self):
        invalid_values = (
            "ftp://reader.example.com",
            "https://reader.example.com/app",
            "https://reader.example.com?theme=dark",
            "https://reader.example.com/#/reader",
            "https://user:password@reader.example.com",
            "https://reader.example.com/{book_id}",
            "https://reader example.com",
            "https://reader.example.com\\invalid",
            "https:///missing-host",
            "x" * 2049,
        )
        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                set_reading_client_base_url(value)

    @override_settings(
        SECOND_PASS_READING_CLIENT_BASE_URL=" https://reader.example.com/ "
    )
    def test_reading_client_environment_override_wins_and_locks_writes(self):
        ServerSetting.objects.create(
            key="reading_client_base_url",
            value="https://stored.example.com",
            description="",
        )
        clear_server_settings_cache()

        self.assertEqual(
            get_reading_client_base_url(), "https://reader.example.com"
        )
        with self.assertRaisesRegex(ValueError, "server environment"):
            set_reading_client_base_url("https://other.example.com")

    @override_settings(
        SECOND_PASS_READING_CLIENT_BASE_URL="https://reader.example.com/app"
    )
    def test_invalid_reading_client_environment_override_fails_system_check(self):
        messages = reading_client_base_url_check()

        self.assertEqual([message.id for message in messages], ["secondpass.E001"])

    def test_ensure_editable_server_settings_creates_optional_banner_row(self):
        ensure_editable_server_settings()

        setting = ServerSetting.objects.get(key="server_banner_message")

        self.assertEqual(setting.value, "")
        self.assertEqual(str(setting.display_key), "Server Banner Message")

    def test_advanced_library_groups_are_disabled_by_default(self):
        self.assertFalse(advanced_library_groups_enabled())

    def test_enable_advanced_library_groups_only_sets_true(self):
        enable_advanced_library_groups()
        self.assertTrue(advanced_library_groups_enabled())

        set_advanced_library_groups_enabled(False)
        self.assertFalse(advanced_library_groups_enabled())

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
        self.assertEqual(public.description, RECOVERED_PUBLIC_GROUP_DESCRIPTION)

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
        self.assertEqual(public.description, RECOVERED_PUBLIC_GROUP_DESCRIPTION)
        setting = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        self.assertEqual(setting.value, str(public.id))

    def test_get_public_group_repairs_invalid_string_setting_to_new_default(self):
        existing = LibraryGroup.objects.create(name=DEFAULT_PUBLIC_GROUP_NAME)
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING, value="not-a-uuid", description=""
        )
        clear_server_settings_cache()

        repaired = get_public_group()
        self.assertNotEqual(repaired.id, existing.id)
        self.assertEqual(repaired.name, DEFAULT_PUBLIC_GROUP_NAME)
        self.assertEqual(repaired.description, RECOVERED_PUBLIC_GROUP_DESCRIPTION)
        self.assertEqual(
            ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING).value,
            str(repaired.id),
        )

    def test_get_public_group_repairs_invalid_type_setting_to_new_default(self):
        existing = LibraryGroup.objects.create(name="Public")
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING, value=["not-a-uuid"], description=""
        )
        clear_server_settings_cache()

        repaired = get_public_group()
        self.assertNotEqual(repaired.id, existing.id)
        self.assertEqual(repaired.name, DEFAULT_PUBLIC_GROUP_NAME)
        self.assertEqual(repaired.description, RECOVERED_PUBLIC_GROUP_DESCRIPTION)
        self.assertEqual(
            ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING).value,
            str(repaired.id),
        )

    def test_get_public_group_does_not_adopt_group_named_public_when_setting_missing(
        self,
    ):
        ordinary = LibraryGroup.objects.create(name="Public")

        public = get_public_group()

        self.assertNotEqual(public.id, ordinary.id)
        self.assertEqual(public.name, DEFAULT_PUBLIC_GROUP_NAME)
        self.assertEqual(
            ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING).value, str(public.id)
        )

    def test_get_public_group_does_not_adopt_group_named_default_when_setting_missing(
        self,
    ):
        ordinary = LibraryGroup.objects.create(name=DEFAULT_PUBLIC_GROUP_NAME)

        public = get_public_group()

        self.assertNotEqual(public.id, ordinary.id)
        self.assertEqual(public.name, DEFAULT_PUBLIC_GROUP_NAME)
        self.assertEqual(
            ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING).value, str(public.id)
        )

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

    def test_explicit_public_group_service_repairs_saved_invalid_string_setting(self):
        public = get_public_group()
        setting = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        setting.value = "0"
        setting.save(update_fields=["value", "updated_at"])

        repaired = get_public_group()
        setting.refresh_from_db()
        self.assertEqual(setting.value, str(repaired.id))
        self.assertNotEqual(repaired.id, public.id)
        self.assertEqual(repaired.name, DEFAULT_PUBLIC_GROUP_NAME)
        self.assertEqual(repaired.description, RECOVERED_PUBLIC_GROUP_DESCRIPTION)

    def test_explicit_public_group_service_repairs_saved_invalid_type_setting(self):
        public = get_public_group()
        setting = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        setting.value = 0
        setting.save(update_fields=["value", "updated_at"])

        repaired = get_public_group()
        setting.refresh_from_db()
        self.assertEqual(setting.value, str(repaired.id))
        self.assertNotEqual(repaired.id, public.id)
        self.assertEqual(repaired.name, DEFAULT_PUBLIC_GROUP_NAME)
        self.assertEqual(repaired.description, RECOVERED_PUBLIC_GROUP_DESCRIPTION)

    def test_explicit_public_group_service_repairs_deleted_setting(self):
        public = get_public_group()
        ServerSetting.objects.filter(key=PUBLIC_GROUP_ID_SETTING).delete()

        repaired_group = get_public_group()
        repaired = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        self.assertEqual(repaired.value, str(repaired_group.id))
        self.assertNotEqual(repaired_group.id, public.id)
        self.assertEqual(repaired_group.name, DEFAULT_PUBLIC_GROUP_NAME)
        self.assertEqual(
            repaired_group.description, RECOVERED_PUBLIC_GROUP_DESCRIPTION
        )

    def test_explicit_public_group_service_repairs_corrupted_setting_for_public_check(
        self,
    ):
        public = get_public_group()
        other = LibraryGroup.objects.create(name="Other")

        setting = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        setting.value = []
        setting.save(update_fields=["value", "updated_at"])
        repaired = get_public_group()

        self.assertFalse(is_public_group(public))
        self.assertTrue(is_public_group(repaired))
        self.assertFalse(is_public_group(other))
