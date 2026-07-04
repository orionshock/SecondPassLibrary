# Production startup

Second Pass Library's first-run setup works in development and production. The
database schema must exist before the web process accepts requests; the setup
wizard does not create tables from request handling.

## Single-instance startup

### Docker Compose

The first Docker path is intentionally small: one Django/Gunicorn container,
SQLite, and a bind-mounted `./userdata` directory.

First run:

```powershell
copy .env.example .env
copy compose.example.yml compose.yml
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
docker compose up --build
```

Edit `.env` before starting. Edit `compose.yml` if you need local port, volume,
or restart-policy changes. At minimum, set:

```text
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<generated secret>
DJANGO_ALLOWED_HOSTS=<hostnames-or-lan-ips>
SECOND_PASS_USERDATA_DIR=/app/userdata
SECOND_PASS_ENABLE_DJANGO_ADMIN=0
```

The example compose file uses `env_file: .env`, maps host port `8000` to the
container, and mounts `./userdata` at `/app/userdata`. Startup runs:

1. `python manage.py check --deploy`
2. `python manage.py migrate --noinput`
3. `python manage.py collectstatic --noinput`
4. `gunicorn secondpass.wsgi:application --bind 0.0.0.0:8000`

Docker does not auto-generate `DJANGO_SECRET_KEY`; settings fail fast if `.env`
is missing, unset, or still using the documented placeholder.

Application diagnostics, including library import diagnostics, are emitted
through standard stdout/stderr logging for container log capture. The app does
not manage a separate file-log directory under `userdata/`.

Update flow:

```powershell
git pull
docker compose up --build
```

Review `.env.example` during updates for newly added variables.
Review `compose.example.yml` during updates for any compose-template changes;
your local `compose.yml` is intentionally untracked.

Reverse proxy and TLS are outside this Docker setup. If serving through an
HTTPS reverse proxy, set `DJANGO_ALLOWED_HOSTS` to include the public host,
set `DJANGO_CSRF_TRUSTED_ORIGINS` to the public `https://` origin, set
`DJANGO_SECURE_COOKIES=1`, and set `DJANGO_TRUST_X_FORWARDED_PROTO=1` only
when the proxy strips untrusted forwarded headers and sets its own.

Do not directly expose the whole `userdata/media` directory through an external
web server. WhiteNoise serves static assets after `collectstatic`; covers are
served through the app's `/media/covers/` route; EPUB/book files should be
served only through authorized app endpoints.

Backups should include `userdata/` and the deployment secret values in `.env`.

### Windows local production-mode helper

Install the runtime dependencies, configure the environment, and run the
Windows local production-mode helper:

```powershell
.\scripts\start-local-production.ps1
```

The script fails fast and performs these steps in order:

1. `python manage.py check --deploy`
2. `python manage.py migrate --noinput`
3. `python manage.py collectstatic --noinput`
4. A WSGI server serving `secondpass.wsgi:application`

The PowerShell script is a local production-mode helper: it runs with
`DJANGO_DEBUG=0`, binds to `127.0.0.1:8000` by default, and fills local-safe
defaults for `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, CSRF trusted origins,
secure cookies, and forwarded-header trust. It is for localhost testing of
production-mode behavior, not a real deployment secrets source. These scripts
remain local/dev convenience helpers and manual smoke tools for now; Docker can
own its own boot script later. There is intentionally no POSIX shell startup
script right now. The local helper also silences Django's built-in HTTPS/HSTS
deploy warnings that do not apply to deliberate localhost HTTP testing.

Environment variables:

- `PYTHON`: Python executable, default `python`
- `DJANGO_SETTINGS_MODULE`: optional Django settings module override; inherited
  by migration, static collection, and Gunicorn processes
- `DJANGO_DEBUG`: production startup scripts force `0`
- `DJANGO_SECRET_KEY`: required when `DJANGO_DEBUG=0`
- `DJANGO_ALLOWED_HOSTS`: comma-separated allowed hostnames/IPs
- `DJANGO_CSRF_TRUSTED_ORIGINS`: comma-separated scheme-qualified origins for
  CSRF checks
- `DJANGO_TRUST_X_FORWARDED_PROTO`: set to `1` only behind a trusted reverse
  proxy that strips/sets `X-Forwarded-Proto`
- `DJANGO_USE_X_FORWARDED_HOST`: set to `1` only behind a trusted reverse proxy
  that strips/sets forwarded host headers
- `DJANGO_SECURE_COOKIES`: set to `1` for HTTPS deployments
- `SECOND_PASS_USERDATA_DIR`: runtime data directory, default `./userdata`
- `SECOND_PASS_ENABLE_DJANGO_ADMIN`: set to `1` to expose `/admin/`; deployment
  examples disable it with `0`
- `SECOND_PASS_SERVER_VERSION`: value published as `server_version` in
  `/.well-known/secondpass`, default `0.1.0-dev`
- `SECOND_PASS_SERVER_RELEASE`: value published as `server_release` in
  `/.well-known/secondpass`, default `pre-release`
- `SECOND_PASS_SERVER_RELEASE_DATE`: value published as `server_release_date`
  in `/.well-known/secondpass`, default `2026-07-03`
- `BIND`: server bind address, default `127.0.0.1:8000` for the PowerShell local
  production-mode helper
- `WAITRESS_THREADS`: PowerShell/Waitress thread count, default `4`

Minimum production environment:

```text
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<generated secret>
DJANGO_ALLOWED_HOSTS=<hostnames-or-lan-ips>
```

Generate a secret key with Django from the project environment:

```powershell
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Without the Windows virtualenv helper, run the same command with whatever
Python executable is active:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Use a unique secret per deployment. Keep it stable across restarts, do not
commit it to Git, and back it up with the rest of the deployment secrets.
Changing `DJANGO_SECRET_KEY` logs users out and invalidates Django-signed
tokens, cookies, and short-lived signed flows.

