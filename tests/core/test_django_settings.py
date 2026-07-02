from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[2]


class DjangoSettingsContractTests(SimpleTestCase):
    def test_debug_defaults_off_and_hosts_are_unrestricted_for_now(self):
        source = (ROOT / "secondpass" / "settings.py").read_text(encoding="utf-8")

        self.assertIn('DEBUG = _env_bool("DJANGO_DEBUG", False)', source)
        self.assertIn("*", settings.ALLOWED_HOSTS)

    def test_static_root_is_generated_artifact_outside_userdata(self):
        self.assertEqual(Path(settings.STATIC_ROOT), ROOT / "var" / "static")
        self.assertNotEqual(Path(settings.STATIC_ROOT).parent, settings.USERDATA_DIR)
