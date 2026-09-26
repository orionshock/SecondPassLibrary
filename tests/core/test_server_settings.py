from __future__ import annotations

import multiprocessing
import uuid
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep

from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings

from core.checks import second_pass_reader_web_client_url_check
from core.models import ServerSetting
from core.server_settings import (
    MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
    MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
    advanced_library_groups_enabled,
    clear_server_settings_cache,
    enable_advanced_library_groups,
    get_server_banner_message,
    get_server_description,
    get_second_pass_reader_web_client_url,
    get_marginalia_active_session_tombstone_retention_days,
    get_marginalia_closed_session_tombstone_retention_days,
    get_server_setting,
    ensure_editable_server_settings,
    set_advanced_library_groups_enabled,
    set_server_banner_message,
    set_server_description,
    set_second_pass_reader_web_client_url,
    set_server_setting,
    set_marginalia_tombstone_retention_days,
    synchronize_deployment_server_settings,
)
from library.models import LibraryGroup
from library.groups.public_group import (
    DEFAULT_PUBLIC_GROUP_NAME,
    PUBLIC_GROUP_ID_SETTING,
    RECOVERED_PUBLIC_GROUP_DESCRIPTION,
    get_public_group,
    is_public_group,
)
from tests.core.server_settings_worker import run_server_settings_worker


def _worker_result(pipe):
    if not pipe.poll(10):
        raise AssertionError("Server-settings worker did not respond")
    status, result = pipe.recv()
    if status == "error":
        raise AssertionError(result)
    return result


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

    def test_server_identity_rich_text_uses_the_shared_limited_html_policy(self):
        set_server_description(
            '<p class="lead">About <strong>this server</strong></p>'
            '<script>alert("no")</script><a href="https://example.test">origin</a>'
        )
        set_server_banner_message(
            '<ul data-list="yes"><li><em>Maintenance</em></li></ul>'
            '<img src="x" onerror="alert(1)">'
        )

        self.assertEqual(
            get_server_description(),
            "<p>About <strong>this server</strong></p>origin",
        )
        self.assertEqual(
            get_server_banner_message(),
            "<ul><li><em>Maintenance</em></li></ul>",
        )

    def test_second_pass_reader_web_client_url_is_optional_and_canonical(self):
        self.assertEqual(get_second_pass_reader_web_client_url(), "")

        cases = {
            "https://reader.example.com": "https://reader.example.com",
            "https://reader.example.com/": "https://reader.example.com",
            "https://reader.example.com/some/path?foo=bar#section": (
                "https://reader.example.com"
            ),
            "https://reader.example.com:8443/path": (
                "https://reader.example.com:8443"
            ),
            "  http://localhost:5173/something  ": "http://localhost:5173",
        }
        for supplied, expected in cases.items():
            with self.subTest(supplied=supplied):
                set_second_pass_reader_web_client_url(supplied)
                self.assertEqual(get_second_pass_reader_web_client_url(), expected)

    def test_second_pass_reader_web_client_url_rejects_invalid_values(self):
        invalid_values = (
            "ftp://reader.example.com",
            "reader.example.com",
            "/reader",
            "https://user:password@reader.example.com",
            "https://reader.example.com/{book_id}",
            "https://reader example.com",
            "https://reader.example.com\\invalid",
            "https:///missing-host",
            "x" * 2049,
        )
        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                set_second_pass_reader_web_client_url(value)

    @override_settings(
        SECOND_PASS_READER_WEB_CLIENT_URL=(
            " https://reader.example.com:8443/application?theme=dark#home "
        )
    )
    def test_deployment_sync_persists_canonical_url_and_locks_writes(self):
        ServerSetting.objects.create(
            key="second_pass_reader_web_client_url",
            value="https://stored.example.com",
            description="",
        )
        clear_server_settings_cache()

        self.assertEqual(
            get_second_pass_reader_web_client_url(), "https://stored.example.com"
        )
        call_command("sync_deployment_server_settings", stdout=StringIO())

        self.assertEqual(
            get_second_pass_reader_web_client_url(), "https://reader.example.com:8443"
        )
        self.assertEqual(
            ServerSetting.objects.get(
                key="second_pass_reader_web_client_url"
            ).value,
            "https://reader.example.com:8443",
        )
        with self.assertRaisesRegex(ValueError, "server environment"):
            set_second_pass_reader_web_client_url("https://other.example.com")

    @override_settings(
        SECOND_PASS_READER_WEB_CLIENT_URL="ftp://reader.example.com/app"
    )
    def test_invalid_reader_web_client_environment_value_fails_system_check(self):
        messages = second_pass_reader_web_client_url_check()

        self.assertEqual([message.id for message in messages], ["secondpass.E001"])

    @override_settings(SECOND_PASS_READER_WEB_CLIENT_URL="")
    def test_deployment_sync_without_environment_value_leaves_storage_unchanged(self):
        set_second_pass_reader_web_client_url("https://stored.example.com")

        self.assertFalse(synchronize_deployment_server_settings())
        self.assertEqual(
            get_second_pass_reader_web_client_url(), "https://stored.example.com"
        )

    def test_ensure_editable_server_settings_creates_optional_banner_row(self):
        ensure_editable_server_settings()

        setting = ServerSetting.objects.get(key="server_banner_message")

        self.assertEqual(setting.value, "")

    def test_annotation_tombstone_retention_defaults_and_validation(self):
        self.assertEqual(
            get_marginalia_closed_session_tombstone_retention_days(), 7
        )
        self.assertEqual(
            get_marginalia_active_session_tombstone_retention_days(), 28
        )

        set_server_setting(
            key=MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
            value=4,
        )
        self.assertEqual(
            get_marginalia_closed_session_tombstone_retention_days(), 4
        )

        for invalid in (-1, True, "7"):
            set_server_setting(
                key=MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
                value=invalid,
            )
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                get_marginalia_active_session_tombstone_retention_days()

    def test_paired_annotation_retention_write_publishes_complete_state(self):
        with self.captureOnCommitCallbacks(execute=True):
            set_marginalia_tombstone_retention_days(
                active_days=35,
                closed_days=9,
            )

        self.assertEqual(
            get_marginalia_active_session_tombstone_retention_days(), 35
        )
        self.assertEqual(
            get_marginalia_closed_session_tombstone_retention_days(), 9
        )

    def test_advanced_library_groups_are_disabled_by_default(self):
        self.assertFalse(advanced_library_groups_enabled())

    def test_enable_advanced_library_groups_only_sets_true(self):
        enable_advanced_library_groups()
        self.assertTrue(advanced_library_groups_enabled())

        set_advanced_library_groups_enabled(False)
        self.assertFalse(advanced_library_groups_enabled())

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


