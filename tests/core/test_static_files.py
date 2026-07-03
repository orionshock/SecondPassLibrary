from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from secondpass.settings import _staticfiles_backend


ROOT = Path(__file__).resolve().parents[2]


class WhiteNoiseStaticFilesTests(SimpleTestCase):
    def test_whitenoise_dependency_is_declared(self):
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

        self.assertIn("whitenoise==", requirements)

    def test_whitenoise_middleware_follows_security_middleware(self):
        security_index = settings.MIDDLEWARE.index(
            "django.middleware.security.SecurityMiddleware"
        )
        whitenoise_index = settings.MIDDLEWARE.index(
            "whitenoise.middleware.WhiteNoiseMiddleware"
        )

        self.assertEqual(whitenoise_index, security_index + 1)

    def test_static_root_and_production_whitenoise_storage_are_configured(self):
        self.assertTrue(settings.STATIC_ROOT)
        self.assertEqual(Path(settings.STATIC_ROOT), ROOT / "var" / "static")
        self.assertFalse(Path(settings.STATIC_ROOT).is_relative_to(ROOT / "userdata"))
        self.assertEqual(settings.STATIC_URL, "/static/")
        self.assertEqual(
            _staticfiles_backend(debug=False),
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
        )
        self.assertEqual(
            _staticfiles_backend(debug=True),
            "django.contrib.staticfiles.storage.StaticFilesStorage",
        )

    def test_production_startup_collects_static_before_wsgi_server(self):
        script_servers = {
            "scripts/start-local-production.ps1": "-m waitress",
            "docker/entrypoint.sh": "gunicorn secondpass.wsgi:application",
        }
        for script_name, server_marker in script_servers.items():
            with self.subTest(script_name=script_name):
                source = (ROOT / script_name).read_text(
                    encoding="utf-8"
                )

                self.assertLess(
                    source.index("manage.py collectstatic --noinput"),
                    source.index(server_marker),
                )

    def test_deployment_docs_keep_static_and_protected_data_separate(self):
        deployment = (ROOT / "docs" / "deployment.md").read_text(encoding="utf-8")
        normalized = " ".join(deployment.split())

        self.assertIn(
            "WhiteNoise serves only application assets under `/static/`",
            normalized,
        )
        self.assertIn("`STATIC_ROOT` at `var/static/`", normalized)
        self.assertIn("`WHITENOISE_MANIFEST_STRICT=False` is intentional", normalized)
        self.assertIn("generated deploy artifact", normalized)
        self.assertIn("Back up `userdata/`", normalized)
        self.assertIn("do not include it in normal backups", normalized)
        self.assertIn("WhiteNoise does not serve `MEDIA_ROOT`", normalized)
        self.assertIn("Django serves only the public cover namespace", normalized)
        self.assertIn("never served as raw media", normalized)
        self.assertIn(
            "Stored EPUB files under `userdata/media/books/`",
            normalized,
        )

    def test_deployment_docs_mark_permissive_hosts_as_temporary(self):
        deployment = (ROOT / "docs" / "deployment.md").read_text(encoding="utf-8")
        normalized = " ".join(deployment.split())

        self.assertIn("`DJANGO_ALLOWED_HOSTS`", normalized)
        self.assertIn("wildcard `*` is available only by explicit operator choice", normalized)
        self.assertIn("`DJANGO_CSRF_TRUSTED_ORIGINS`", normalized)
        self.assertIn("`DJANGO_TRUST_X_FORWARDED_PROTO`", normalized)
        self.assertIn("`DJANGO_USE_X_FORWARDED_HOST`", normalized)
        self.assertIn("`DJANGO_SECURE_COOKIES`", normalized)

    def test_deployment_docs_explain_cors_contract(self):
        deployment = (ROOT / "docs" / "deployment.md").read_text(encoding="utf-8")
        normalized = " ".join(deployment.split())

        self.assertIn("CORS remains open for `/api/` and `/.well-known/`", normalized)
        self.assertIn("credentials disabled", normalized)
        self.assertIn("independent bearer-token browser clients", normalized)
        self.assertIn("`DJANGO_ALLOWED_HOSTS`", normalized)
