from __future__ import annotations

import uuid

from django.core.cache import cache
from django.test import TestCase

from core.models import ServerSetting
from core.server_settings import (
    clear_server_settings_cache,
    get_server_setting,
    get_server_settings_map,
    set_server_setting,
)
from library.group_services import PUBLIC_GROUP_ID_SETTING, get_public_group


class ServerSettingsServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        clear_server_settings_cache()

    def test_get_set_roundtrip(self):
        self.assertIsNone(get_server_setting("example", default=None))
        set_server_setting(key="example", value={"a": 1}, description="d")
        self.assertEqual(get_server_setting("example", default=None), {"a": 1})

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

    def test_get_public_group_repairs_missing_setting(self):
        public = get_public_group()
        ServerSetting.objects.filter(key=PUBLIC_GROUP_ID_SETTING).delete()
        clear_server_settings_cache()

        public2 = get_public_group()
        self.assertEqual(public2.id, public.id)

        setting = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        self.assertEqual(setting.value, str(public.id))

    def test_get_public_group_repairs_missing_group(self):
        missing_id = str(uuid.uuid4())
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=missing_id,
            description="",
        )
        clear_server_settings_cache()

        public = get_public_group()
        self.assertEqual(public.name, "Public")
        setting = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        self.assertEqual(setting.value, str(public.id))

