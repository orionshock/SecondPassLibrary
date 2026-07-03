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

    def test_powershell_local_production_script_sets_local_prod_defaults(self):
        source = (ROOT / "scripts" / "start-local-production.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn('$ErrorActionPreference = "Stop"', source)
        self.assertIn('"127.0.0.1:8000"', source)
        self.assertIn('$WaitressThreads = if ($env:WAITRESS_THREADS)', source)
        self.assertIn('$env:DJANGO_DEBUG = "0"', source)
        self.assertIn("DJANGO_SECRET_KEY", source)
        self.assertIn("secondpass-local-production-mode-not-for-real-deployments", source)
        self.assertIn("DJANGO_ALLOWED_HOSTS", source)
        self.assertIn("localhost,127.0.0.1,[::1]", source)
        self.assertIn("DJANGO_CSRF_TRUSTED_ORIGINS", source)
        self.assertIn("http://localhost:8000,http://127.0.0.1:8000", source)
        self.assertIn("DJANGO_SECURE_COOKIES", source)
        self.assertIn("DJANGO_TRUST_X_FORWARDED_PROTO", source)
        self.assertIn("DJANGO_USE_X_FORWARDED_HOST", source)
        self.assertIn("DJANGO_SILENCED_SYSTEM_CHECKS", source)
        self.assertIn("security.W004,security.W008,security.W012,security.W016", source)
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

    def test_scripts_are_windows_native_only_for_now(self):
        scripts = {path.name for path in (ROOT / "scripts").iterdir()}

        self.assertIn("start-dev.ps1", scripts)
        self.assertIn("start-local-production.ps1", scripts)
        self.assertNotIn("start-dev.sh", scripts)
        self.assertNotIn("start-production.sh", scripts)

    def test_documentation_does_not_reference_removed_devserver_command(self):
        docs = [
            ROOT / "README.md",
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
            ROOT / "docs" / "development.md",
            ROOT / "docs" / "deployment.md",
        ]
        for path in docs:
            with self.subTest(path=path):
                normalized = " ".join(path.read_text(encoding="utf-8").split())
                self.assertIn("DJANGO_DEBUG=1", normalized)
                self.assertIn("runserver", normalized)


class DockerStartupContractTests(SimpleTestCase):
    def test_compose_uses_env_file_userdata_mount_and_port_8000(self):
        source = (ROOT / "compose.yml").read_text(encoding="utf-8")

        self.assertIn("env_file:", source)
        self.assertIn("- .env", source)
        self.assertIn("SECOND_PASS_USERDATA_DIR: /app/userdata", source)
        self.assertIn("- ./userdata:/app/userdata", source)
        self.assertIn('- "8000:8000"', source)

    def test_compose_does_not_define_reverse_proxy_services(self):
        source = (ROOT / "compose.yml").read_text(encoding="utf-8").lower()

        self.assertNotIn("nginx", source)
        self.assertNotIn("caddy", source)
        self.assertNotIn("traefik", source)
        self.assertNotIn("letsencrypt", source)

    def test_docker_entrypoint_runs_startup_steps_in_order(self):
        source = (ROOT / "docker" / "entrypoint.sh").read_text(encoding="utf-8")

        check_at = source.index("manage.py check --deploy")
        migrate_at = source.index("manage.py migrate --noinput")
        collectstatic_at = source.index("manage.py collectstatic --noinput")
        gunicorn_at = source.index("gunicorn secondpass.wsgi:application")
        self.assertLess(check_at, migrate_at)
        self.assertLess(migrate_at, collectstatic_at)
        self.assertLess(collectstatic_at, gunicorn_at)
        self.assertIn("--bind 0.0.0.0:8000", source)

    def test_dockerfile_uses_requirements_gunicorn_entrypoint_and_not_windows_scripts(self):
        source = (ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("FROM python:3.13-slim", source)
        self.assertIn("COPY requirements.txt", source)
        self.assertIn("pip install --no-cache-dir -r requirements.txt", source)
        self.assertIn('ENTRYPOINT ["/app/docker/entrypoint.sh"]', source)
        self.assertNotIn("start-local-production.ps1", source)
        self.assertNotIn("scripts/", source)

    def test_dockerignore_excludes_local_state_and_windows_scripts(self):
        source = (ROOT / ".dockerignore").read_text(encoding="utf-8")

        for pattern in (
            ".env",
            ".venv",
            "__pycache__/",
            "node_modules/",
            "TestFiles/",
            "out/",
            "userdata/",
            "var/",
            ".ruff_cache",
            "scripts/",
        ):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, source)

    def test_env_example_documents_docker_environment_contract(self):
        source = (ROOT / ".env.example").read_text(encoding="utf-8")

        self.assertIn("DJANGO_DEBUG=0", source)
        self.assertIn("DJANGO_SECRET_KEY=replace-me-with-a-generated-secret", source)
        self.assertIn(
            "DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,your-hostname-or-domain",
            source,
        )
        self.assertIn("DJANGO_CSRF_TRUSTED_ORIGINS=", source)
        self.assertIn("DJANGO_SECURE_COOKIES=0", source)
        self.assertIn("DJANGO_TRUST_X_FORWARDED_PROTO=0", source)
        self.assertIn("DJANGO_USE_X_FORWARDED_HOST=0", source)
        self.assertIn("SECOND_PASS_USERDATA_DIR=/app/userdata", source)
        self.assertIn("DJANGO_SILENCED_SYSTEM_CHECKS=", source)
