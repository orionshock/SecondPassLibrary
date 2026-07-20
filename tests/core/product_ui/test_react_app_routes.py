from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.staticfiles.finders import FileSystemFinder
from django.test import override_settings
from django.urls import resolve

from tests.core.product_ui.helpers import ProductUiTestCase
from web.views import react_app


class ReactAppRouteContractTests(ProductUiTestCase):
    def test_missing_build_returns_bounded_service_unavailable(self):
        with TemporaryDirectory() as directory:
            missing_dist = Path(directory) / "missing"
            with override_settings(REACT_UI_DIST_DIR=missing_dist):
                response = self.client.get("/app/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertContains(response, "npm.cmd run build", status_code=503)
        self.assertNotContains(response, str(missing_dist), status_code=503)

    def test_root_and_deep_link_serve_the_same_built_shell(self):
        with TemporaryDirectory() as directory:
            dist = Path(directory)
            shell = '<!doctype html><div id="root"></div><script src="/static/react/assets/app.js"></script>'
            (dist / "index.html").write_text(shell, encoding="utf-8")
            with override_settings(REACT_UI_DIST_DIR=dist):
                root = self.client.get("/app/")
                deep_link = self.client.get("/app/library/books/example/")

        self.assertEqual(root.status_code, 200)
        self.assertEqual(deep_link.status_code, 200)
        self.assertEqual(root.content, deep_link.content)
        self.assertEqual(root["Cache-Control"], "no-cache")
        self.assertContains(root, "/static/react/assets/app.js")

    def test_existing_routes_are_not_captured_by_react(self):
        self.client.force_login(self.bootstrap_owner)

        self.assertIs(resolve("/app/").func, react_app)
        self.assertIsNot(resolve("/").func, react_app)
        self.assertIsNot(resolve("/legacy/").func, react_app)
        self.assertIsNot(resolve("/api/v1/health/").func, react_app)
        self.assertEqual(self.client.get("/").status_code, 302)
        self.assertEqual(self.client.get("/legacy/").status_code, 302)
        self.assertEqual(self.client.get("/api/v1/health/").status_code, 200)

    def test_react_static_prefix_is_discoverable(self):
        with TemporaryDirectory() as directory:
            dist = Path(directory)
            asset = dist / "assets" / "app.js"
            asset.parent.mkdir()
            asset.write_text("export {};", encoding="utf-8")
            with override_settings(STATICFILES_DIRS=[("react", dist)]):
                discovered = FileSystemFinder().find(str(Path("react") / "assets" / "app.js"))

        self.assertEqual(Path(discovered), asset)