`DJANGO_ALLOWED_HOSTS` defaults to local-safe hosts:
`localhost,127.0.0.1,[::1]`. Production deployments should set it to the public
hostnames or LAN IPs that users will actually use. The wildcard `*` is available
only by explicit operator choice, for example `DJANGO_ALLOWED_HOSTS=*`; do not
treat wildcard hosts as the recommended hardened deployment posture. The
project deploy check warns when `DEBUG=False` and wildcard hosts are configured.

HTTPS reverse proxy example:

```text
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<generated secret>
DJANGO_ALLOWED_HOSTS=books.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://books.example.com
DJANGO_TRUST_X_FORWARDED_PROTO=1
DJANGO_SECURE_COOKIES=1
```

Direct HTTP LAN example:

```text
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<generated secret>
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,[::1],192.168.1.25
DJANGO_CSRF_TRUSTED_ORIGINS=
DJANGO_TRUST_X_FORWARDED_PROTO=0
DJANGO_USE_X_FORWARDED_HOST=0
DJANGO_SECURE_COOKIES=0
```

Do not enable forwarded-proxy trust unless the app is behind a trusted reverse
proxy that strips untrusted incoming forwarded headers and sets the replacement
headers itself. Direct HTTP LAN deployments may intentionally leave secure
cookies off. HTTPS reverse-proxy deployments should set
`DJANGO_SECURE_COOKIES=1` and enable `DJANGO_TRUST_X_FORWARDED_PROTO=1` only
when the proxy is trusted. The project deploy check warns if forwarded HTTPS
trust is enabled while both secure cookie settings are off.

`python manage.py check --deploy` may also report Django's built-in HTTPS and
HSTS warnings. Treat those as deployment-policy prompts: direct HTTP LAN and
reverse-proxy HTTPS deployments have different answers.

The Django admin is an operator/recovery hatch, not the Product UI. The settings
default and `.env.example` disable URL exposure with
`SECOND_PASS_ENABLE_DJANGO_ADMIN=0`; the local production helper sets it to `1`
for local operator testing. To expose `/admin/` in a trusted deployment, set
`SECOND_PASS_ENABLE_DJANGO_ADMIN=1` and restrict access outside the app where
practical: LAN-only access, VPN, reverse-proxy IP allowlisting, or equivalent
network controls. Disabling admin removes the `/admin/` URL route; it does not
remove admin classes or repair code. See `docs/admin.md` for admin-only repair
workflows.

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

WhiteNoise does not serve `MEDIA_ROOT` or any user/library data. Django serves
only the public cover namespace, `/media/covers/`, so Product UI book lists can
render covers in direct-server usage. Stored EPUB files under
`userdata/media/books/` are never served as raw media and must be delivered only
through explicit authenticated views/API endpoints. Do not point WhiteNoise at
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

Raw `python manage.py runserver` and raw WSGI server commands remain usable
only after migrations have been applied manually. The recommended startup path
is the appropriate wrapper script so migrations finish before the web server starts.
Raw local `runserver` also needs `DJANGO_DEBUG=1` if development static/media
behavior is expected; production-mode wrapper scripts force `DJANGO_DEBUG=0`.
