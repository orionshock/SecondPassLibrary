from __future__ import annotations

from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[2]


class DockerStartupContractTests(SimpleTestCase):
    def test_compose_uses_env_file_userdata_mount_loopback_port_and_healthcheck(self):
        source = (ROOT / "docker" / "compose.example.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("  secondpasslibrary:", source)
        self.assertNotIn("  app:", source)
        self.assertIn("context: ..", source)
        self.assertIn("dockerfile: docker/Dockerfile", source)
        self.assertIn("APP_UID: ${APP_UID:-1000}", source)
        self.assertIn("APP_GID: ${APP_GID:-1000}", source)
        self.assertIn("env_file:", source)
        self.assertIn("- .env", source)
        self.assertNotIn("SECOND_PASS_USERDATA_DIR: /app/userdata", source)
        self.assertIn("- ../userdata:/app/userdata", source)
        self.assertIn('- "127.0.0.1:8000:8000"', source)
        self.assertNotIn('- "8000:8000"', source)
        self.assertIn("healthcheck:", source)
        self.assertIn("urllib.request", source)
        self.assertIn("http://127.0.0.1:8000/api/v1/health/", source)

    def test_compose_does_not_define_reverse_proxy_services(self):
        source = (ROOT / "docker" / "compose.example.yml").read_text(
            encoding="utf-8"
        ).lower()

        self.assertNotIn("nginx", source)
        self.assertNotIn("caddy", source)
        self.assertNotIn("traefik", source)
        self.assertNotIn("letsencrypt", source)

    def test_docker_entrypoint_runs_startup_steps_in_order(self):
        source = (ROOT / "docker" / "entrypoint.sh").read_text(encoding="utf-8")

        self.assertIn("export SECOND_PASS_ENABLE_WHITENOISE=1", source)
        self.assertIn("SECOND_PASS_USERDATA_DIR must be set.", source)
        self.assertIn('"$SECOND_PASS_USERDATA_DIR/db"', source)
        self.assertIn('"$SECOND_PASS_USERDATA_DIR/media"', source)
        self.assertIn('"$SECOND_PASS_USERDATA_DIR/imports"', source)
        self.assertIn("Required userdata directory is not writable", source)
        self.assertIn("uid=$(id -u) gid=$(id -g)", source)
        check_at = source.index("manage.py check --deploy")
        migrate_at = source.index("manage.py migrate --noinput")
        collectstatic_at = source.index("manage.py collectstatic --noinput")
        uvicorn_at = source.index("python -m uvicorn secondpass.asgi:application")
        self.assertLess(check_at, migrate_at)
        self.assertLess(migrate_at, collectstatic_at)
        self.assertLess(collectstatic_at, uvicorn_at)
        self.assertIn("--host 0.0.0.0", source)
        self.assertIn("--port 8000", source)
        self.assertIn("--workers 1", source)
        self.assertIn("--no-access-log", source)
        self.assertNotIn("gunicorn", source.lower())

    def test_dockerfile_uses_runtime_requirements_entrypoint_and_not_windows_scripts(self):
        source = (ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("FROM python:3.13-slim", source)
        self.assertIn("ARG APP_UID=1000", source)
        self.assertIn("ARG APP_GID=1000", source)
        self.assertIn("groupadd", source)
        self.assertIn("useradd", source)
        self.assertIn("secondpass", source)
        self.assertIn("mkdir -p /app/userdata /app/var/static", source)
        self.assertIn("chown -R secondpass:secondpass /app/userdata /app/var", source)
        self.assertIn("USER secondpass", source)
        self.assertIn("COPY requirements.txt", source)
        self.assertIn("pip install --no-cache-dir -r requirements.txt", source)
        self.assertIn('ENTRYPOINT ["/app/docker/entrypoint.sh"]', source)
        self.assertNotIn("start-local-production.ps1", source)
        self.assertNotIn("scripts/", source)

    def test_dockerignore_excludes_local_state_and_windows_scripts(self):
        source = (ROOT / "docker" / "Dockerfile.dockerignore").read_text(
            encoding="utf-8"
        )

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
        source = (ROOT / "docker" / ".env.example").read_text(encoding="utf-8")

        self.assertIn("DJANGO_DEBUG=0", source)
        self.assertIn("APP_UID=1000", source)
        self.assertIn("APP_GID=1000", source)
        self.assertIn("DJANGO_SECRET_KEY=replace-me-with-a-generated-secret", source)
        self.assertIn(
            "DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,your-hostname-or-domain",
            source,
        )
        self.assertIn("DJANGO_CSRF_TRUSTED_ORIGINS=", source)
        self.assertIn("DJANGO_SECURE_COOKIES=0", source)
        self.assertIn("DJANGO_TRUST_X_FORWARDED_PROTO=0", source)
        self.assertIn("DJANGO_USE_X_FORWARDED_HOST=0", source)
        self.assertIn("SECOND_PASS_ENABLE_DJANGO_ADMIN=0", source)
        self.assertIn("SECOND_PASS_USERDATA_DIR=/app/userdata", source)
        self.assertIn("DJANGO_SILENCED_SYSTEM_CHECKS=", source)

    def test_gitignore_keeps_local_compose_file_untracked(self):
        source = (ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn("docker/compose.yml", source)
