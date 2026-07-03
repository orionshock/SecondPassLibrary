from __future__ import annotations

from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[2]


class StartupScriptContractTests(SimpleTestCase):
    def test_powershell_dev_script_migrates_before_runserver(self):
        source = (ROOT / "scripts" / "start-dev.ps1").read_text(encoding="utf-8")

        self.assertIn('$ErrorActionPreference = "Stop"', source)
        self.assertIn("$env:PYTHON", source)
        self.assertIn('$env:DJANGO_DEBUG = if ($env:DJANGO_DEBUG)', source)
        self.assertIn("DJANGO_ALLOWED_HOSTS", source)
        self.assertIn("localhost,127.0.0.1,[::1]", source)
        self.assertLess(
            source.index("manage.py migrate --noinput"),
            source.index("manage.py runserver @args"),
        )
        self.assertIn("if ($LASTEXITCODE -ne 0)", source)

    def test_posix_dev_script_migrates_before_runserver(self):
        source = (ROOT / "scripts" / "start-dev.sh").read_text(encoding="utf-8")

        self.assertIn("set -e", source)
        self.assertIn('PYTHON="${PYTHON:-python}"', source)
        self.assertIn('export DJANGO_DEBUG="${DJANGO_DEBUG:-1}"', source)
        self.assertIn(
            'export DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-localhost,127.0.0.1,[::1]}"',
            source,
        )
        self.assertLess(
            source.index("manage.py migrate --noinput"),
            source.index('manage.py runserver "$@"'),
        )

    def test_posix_production_script_prepares_database_and_static_before_gunicorn(self):
        source = (ROOT / "scripts" / "start-production.sh").read_text(encoding="utf-8")

        self.assertIn("set -e", source)
        self.assertIn('BIND="${BIND:-0.0.0.0:8000}"', source)
        self.assertIn('WEB_CONCURRENCY="${WEB_CONCURRENCY:-2}"', source)
        self.assertIn("export DJANGO_DEBUG=0", source)
        self.assertIn("GUNICORN_CONFIG", source)
        check_at = source.index("manage.py check --deploy")
        migrate_at = source.index("manage.py migrate --noinput")
        collectstatic_at = source.index("manage.py collectstatic --noinput")
        gunicorn_at = source.index("-m gunicorn")
        self.assertLess(check_at, migrate_at)
        self.assertLess(migrate_at, collectstatic_at)
        self.assertLess(collectstatic_at, gunicorn_at)
        self.assertIn("secondpass.wsgi:application", source)
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("gunicorn==", requirements)

    def test_powershell_production_script_matches_production_startup_contract(self):
        source = (ROOT / "scripts" / "start-production.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn('$ErrorActionPreference = "Stop"', source)
        self.assertIn('$Bind = if ($env:BIND)', source)
        self.assertIn('$WaitressThreads = if ($env:WAITRESS_THREADS)', source)
        self.assertIn('$env:DJANGO_DEBUG = "0"', source)
        check_at = source.index("manage.py check --deploy")
        migrate_at = source.index("manage.py migrate --noinput")
        collectstatic_at = source.index("manage.py collectstatic --noinput")
        waitress_at = source.index("-m waitress")
        self.assertLess(check_at, migrate_at)
        self.assertLess(migrate_at, collectstatic_at)
        self.assertLess(collectstatic_at, waitress_at)
        self.assertIn("--listen=$Bind", source)
        self.assertIn("--threads=$WaitressThreads", source)
        self.assertIn("secondpass.wsgi:application", source)
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("waitress==", requirements)

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

    def test_docs_describe_scripts_as_local_convenience_not_deployment_contract(self):
        docs = [
            ROOT / "README.md",
            ROOT / "docs" / "deployment.md",
        ]
        for path in docs:
            with self.subTest(path=path):
                normalized = " ".join(path.read_text(encoding="utf-8").split())
                self.assertIn("local/dev convenience", normalized)
                self.assertIn("Docker", normalized)

    def test_docs_explain_raw_runserver_requires_debug_opt_in(self):
        docs = [
            ROOT / "README.md",
            ROOT / "DEVELOPMENT.md",
            ROOT / "docs" / "development.md",
            ROOT / "docs" / "deployment.md",
        ]
        for path in docs:
            with self.subTest(path=path):
                normalized = " ".join(path.read_text(encoding="utf-8").split())
                self.assertIn("DJANGO_DEBUG=1", normalized)
                self.assertIn("runserver", normalized)
