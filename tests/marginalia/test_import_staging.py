from __future__ import annotations

from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from marginalia.imports.services import preview_import
from marginalia.imports.staging import (
    ImportStageStorageError,
    ImportStageUnavailableError,
    cleanup_import_stages,
    import_stage_root,
    load_import_stage,
    stage_file_path,
)
from marginalia.models import ImportStage
from tests.marginalia.import_helpers import archive_payload, archive_upload
from tests.testenv.filesystem import IsolatedUserdataMixin


User = get_user_model()


class MarginaliaImportStagingTests(IsolatedUserdataMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="testpass")
        self.other = User.objects.create_user(username="other", password="testpass")

    def create_stage(self):
        result = preview_import(
            user=self.user,
            file=archive_upload(archive_payload(file_hash=f"sha256:{'a' * 64}")),
            include_empty_sessions=True,
        )
        return result["import_token"], ImportStage.objects.get()

    def test_lookup_is_user_bound_and_expiry_is_immediate_no_leakage(self):
        token, stage = self.create_stage()
        self.assertEqual(load_import_stage(user=self.user, token=token), stage)
        with self.assertRaises(ImportStageUnavailableError):
            load_import_stage(user=self.other, token=token)
        with self.assertRaises(ImportStageUnavailableError):
            load_import_stage(user=self.user, token="not-a-token")

        path = stage_file_path(stage.storage_name)
        ImportStage.objects.filter(pk=stage.pk).update(expires_at=timezone.now())
        with self.assertRaises(ImportStageUnavailableError):
            load_import_stage(user=self.user, token=token)
        self.assertFalse(ImportStage.objects.filter(pk=stage.pk).exists())
        self.assertFalse(path.exists())

    def test_stage_file_and_record_fail_as_one_preview_operation(self):
        files_before = (
            set(import_stage_root().iterdir())
            if import_stage_root().exists()
            else set()
        )
        with (
            patch("marginalia.imports.staging.os.replace", side_effect=OSError),
            self.assertRaises(ImportStageStorageError),
        ):
            self.create_stage()

        self.assertEqual(ImportStage.objects.count(), 0)
        files_after = (
            set(import_stage_root().iterdir())
            if import_stage_root().exists()
            else set()
        )
        self.assertEqual(files_after, files_before)

    def test_cleanup_dry_run_then_delete_is_bounded_and_repeat_safe(self):
        _token, expired = self.create_stage()
        ImportStage.objects.filter(pk=expired.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        orphan = import_stage_root() / ("f" * 64 + ".json")
        orphan.write_bytes(b"orphan")

        dry_output = StringIO()
        call_command(
            "cleanup_marginalia_import_stages", dry_run=True, stdout=dry_output
        )
        self.assertTrue(ImportStage.objects.filter(pk=expired.pk).exists())
        self.assertTrue(stage_file_path(expired.storage_name).exists())
        self.assertNotIn(str(import_stage_root()), dry_output.getvalue())

        output = StringIO()
        call_command("cleanup_marginalia_import_stages", stdout=output)
        self.assertFalse(ImportStage.objects.filter(pk=expired.pk).exists())
        self.assertFalse(stage_file_path(expired.storage_name).exists())
        self.assertFalse(orphan.exists())
        self.assertIn("expired_stages_found=1", output.getvalue())
        self.assertNotIn(self.user.username, output.getvalue())

        repeated = cleanup_import_stages()
        self.assertEqual(repeated.failures, 0)
        self.assertEqual(repeated.expired_stages_found, 0)

    def test_cleanup_missing_file_removes_record_safely(self):
        _token, stage = self.create_stage()
        stage_file_path(stage.storage_name).unlink()
        ImportStage.objects.filter(pk=stage.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )

        result = cleanup_import_stages()

        self.assertEqual(result.missing_files, 1)
        self.assertEqual(result.records_deleted, 1)

    def test_cleanup_failure_is_nonzero_and_retains_stage_for_retry(self):
        _token, stage = self.create_stage()
        ImportStage.objects.filter(pk=stage.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        real_unlink = Path.unlink

        def fail_stage_file(path, *args, **kwargs):
            if path == stage_file_path(stage.storage_name):
                raise OSError("simulated")
            return real_unlink(path, *args, **kwargs)

        with (
            patch.object(Path, "unlink", fail_stage_file),
            self.assertRaises(CommandError),
        ):
            call_command("cleanup_marginalia_import_stages", stdout=StringIO())

        self.assertTrue(ImportStage.objects.filter(pk=stage.pk).exists())
