from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import runpy
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from docker.write_image_version import write_image_version


class ImageReleaseMetadataTests(SimpleTestCase):
    def test_supplied_build_metadata_is_written_as_importable_python(self):
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "version.py"

            write_image_version(output_path, "v2.4.0-3-gabc123-dirty", "2026-09-13")
            namespace = runpy.run_path(str(output_path))

        self.assertEqual(namespace["SERVER_VERSION"], "v2.4.0-3-gabc123-dirty")
        self.assertEqual(namespace["SERVER_RELEASE_DATE"], "2026-09-13")

    def test_empty_build_date_uses_the_current_utc_date(self):
        before_write = datetime.now(timezone.utc).date().isoformat()
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "version.py"

            write_image_version(output_path, "live-dev-env")
            namespace = runpy.run_path(str(output_path))
        after_write = datetime.now(timezone.utc).date().isoformat()

        release_date = namespace["SERVER_RELEASE_DATE"]
        self.assertEqual(date.fromisoformat(release_date).isoformat(), release_date)
        self.assertIn(release_date, {before_write, after_write})