class ServerSettingsFreshnessTests(TransactionTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_direct_model_mutations_refresh_public_getters_after_commit(self):
        setting = ServerSetting.objects.create(key="k", value="v1", description="")
        self.assertEqual(get_server_setting("k", default=None), "v1")

        setting.value = "v2"
        setting.save(update_fields=["value", "updated_at"])
        self.assertEqual(get_server_setting("k", default=None), "v2")

        setting.delete()
        self.assertIsNone(get_server_setting("k", default=None))

    def test_worker_sensitive_retention_read_bypasses_stale_process_cache(self):
        ServerSetting.objects.create(
            key=MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
            value=28,
        )
        self.assertEqual(
            get_server_setting(
                MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING
            ),
            28,
        )

        # A commit in another process cannot invalidate this process's LocMemCache.
        ServerSetting.objects.filter(
            key=MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING
        ).update(value=2)

        self.assertEqual(
            get_server_setting(
                MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING
            ),
            28,
        )
        self.assertEqual(
            get_marginalia_active_session_tombstone_retention_days(),
            2,
        )


class ServerSettingsCrossWorkerFreshnessTests(SimpleTestCase):
    def test_commits_become_visible_after_cache_expiry_and_rollbacks_do_not_publish(self):
        process_context = multiprocessing.get_context("spawn")
        cache_seconds = 0.2

        with TemporaryDirectory() as temp_dir:
            database_path = str(Path(temp_dir) / "server-settings.sqlite3")
            writer_pipe, writer_child_pipe = process_context.Pipe()
            reader_pipe, reader_child_pipe = process_context.Pipe()
            writer = process_context.Process(
                target=run_server_settings_worker,
                args=(database_path, writer_child_pipe, cache_seconds),
            )
            reader = process_context.Process(
                target=run_server_settings_worker,
                args=(database_path, reader_child_pipe, cache_seconds),
            )
            writer.start()
            try:
                writer_pipe.send(("bootstrap", None))
                self.assertIsNone(_worker_result(writer_pipe))
                reader.start()

                writer_pipe.send(("set", "Original"))
                self.assertIsNone(_worker_result(writer_pipe))
                reader_pipe.send(("get", None))
                self.assertEqual(_worker_result(reader_pipe), "Original")

                writer_pipe.send(("set", "Committed"))
                self.assertIsNone(_worker_result(writer_pipe))
                reader_pipe.send(("get", None))
                self.assertEqual(_worker_result(reader_pipe), "Original")

                sleep(cache_seconds * 2)
                reader_pipe.send(("get", None))
                self.assertEqual(_worker_result(reader_pipe), "Committed")

                writer_pipe.send(("get", None))
                self.assertEqual(_worker_result(writer_pipe), "Committed")
                writer_pipe.send(("rollback", "Rolled back"))
                self.assertEqual(_worker_result(writer_pipe), "Committed")

                sleep(cache_seconds * 2)
                reader_pipe.send(("get", None))
                self.assertEqual(_worker_result(reader_pipe), "Committed")
            finally:
                for pipe, process in (
                    (reader_pipe, reader),
                    (writer_pipe, writer),
                ):
                    if process.pid is None:
                        continue
                    if process.is_alive():
                        pipe.send(("close", None))
                        _worker_result(pipe)
                    process.join(timeout=10)
                    if process.is_alive():
                        process.terminate()
                        process.join(timeout=10)
