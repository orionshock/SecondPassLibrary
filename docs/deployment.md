# Deployment

Second Pass Library supports a single-instance Docker Compose deployment with
SQLite and a bind-mounted runtime directory. The Windows production-mode
helper is available for local operator testing; it is not a substitute for a
managed deployment.

The database schema must exist before the web process accepts requests. The
first-run setup wizard configures the application after migrations; it does not
create database tables from request handling.

## Fresh database requirement

The first-party migration history has been flattened into new initial
migrations. Databases created from the earlier migration history are not
compatible with this release. Create a fresh database and apply the current
initial migrations. Do not use `--fake-initial` or otherwise mark them as
applied to an old database.

Retaining `userdata/media/` does not restore its database records or
relationships. EPUBs must be re-imported through a supported import path after
the fresh database is initialized. Restore a complete, mutually consistent
database and `userdata/` backup together; do not combine an old database with
unrelated media files.

## Docker Compose

The example deployment runs one Django/Uvicorn service named
`secondpasslibrary`, uses SQLite, and bind-mounts `./userdata` at
`/app/userdata`. Uvicorn serves `secondpass.asgi:application` directly with one
worker. The container entrypoint always enables WhiteNoise; this is not an
operator-configurable Docker setting. Reverse proxy and TLS configuration
remain deployment-owned.

First run:

```powershell
copy docker\.env.example docker\.env
copy docker\compose.example.yml docker\compose.yml
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
docker compose -f docker/compose.yml up --build
```

Set at least these values in `.env`:

```text
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<generated-secret>
DJANGO_ALLOWED_HOSTS=<hostnames-or-lan-ips>
SECOND_PASS_USERDATA_DIR=/app/userdata
SECOND_PASS_ENABLE_DJANGO_ADMIN=0
SECOND_PASS_READING_CLIENT_BASE_URL=
```

Set `SECOND_PASS_READING_CLIENT_BASE_URL` to an HTTP(S) Reading Client root URL
only when deployment configuration should override and lock the editable Server
Settings value. Leave it blank to use the stored setting.

The image runs as the non-root `secondpass` user. Its default UID/GID is
`1000:1000`; set `APP_UID` and `APP_GID` before building if the host requires
different ownership. On native Linux, prepare the bind mount accordingly:

```bash
mkdir -p userdata
sudo chown -R 1000:1000 userdata
```

On Windows Docker Desktop, bind-mount permissions are normally handled by
Docker Desktop.

The example binds host `127.0.0.1:8000` for a reverse proxy on the same host.
Direct LAN or public exposure requires an intentional `docker/compose.yml`
change.
Startup performs:

1. `python manage.py check --deploy`
2. `python manage.py migrate --noinput`
3. `python manage.py collectstatic --noinput`
4. `python -m uvicorn secondpass.asgi:application --host 0.0.0.0 --port 8000 --workers 1 --no-access-log`

The healthcheck calls `/api/v1/health/` inside the container. Docker does not
generate `DJANGO_SECRET_KEY`; startup fails when it is missing or still uses
the documented placeholder. Uvicorn access logs are disabled to match the
Windows production-like path and avoid routine request noise; startup,
shutdown, application, and error output still use stdout/stderr.

Update with:

```powershell
git pull
docker compose -f docker/compose.yml up --build
```

Review `docker/.env.example` and `docker/compose.example.yml` during updates.
Local `docker/.env` and `docker/compose.yml` files remain deployment-owned and
untracked.

## Runtime data and backups

Durable runtime state belongs under `userdata/`:

- `userdata/db/` contains the SQLite database;
- `userdata/media/` contains EPUB and cover files;
- `userdata/imports/` contains temporary or staged import data.

Back up the complete `userdata/` directory and stable deployment secrets.
Database and durable media must be restored as one consistent snapshot.
Generated `var/static/` output is not user data and can be regenerated with
`collectstatic`.

