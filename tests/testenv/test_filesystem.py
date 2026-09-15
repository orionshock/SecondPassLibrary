from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import SimpleTestCase

from .filesystem import IsolatedMediaRootMixin, RuntimePathIsolation


ROOT = Path(__file__).resolve().parents[2]


class RuntimePathIsolationTests(SimpleTestCase):
    def test_runtime_paths_use_os_temp_and_cleanup(self):
        isolation = RuntimePathIsolation(
            userdata=True,
            media=True,
            imports=True,
            static=True,
        )
        isolation.enable()
        assert isolation.root is not None
        assert isolation.userdata_root is not None
        assert isolation.media_root is not None
        assert isolation.imports_dir is not None
        assert isolation.static_root is not None

        root = isolation.root
        marker = isolation.imports_dir / "marker.txt"
        marker.write_text("created by test", encoding="utf-8")

        self.assertTrue(root.exists())
        self.assertFalse(root.is_relative_to(ROOT / "TestFiles"))
        self.assertFalse(root.is_relative_to(ROOT / "userdata"))
        self.assertFalse(root.is_relative_to(ROOT / "var"))
        self.assertEqual(settings.USERDATA_DIR, isolation.userdata_root)
        self.assertEqual(Path(settings.MEDIA_ROOT), isolation.media_root)
        self.assertEqual(settings.IMPORTS_DIR, isolation.imports_dir)
        self.assertEqual(Path(settings.STATIC_ROOT), isolation.static_root)

        isolation.disable()

        self.assertFalse(root.exists())


class MediaRootPerTestIsolationTests(IsolatedMediaRootMixin, SimpleTestCase):
    storage_name = "covers/reused-name.png"

    def setUp(self):
        self.saved_name = default_storage.save(
            self.storage_name,
            ContentFile(b"same cover bytes"),
        )

    def test_first_write_keeps_requested_name(self):
        self.assertEqual(self.saved_name, self.storage_name)

    def test_later_write_does_not_see_previous_test_file(self):
        self.assertEqual(self.saved_name, self.storage_name)
