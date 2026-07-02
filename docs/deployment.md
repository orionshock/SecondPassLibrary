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

The scripts are local/dev convenience helpers and manual smoke tools for now,
not the final deployment orchestration contract. Real deployment environment
wiring and process supervision can wait for Docker.

Environment variables:

- `PYTHON`: Python executable, default `python`
- `DJANGO_SETTINGS_MODULE`: optional Django settings module override; inherited
  by migration, static collection, and Gunicorn processes
- `DJANGO_DEBUG`: production startup scripts force `0`
- `DJANGO_ALLOWED_HOSTS`: comma-separated allowed hostnames/IPs
- `DJANGO_CSRF_TRUSTED_ORIGINS`: comma-separated scheme-qualified origins for
  CSRF checks
- `DJANGO_TRUST_X_FORWARDED_PROTO`: set to `1` only behind a trusted reverse
  proxy that strips/sets `X-Forwarded-Proto`
- `DJANGO_USE_X_FORWARDED_HOST`: set to `1` only behind a trusted reverse proxy
  that strips/sets forwarded host headers
- `DJANGO_SECURE_COOKIES`: set to `1` for HTTPS deployments
- `BIND`: server bind address, default `0.0.0.0:8000`
- `WEB_CONCURRENCY`: POSIX/Gunicorn worker count, default `2`
- `GUNICORN_CONFIG`: optional POSIX/Gunicorn configuration file
- `WAITRESS_THREADS`: PowerShell/Waitress thread count, default `4`

`DJANGO_ALLOWED_HOSTS` defaults to local-safe hosts:
`localhost,127.0.0.1,[::1]`. Production deployments should set it to the public
hostnames or LAN IPs that users will actually use. The wildcard `*` is available
only by explicit operator choice, for example `DJANGO_ALLOWED_HOSTS=*`; do not
treat wildcard hosts as the recommended hardened deployment posture.

HTTPS reverse proxy example:

```text
DJANGO_ALLOWED_HOSTS=books.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://books.example.com
DJANGO_TRUST_X_FORWARDED_PROTO=1
DJANGO_SECURE_COOKIES=1
```

Direct HTTP LAN example:

```text
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,[::1],192.168.1.25
DJANGO_CSRF_TRUSTED_ORIGINS=
DJANGO_TRUST_X_FORWARDED_PROTO=0
DJANGO_USE_X_FORWARDED_HOST=0
DJANGO_SECURE_COOKIES=0
```

Do not enable forwarded-proxy trust unless the app is behind a trusted reverse
proxy that strips untrusted incoming forwarded headers and sets the replacement
headers itself.

CORS remains open for `/api/` and `/.well-known/` with credentials disabled.
This is for independent bearer-token browser clients such as the reading
client. The Product UI remains same-origin session/CSRF and is not CORS-open.

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
