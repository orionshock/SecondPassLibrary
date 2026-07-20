from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.finders import FileSystemFinder
from django.test import TestCase, override_settings
from django.urls import Resolver404, resolve

from web.views import react_app


class ReactRootRouteContractTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser(
            username="react-owner",
            email="react-owner@example.test",
            password="pw",
        )

    def _built_dist(self, directory: str) -> Path:
        dist = Path(directory)
        (dist / "index.html").write_text(
            '<!doctype html><div id="root"></div><script src="/static/react/assets/app.js"></script>',
            encoding="utf-8",
        )
        return dist

    def test_unauthenticated_root_and_deep_link_redirect_to_user_login(self):
        for path in ("/", "/library/books/example/", "/server"):
            with self.subTest(path=path):
                response = self.client.get(path, follow=False)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response["Location"], f"/login/?next={path}")

    def test_authenticated_root_and_deep_link_serve_the_same_shell(self):
        self.client.force_login(self.owner)
        with TemporaryDirectory() as directory:
            dist = self._built_dist(directory)
            with override_settings(REACT_UI_DIST_DIR=dist):
                root = self.client.get("/")
                deep_link = self.client.get("/library/books/example/")
                server_link = self.client.get("/server")

        self.assertEqual(root.status_code, 200)
        self.assertEqual(deep_link.status_code, 200)
        self.assertEqual(root.content, deep_link.content)
        self.assertEqual(root.content, server_link.content)
        self.assertEqual(root["Cache-Control"], "no-cache")

    def test_get_logout_clears_session_and_redirects_to_login(self):
        self.client.force_login(self.owner)

        response = self.client.get("/logout/")

        self.assertRedirects(response, "/login/", fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_missing_build_returns_bounded_service_unavailable_after_auth(self):
        self.client.force_login(self.owner)
        with TemporaryDirectory() as directory:
            missing_dist = Path(directory) / "missing"
            with override_settings(REACT_UI_DIST_DIR=missing_dist):
                response = self.client.get("/")

        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "npm.cmd run build", status_code=503)
        self.assertNotContains(response, str(missing_dist), status_code=503)

    def test_service_routes_are_not_captured_by_react(self):
        self.assertIs(resolve("/").func, react_app)
        self.assertIsNot(resolve("/api/v1/health/").func, react_app)
        self.assertIsNot(resolve("/media/covers/missing.png").func, react_app)
        for path in (
            "/app/",
            "/legacy/",
            "/client-api/authorize/",
            "/api-auth/login/",
            "/reading/",
        ):
            with self.subTest(path=path), self.assertRaises(Resolver404):
                resolve(path)
        with self.assertRaises(Resolver404):
            resolve("/static/web/app.css")
        self.assertEqual(self.client.get("/api/v1/health/").status_code, 200)

    def test_react_static_prefix_is_discoverable(self):
        with TemporaryDirectory() as directory:
            dist = Path(directory)
            asset = dist / "assets" / "app.js"
            asset.parent.mkdir()
            asset.write_text("export {};", encoding="utf-8")
            with override_settings(STATICFILES_DIRS=[("react", dist)]):
                discovered = FileSystemFinder().find(
                    str(Path("react") / "assets" / "app.js")
                )

        self.assertEqual(Path(discovered), asset)
