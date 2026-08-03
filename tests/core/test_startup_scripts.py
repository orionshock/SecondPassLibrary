from __future__ import annotations

from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[2]


class DockerStartupContractTests(SimpleTestCase):
    def test_compose_uses_required_environment_bind_mount_and_bounded_port(self):
        source = (ROOT / "docker" / "compose.example.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("  secondpasslibrary:", source)
        self.assertNotIn("  app:", source)
        self.assertIn("context: ..", source)
        self.assertIn("dockerfile: docker/Dockerfile", source)
        self.assertIn("APP_UID: 1000", source)
        self.assertIn("APP_GID: 1000", source)
        self.assertIn("env_file:", source)
        self.assertIn("- .env", source)
        self.assertIn("- ../userdata:/app/userdata", source)
        self.assertNotIn("secondpass_userdata", source)
        self.assertIn('- "127.0.0.1:8000:8000"', source)
        self.assertNotIn('- "8000:8000"', source)
        self.assertIn("healthcheck:", source)
        self.assertIn("urllib.request", source)
        self.assertIn("http://127.0.0.1:8000/api/v1/health/", source)
        self.assertIn("os.environ['DJANGO_ALLOWED_HOSTS'].split(',')[0]", source)
        self.assertIn("headers={'Host': host}", source)
        self.assertIn("restart: unless-stopped", source)

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
        self.assertIn(
            "SECOND_PASS_USERDATA_DIR must be /app/userdata in Docker.", source
        )
        self.assertIn('"$SECOND_PASS_USERDATA_DIR/db"', source)
        self.assertIn('"$SECOND_PASS_USERDATA_DIR/media"', source)
        self.assertIn('"$SECOND_PASS_USERDATA_DIR/imports"', source)
        self.assertIn("Required userdata directory is not writable", source)
        self.assertIn("gosu secondpass id -u", source)
        check_at = source.index("manage.py check --deploy")
        migrate_at = source.index("manage.py migrate --noinput")
        uvicorn_at = source.index("python -m uvicorn secondpass.asgi:application")
        self.assertLess(check_at, migrate_at)
        self.assertLess(migrate_at, uvicorn_at)
        self.assertNotIn("collectstatic", source)
        self.assertIn("exec gosu secondpass", source)
        self.assertIn("--host 0.0.0.0", source)
        self.assertIn("--port 8000", source)
        self.assertIn("--workers 1", source)
        self.assertIn("--no-access-log", source)
        self.assertNotIn("gunicorn", source.lower())

    def test_dockerfile_has_cached_build_stages_and_minimal_runtime_copy(self):
        source = (ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("AS frontend-dependencies", source)
        self.assertIn("AS frontend-build", source)
        self.assertIn("AS python-runtime-dependencies", source)
        self.assertIn("AS static-collection", source)
        self.assertIn("AS runtime", source)
        self.assertIn("npm ci", source)
        self.assertIn("--mount=type=cache,target=/root/.npm", source)
        self.assertIn("npm run build", source)
        self.assertIn("--mount=type=cache,target=/root/.cache/pip", source)
        self.assertIn("python manage.py collectstatic --noinput --clear", source)
        self.assertIn("ARG APP_UID=1000", source)
        self.assertIn("ARG APP_GID=1000", source)
        self.assertIn("groupadd", source)
        self.assertIn("useradd", source)
        self.assertIn("secondpass", source)
        self.assertIn("COPY requirements.txt", source)
        self.assertIn("COPY --from=static-collection /app/var/static/ var/static/", source)
        self.assertIn(
            "COPY --from=static-collection /app/web/react/dist/index.html web/react/dist/index.html",
            source,
        )
        self.assertIn('ENTRYPOINT ["/app/docker/entrypoint.sh"]', source)
        self.assertNotIn("start-local-production.ps1", source)
        self.assertNotIn("COPY . .", source)

    def test_dockerignore_excludes_local_state_and_windows_scripts(self):
        source = (ROOT / "docker" / "Dockerfile.dockerignore").read_text(
            encoding="utf-8"
        )

        for pattern in (
            ".env.*",
            ".venv",
            "__pycache__/",
            "node_modules/",
            "web/react/dist/",
            "web/react/coverage/",
            "*.tsbuildinfo",
            "*.map",
            "tests/",
            "docs/",
            "requirements-dev.txt",
            "*.sqlite3",
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
        self.assertNotIn("APP_UID=", source)
        self.assertNotIn("APP_GID=", source)
        self.assertIn("DJANGO_SECRET_KEY=replace-me-with-a-generated-secret", source)
        self.assertIn("DJANGO_ALLOWED_HOSTS=your-hostname-or-domain", source)
        self.assertIn("DJANGO_CSRF_TRUSTED_ORIGINS=", source)
        self.assertIn("DJANGO_SECURE_COOKIES=0", source)
        self.assertIn("DJANGO_TRUST_X_FORWARDED_PROTO=0", source)
        self.assertIn("DJANGO_USE_X_FORWARDED_HOST=0", source)
        self.assertIn("SECOND_PASS_ENABLE_DJANGO_ADMIN=0", source)
        self.assertIn("SECOND_PASS_USERDATA_DIR=/app/userdata", source)
        self.assertIn("DJANGO_SILENCED_SYSTEM_CHECKS=", source)

    def test_runtime_requirements_exclude_test_dependencies(self):
        runtime = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        development = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")

        self.assertNotIn("pytest==", runtime)
        self.assertNotIn("pytest-django==", runtime)
        self.assertIn("pytest==", development)
        self.assertIn("pytest-django==", development)

    def test_gitignore_keeps_local_compose_file_untracked(self):
        source = (ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn("docker/compose.yml", source)