Do not expose `userdata/` or all of `userdata/media/` through a web server.
WhiteNoise serves packaged application assets under `/static/`. Django exposes
only `/media/covers/` as public display assets. Stored EPUBs are protected and
downloads are authenticated application/API responses. This static and media
behavior is the same under direct Uvicorn as it was under the previous runtime.

## Reverse proxy and HTTPS

For an HTTPS reverse proxy, configure the public host and origin, enable secure
cookies, and trust forwarded protocol only when the proxy removes untrusted
incoming headers and supplies its own:

```text
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<generated-secret>
DJANGO_ALLOWED_HOSTS=books.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://books.example.com
DJANGO_TRUST_X_FORWARDED_PROTO=1
DJANGO_SECURE_COOKIES=1
```

A direct HTTP LAN deployment may leave secure cookies and forwarded-header
trust disabled. Never enable forwarded host/protocol trust for an untrusted or
pass-through proxy. Django's deploy check may report HTTPS/HSTS warnings whose
resolution depends on the deployment boundary.

Uvicorn retains its safe proxy-header defaults. The supplied startup commands
do not broaden which proxy addresses are trusted. If a deployment needs a
different trusted proxy address or network, configure that deliberately at the
deployment boundary together with Django's forwarded-protocol and forwarded-
host settings.

## Service Hatch and logging

Django Admin is the Service Hatch for advanced settings and recovery. Its URL
is registered only when `SECOND_PASS_ENABLE_DJANGO_ADMIN=1`. Keep it disabled
unless needed, and restrict an enabled Service Hatch with appropriate network
controls such as LAN/VPN access or reverse-proxy allowlisting. Disabling the
route does not remove its registered models or recovery operations.

Application log level is controlled by **Application Log Level** in the Service
Hatch. Normal container diagnostics go to stdout/stderr; the application does
not manage a log directory under `userdata/`. Prefer homelab-readable,
bounded operational summaries. Logs must not contain passwords, authentication
or client tokens, email addresses, marginalia content, raw payloads, unsafe or
absolute paths, file hashes, or other storage identifiers.

## Shelf cleanup scheduling

Unavailable items on personal shelves are retained until explicit cleanup.
`cleanup_shelves` is a host-scheduled maintenance command, not implicit
application cleanup. It is a dry run unless `--apply` is supplied:

```bash
docker compose -f docker/compose.yml exec -T secondpasslibrary python manage.py cleanup_shelves
docker compose -f docker/compose.yml exec -T secondpasslibrary python manage.py cleanup_shelves --apply
```

The apply form permanently removes unavailable personal-shelf rows and compacts
the remaining positions. It does not clean group shelves. Run the dry form
before applying when reviewing a deployment manually.

A host cron example:

```cron
0 3 * * * root cd /srv/second-pass-library && /usr/bin/docker compose -f docker/compose.yml exec -T secondpasslibrary python manage.py cleanup_shelves --apply
```

Replace the directory with the repository directory containing
`docker/compose.yml`.
The scheduler account must be allowed to use Docker. Windows deployments can
invoke the equivalent command from Task Scheduler.

## Windows local production-mode helper

For localhost production-mode checks:

```powershell
.\scripts\start-local-production.ps1
```

The helper uses `DJANGO_DEBUG=0`, runs deploy checks, migrations, and static
collection, then starts one direct Uvicorn worker with
`secondpass.asgi:application` on `127.0.0.1:8000` by default. Access logs are
disabled, matching Docker. It supplies local-safe defaults and is not a
production secret-management mechanism. It always enables Django Admin for
local operator use.

The Python executable, bind host and port, and complete application environment
are defined near the top of the script. Values inherited from the calling shell
are replaced. Edit the script directly when a different local configuration is
needed. This rule applies only to the local helper; Docker deployments continue
to use `.env` and the Compose build arguments documented above.

Normal development remains on Django's `runserver`. Raw server commands are
usable after migrations have been applied manually. Prefer the provided
startup paths so schema checks and migrations finish before the web process
starts.
