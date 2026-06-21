from __future__ import annotations

from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[2]


class StartupScriptContractTests(SimpleTestCase):
    def test_powershell_dev_script_migrates_before_runserver(self):
        source = (ROOT / "scripts" / "start-dev.ps1").read_text(encoding="utf-8")

        self.assertIn('$ErrorActionPreference = "Stop"', source)
        self.assertIn("$env:PYTHON", source)
        self.assertLess(
            source.index("manage.py migrate --noinput"),
            source.index("manage.py runserver @args"),
        )
        self.assertIn("if ($LASTEXITCODE -ne 0)", source)

    def test_posix_dev_script_migrates_before_runserver(self):
        source = (ROOT / "scripts" / "start-dev.sh").read_text(encoding="utf-8")

        self.assertIn("set -e", source)
        self.assertIn('PYTHON="${PYTHON:-python}"', source)
        self.assertLess(
            source.index("manage.py migrate --noinput"),
            source.index('manage.py runserver "$@"'),
        )

    def test_production_script_prepares_database_and_static_before_gunicorn(self):
        source = (ROOT / "scripts" / "start-production.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("set -e", source)
        self.assertIn('BIND="${BIND:-0.0.0.0:8000}"', source)
        self.assertIn('WEB_CONCURRENCY="${WEB_CONCURRENCY:-2}"', source)
        self.assertIn("GUNICORN_CONFIG", source)
        migrate_at = source.index("manage.py migrate --noinput")
        collectstatic_at = source.index("manage.py collectstatic --noinput")
        gunicorn_at = source.index("-m gunicorn")
        self.assertLess(migrate_at, collectstatic_at)
        self.assertLess(collectstatic_at, gunicorn_at)
        self.assertIn("secondpass.wsgi:application", source)
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("gunicorn==", requirements)

    def test_documentation_does_not_reference_removed_devserver_command(self):
        docs = [
            ROOT / "README.md",
            ROOT / "DEVELOPMENT.md",
            ROOT / "docs" / "development.md",
            ROOT / "docs" / "deployment.md",
        ]
        for path in docs:
            with self.subTest(path=path):
                self.assertNotIn(
                    "manage.py devserver",
                    path.read_text(encoding="utf-8"),
                )

    def test_deployment_docs_describe_cross_mode_setup(self):
        deployment = (ROOT / "docs" / "deployment.md").read_text(encoding="utf-8")
        normalized = " ".join(deployment.split())

        self.assertIn("development and production", normalized)
        self.assertIn("setup wizard does not create tables", normalized)
        self.assertIn("seed_dev_users", normalized)
