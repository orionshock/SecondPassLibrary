# Deployment

Second Pass Library supports one Docker Compose application instance with
SQLite and persistent Docker storage. The image builds the React Product UI,
collects immutable static assets, applies migrations at container startup, and
runs Uvicorn directly. No host-side React build, migration, static collection,
directory creation, or ownership preparation is required.

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

The example runs one Django/Uvicorn service named `secondpasslibrary`, uses
SQLite, and mounts the named volume `secondpass_userdata` at `/app/userdata`.
The entrypoint initializes that storage before dropping privileges; Django and
Uvicorn run as the non-root `secondpass` user. Uvicorn serves
`secondpass.asgi:application` with exactly one worker. Do not scale this service
or increase its worker count while it uses SQLite.

The multi-stage image builds only `frontend/`, copies `backend/` into a prepared
runtime tree, places the React artifact at `web/product_ui/`, and runs
`collectstatic`. It then drops the source static directories and the copied
Product UI asset directory, retaining the Product UI index and one immutable
collected asset tree for WhiteNoise. Reverse proxy and TLS configuration remain
operator-owned.

From the repository root:

```powershell
copy docker\.env.example docker\.env
copy docker\compose.example.yml docker\compose.yml
docker compose -f docker/compose.yml up -d --build
```

Before starting, replace the secret and hostname placeholder in `docker/.env`.
These values are required:

```text
DJANGO_SECRET_KEY=<generated-secret>
DJANGO_ALLOWED_HOSTS=<hostnames-or-lan-ips>
```

The standard Docker image always sets `SECOND_PASS_USERDATA_DIR` to
`/app/userdata`; it is not an operator setting. The image initializes mounted
storage as UID/GID `1000:1000` by default. Advanced deployments may edit the
Docker build arguments in `docker/compose.yml`; they are deliberately not
runtime environment variables.

Optional values and defaults are documented inline in `docker/.env.example`.
Set `SECOND_PASS_READING_CLIENT_BASE_URL` to an HTTP(S) Reader Client root only
when deployment configuration should override and lock the editable Server
Settings value. Leave it blank to use the stored setting.

The example binds host `127.0.0.1:8000` for a reverse proxy on the same host.
Direct LAN or public exposure requires an intentional Compose port change. The
supplied Compose file does not provide TLS or a reverse proxy.
Startup performs:

1. `python manage.py check --deploy`
2. `python manage.py migrate --noinput`
3. `python -m uvicorn secondpass.asgi:application --host 0.0.0.0 --port 8000 --workers 1 --no-access-log`

The healthcheck calls `/api/v1/health/` with the first configured allowed host.
Readiness requires a working database query, the built React index, and writable
userdata/database/media/import directories. Docker does not generate
`DJANGO_SECRET_KEY`; startup fails when it is missing or uses the documented
placeholder. Uvicorn access logs are disabled; startup, shutdown, application,
and error output still use stdout/stderr.

Inspect status and logs with:

```powershell
docker compose -f docker/compose.yml ps
docker compose -f docker/compose.yml logs --tail 200 secondpasslibrary
docker inspect --format '{{json .State.Health}}' (docker compose -f docker/compose.yml ps -q secondpasslibrary)
```

Update with:

```powershell
git pull
docker compose -f docker/compose.yml up -d --build
```

Review `docker/.env.example` and `docker/compose.example.yml` during updates.
Local `docker/.env` and `docker/compose.yml` files remain deployment-owned and
untracked.

For a deliberately clean image rebuild:

```powershell
docker compose -f docker/compose.yml build --no-cache --pull
docker compose -f docker/compose.yml up -d
```

## Runtime data and backups

Durable runtime state belongs under `/app/userdata` in the container:

- `/app/userdata/db/` contains the SQLite database;
- `/app/userdata/media/` contains EPUB and cover files;
- `/app/userdata/imports/` contains temporary or staged import data.

Back up the complete volume and stable deployment secrets. Database and durable
media must be restored as one consistent snapshot. Stop the service first so
SQLite and media are quiescent. For the default named volume, create an archive
through a temporary Compose container:

```powershell
New-Item -ItemType Directory -Force backups
docker compose -f docker/compose.yml stop secondpasslibrary
docker compose -f docker/compose.yml run --rm --no-deps -v ./backups:/backup --entrypoint python secondpasslibrary -c "import tarfile; archive=tarfile.open('/backup/secondpass-userdata.tar.gz','w:gz'); archive.add('/app/userdata', arcname='userdata'); archive.close()"
docker compose -f docker/compose.yml start secondpasslibrary
```

For a bind mount, stop the service, copy the complete host directory to backup
storage, and then restart the service. The database and media must be copied
together.

An operator who cannot stop the service must use SQLite's online backup tooling
and coordinate the resulting database snapshot with media storage. Copying a
live `db.sqlite3` file is not a supported backup procedure.
Generated `var/static/` output is not user data and can be regenerated with
an image rebuild.

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

Uvicorn retains its safe proxy-header defaults. The supplied startup command
does not broaden which proxy addresses are trusted. Configure any different
trusted proxy address or network deliberately together with Django's forwarded
protocol and forwarded-host settings.

## Operator-controlled storage

The default Compose file uses the Docker-managed `secondpass_userdata` named
volume. To control the physical host location directly, replace only the volume
source in deployment-owned `docker/compose.yml`:

```yaml
volumes:
  - /srv/secondpass/userdata:/app/userdata
```

Keep the container target `/app/userdata`. Do not add or change
`SECOND_PASS_USERDATA_DIR`; the Docker image fixes that internal path. The
entrypoint creates required subdirectories and establishes application
ownership. Back up the selected host directory exactly as described above.

Development and non-Docker deployments retain the normal configurable
`SECOND_PASS_USERDATA_DIR` setting. The fixed path applies only to the standard
Docker image and entrypoint.

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

## Marginalia import-stage cleanup

Canonical Marginalia import previews store protected temporary archives under
`userdata/imports/staged/marginalia/`. Runtime access expires after exactly two
hours. Cleanup controls only how long abandoned files remain on disk.

```bash
docker compose -f docker/compose.yml exec -T secondpasslibrary python manage.py cleanup_marginalia_import_stages --dry-run
docker compose -f docker/compose.yml exec -T secondpasslibrary python manage.py cleanup_marginalia_import_stages
```

The command is repeat-safe and prints counts only. It also removes safe
digest-named leftovers from a successful Apply whose post-commit file cleanup
failed; the applied database result remains authoritative. A weekly host cron
entry is adequate and may run alongside Shelf cleanup. Django does not include
a job runner; schedule this through the host cron or Windows Task Scheduler.

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
