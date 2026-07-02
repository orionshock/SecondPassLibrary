# Production startup

Second Pass Library's first-run setup works in development and production. The
database schema must exist before the web process accepts requests; the setup
wizard does not create tables from request handling.

## Single-instance startup

Install the runtime dependencies, configure the environment, and run:

```sh
sh scripts/start-production.sh
```

On PowerShell:

```powershell
.\scripts\start-production.ps1
```

The script fails fast and performs these steps in order:

1. `python manage.py migrate --noinput`
2. `python manage.py collectstatic --noinput`
3. A WSGI server serving `secondpass.wsgi:application`

Environment variables:

- `PYTHON`: Python executable, default `python`
- `DJANGO_SETTINGS_MODULE`: optional Django settings module override; inherited
  by migration, static collection, and Gunicorn processes
- `DJANGO_DEBUG`: production startup scripts force `0`
- `BIND`: server bind address, default `0.0.0.0:8000`
- `WEB_CONCURRENCY`: POSIX/Gunicorn worker count, default `2`
- `GUNICORN_CONFIG`: optional POSIX/Gunicorn configuration file
- `WAITRESS_THREADS`: PowerShell/Waitress thread count, default `4`

`ALLOWED_HOSTS` is currently permissive (`["*"]`) as a temporary deployment
posture while self-hosted setup hardens. Do not treat wildcard hosts as the
recommended long-term production configuration. The expected future shape is an
environment-driven setting such as `DJANGO_ALLOWED_HOSTS`.

WhiteNoise serves only application assets under `/static/` from the collected
`STATIC_ROOT` at `var/static/`: Product UI CSS, JavaScript, icons, favicon
assets, and other packaged static files. WhiteNoise runs inside the Django/WSGI
application, so a separate static-file web server is not required for these
assets.
Production (`DEBUG=False`) uses compressed manifest storage for hashed,
cacheable filenames. Development keeps Django's normal `runserver` static-file
behavior and does not require `collectstatic`.
`WHITENOISE_MANIFEST_STRICT=False` is intentional for now to reduce local and
offline production-mode friction while static references stabilize. Revisit it
later when stricter deployment checks are useful.

`var/static/` is a generated deploy artifact. It is safe to delete and
regenerate with `python manage.py collectstatic --noinput`; do not include it
in normal backups.

WhiteNoise does not serve `MEDIA_ROOT` or any user/library data. Books, EPUB
files, covers, imports, exports, or marginalia continue to use their existing
storage and authenticated Django/API paths. Do not point WhiteNoise at
`userdata/media/`, `userdata/imports/`, or any directory containing protected
content.
Back up `userdata/` for durable app state. Do not treat generated `var/static/`
files as backup-worthy state.

After the first startup, visit `/`. With a migrated database and no active
Django superuser, `/`, Product UI routes, and login direct to `/setup/`.
Complete setup to save the server name and optional description, configure the
Public group's display name and description, save the advanced-groups UI
preference, and create the first active staff/superuser, Manager profile, and
Public membership. The defaults are `Second Pass Library`, a blank server
description, `Common Room`, `Main Public Library Room for everyone`, and
advanced groups disabled. Common Room is the shared public library space
managed by librarians and managers. Advanced groups expose separate
curator-managed rooms without changing the underlying permission model.
Subsequent starts use normal login because the bootstrap Owner already exists.

`seed_dev_users` is an optional local development/demo command. It is not part
of production startup and is not required for normal first-run setup.

## Raw commands

Raw `python manage.py runserver` and raw `gunicorn` remain usable only after
migrations have been applied manually. The recommended startup path is the
appropriate wrapper script so migrations finish before the web server starts.
Raw local `runserver` also needs `DJANGO_DEBUG=1` if development static/media
behavior is expected; production wrapper scripts force `DJANGO_DEBUG=0`.
