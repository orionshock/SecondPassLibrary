# Second Pass Library

Your books, your notes, your reading history.

Second Pass Library is a self-hosted reading library for EPUB collections. It is built for readers who want to keep their books, highlights, bookmarks, notes, reading progress, and reread history under their own control.

It is EPUB-first, private by default, and designed around durable user-owned reading data.

## What It Does

- Store and browse an EPUB library
- Import single EPUB files or simple ZIP archives of EPUBs
- Keep book metadata, authors, series, identifiers, and cover images
- Organize books with shelves
- Manage shared library access with groups and roles
- Track reading sessions, including rereads and closed historical sessions
- Store reading progress per session
- Store bookmarks, highlights, and notes
- View session marginalia in the product UI
- Export marginalia as JSON for one session, selected sessions, one book, or the whole library
- Preview SPL native marginalia imports without writing data
- Provide a REST/JSON API for reader clients

## Product Direction

Second Pass Library is for people who want a personal or small shared EPUB library that is not tied to a vendor cloud.

The project is not trying to be:

- A Kindle clone
- A PDF annotation system
- A Calibre replacement
- A SaaS platform
- An AI reading product

The focus is a dependable home for EPUB files and reading data.

## Current UI

The product UI includes:

- Dashboard with recent reading activity
- Library browsing and book detail pages
- Shelves
- Reading session history
- Session marginalia pages
- Marginalia export center
- User/profile and basic administration pages

The reader client is separate from this repository. This app provides the library, product UI, and API backing it.

## Data Ownership

Runtime and user data live under `userdata/`:

- `userdata/db/` for the SQLite database
- `userdata/media/` for uploaded/stored EPUBs and covers. Only covers are
  raw-public under `/media/covers/`; EPUB/book files are delivered through
  authenticated app/API endpoints.
- `userdata/imports/` for staged imports

`userdata/` is ignored by Git and should be backed up separately.
Collected static files are generated deploy artifacts under `var/static/`.
They can be deleted and regenerated with `collectstatic`; they should not be
part of normal user-data backups.

EPUB files are stored by SHA-256 checksum for deduplication. Human-readable filenames are derived from book metadata when files are downloaded or exported.

Production startup collects Product UI assets into `var/static/`, which
WhiteNoise serves under `/static/`. WhiteNoise does not serve `userdata/media/`.
The only public raw media namespace is `/media/covers/`; books, imports,
exports, marginalia, and other protected user data are not exposed as raw media.
Production deployments must provide a non-default `DJANGO_SECRET_KEY`,
`DJANGO_DEBUG=0`, and explicit `DJANGO_ALLOWED_HOSTS`; see
[Production startup](docs/deployment.md).

## Import And Export

Imports currently support:

- `.epub`
- `.zip` archives containing EPUB files
- OPF sidecar metadata for new books when present in ZIP imports

Marginalia export is available for:

- All reading data
- All sessions for one book
- Selected sessions for one book
- One reading session

The export format is documented in [docs/specs/marginalia-export.md](docs/specs/marginalia-export.md), with a JSON Schema in [docs/specs/marginalia-export.schema.json](docs/specs/marginalia-export.schema.json).

Importing marginalia back into the system supports SPL native marginalia exports. The product UI previews the file, stages the validated payload with a short-lived import token, and can apply selected sessions as historical reading sessions. Foreign annotation formats should be normalized by a client through the normal reading APIs or converted by an external tool into SPL native format first.

## Documentation

Useful docs:

- [Project overview](PROJECT.md)
- [Development setup](docs/development.md)
- [Production startup](docs/deployment.md)
- [Architecture](docs/architecture.md)
- [API index](docs/api.md)
- [Imports](docs/imports.md)
- [Reading data](docs/reading.md)
- [Permissions](docs/permissions.md)

## Quick Start For Local Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\scripts\start-dev.ps1
```

The startup script applies migrations before starting Django. Visit `/` and
complete the first-run setup wizard. It initializes the server identity, the
shared Public group (displayed as `Common Room` by default), the advanced-groups
UI preference, and the initial Owner account. `seed_dev_users` remains optional
development/demo data and is not required for setup. The development script
opts into Django debug mode; the app settings default to debug off.

Raw `python manage.py runserver` uses the default debug-off settings. For local
development behavior without the wrapper script, set `DJANGO_DEBUG=1` first.
The development script also sets local-safe `DJANGO_ALLOWED_HOSTS` defaults.
Production deployments should set `DJANGO_ALLOWED_HOSTS` to their real
hostnames or IP addresses.
For localhost production-mode testing on Windows, use
`.\scripts\start-local-production.ps1`; it sets local-safe `DEBUG=0`
environment defaults before running deploy checks, migrations, static
collection, and Waitress. The scripts remain local/dev convenience helpers;
Docker-based deployment orchestration can own final production process and
environment wiring later.

## Docker Quick Start

For a simple single-container SQLite deployment:

```powershell
copy .env.example .env
copy compose.example.yml compose.yml
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
docker compose up --build
```

Edit `.env` before starting: set `DJANGO_SECRET_KEY` to the generated value and
set `DJANGO_ALLOWED_HOSTS` to the hostnames or LAN IPs users will use. Edit
`compose.yml` if you need to customize ports, volumes, or restart policy.
The container runs as a non-root `secondpass` user and serves Django on
`127.0.0.1:8000` by default for a reverse proxy on the same host. Direct LAN or
public exposure requires intentionally changing the compose port binding. The
container bind-mounts `./userdata` for the SQLite database, stored EPUBs,
covers, and imports, and its healthcheck uses `/api/v1/health/`.

The default Docker UID/GID are `1000:1000` and can be overridden before build
with `APP_UID` and `APP_GID` in `.env`. On native Linux, make sure the bind
mount is writable by that UID/GID:

```bash
mkdir -p userdata
sudo chown -R 1000:1000 userdata
```

On Windows Docker Desktop, bind mount permissions are usually handled by Docker
Desktop.

For updates: `git pull`, review `.env.example` and `compose.example.yml` for
new options, merge any changes you want into your local files, then run
`docker compose up --build` again.

Reverse proxy, TLS, and public exposure are deployment-owned; Caddy/nginx/TLS
do not live in this app compose file. See [Production startup](docs/deployment.md)
for HTTPS reverse-proxy settings and backup notes.
