from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import TestCase, override_settings


class HealthCheckContractTests(TestCase):
    def _ready_paths(self, directory: str) -> tuple[Path, Path]:
        userdata = Path(directory) / "userdata"
        for name in ("db", "media", "imports"):
            (userdata / name).mkdir(parents=True, exist_ok=True)
        react_dist = Path(directory) / "react-dist"
        react_dist.mkdir()
        (react_dist / "index.html").write_text("<!doctype html>", encoding="utf-8")
        return userdata, react_dist

    def test_ready_response_checks_database_product_ui_and_userdata(self):
        with TemporaryDirectory() as directory:
            userdata, react_dist = self._ready_paths(directory)
            with override_settings(
                USERDATA_DIR=userdata,
                PRODUCT_UI_DIR=react_dist,
            ):
                response = self.client.get("/api/v1/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "checks": {
                    "database": True,
                    "product_ui": True,
                    "userdata": True,
                },
            },
        )

    def test_missing_react_index_is_unavailable(self):
        with TemporaryDirectory() as directory:
            userdata, _react_dist = self._ready_paths(directory)
            missing_dist = Path(directory) / "missing-react-dist"
            with override_settings(
                USERDATA_DIR=userdata,
                PRODUCT_UI_DIR=missing_dist,
            ):
                response = self.client.get("/api/v1/health/")

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["checks"]["product_ui"])

    def test_database_failure_is_unavailable(self):
        with TemporaryDirectory() as directory:
            userdata, react_dist = self._ready_paths(directory)
            with (
                override_settings(
                    USERDATA_DIR=userdata,
                    PRODUCT_UI_DIR=react_dist,
                ),
                patch("core.views._database_is_ready", return_value=False),
            ):
                response = self.client.get("/api/v1/health/")

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["checks"]["database"])

    def test_unwritable_userdata_is_unavailable(self):
        with TemporaryDirectory() as directory:
            userdata, react_dist = self._ready_paths(directory)
            with (
                override_settings(
                    USERDATA_DIR=userdata,
                    PRODUCT_UI_DIR=react_dist,
                ),
                patch("core.views.os.access", return_value=False),
            ):
                response = self.client.get("/api/v1/health/")

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["checks"]["userdata"])
