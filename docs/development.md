# Development

Practical local development workflow (Windows/PowerShell).

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Note: `requirements.txt` includes Pillow for cover image validation.
EPUB imports also attempt best-effort embedded cover extraction (JPEG/PNG/WebP only).
ZIP imports can also use `metadata.opf` / sidecar `.opf` files (Calibre-style) to bootstrap metadata and cover for new books only.

## Media serving (dev)

Cover images (and other user media) are addressed under `MEDIA_URL` (default: `/media/`) and stored under `MEDIA_ROOT` (default: `userdata/media`).

In local development (`DEBUG=True`), Django serves `MEDIA_ROOT` at `MEDIA_URL` so cover images render in the product UI.

Production deployments must handle `MEDIA_ROOT` separately from WhiteNoise.
WhiteNoise serves packaged Product UI assets under `/static/` only; it does not
serve books, covers, imports, exports, marginalia, or other user data.

Optional: copy `.env.example` to `.env` and set environment variables for your shell/session.

## Run server

Windows:

```powershell
.\scripts\start-dev.ps1
```

POSIX:

```sh
sh scripts/start-dev.sh
```

Both scripts run `python manage.py migrate --noinput` and only then start
Django's development server. Set `PYTHON` to override the Python executable.
Additional arguments are passed through to `runserver`, for example:

```powershell
.\scripts\start-dev.ps1 127.0.0.1:8080 --noreload
```

For a clean local reset:

1. Stop the server.
2. Delete `userdata/` if the database and all local runtime/user data may be discarded.
3. Run the development startup script for the operating system.
4. Visit `/`.
5. Complete the first-run setup wizard.

The setup page initializes:

- Server Name: `Second Pass Library`
- Server Description: blank
- Public Group Name: `Common Room`
- Public Group Description: `Main Public Library Room for everyone`
- Enable Advanced Library Group Usage: off
- The first active Owner account, its Manager `UserProfile`, and its reader
  membership in the Public group

Email and the display-name fields are optional account metadata. `Common Room`
is the default display name for the protected shared public library space
managed by librarians and managers. Enabling advanced library groups presents
separate curator-managed rooms as a first-class UI feature; it does not change
permissions in this pass. Once an active Owner exists, `/setup/` is disabled
and normal login at `/api-auth/login/` is used.

Raw `python manage.py runserver` remains available, but it does not create or
migrate the database schema. If using raw `runserver`, run
`python manage.py migrate --noinput` first. The setup wizard assumes migrations
already exist; it does not create database tables during an HTTP request.

The setup wizard is not development-only. The same migrated-database/no-active-
Owner condition is used in production. See `docs/deployment.md`.

## Standalone reader dev (React)

The first reader client is expected to be a standalone browser app (e.g. React) running on `http://localhost:5173` during development.

The Django server enables open CORS for API + discovery endpoints only:

- `/.well-known/*`
- `/api/*`

This supports standalone reader clients from arbitrary origins. Cross-origin cookie credentials are not enabled; clients must use `Authorization: Bearer ...` tokens for protected API calls.

## Product UI (current)

- App shell/dashboard: `/app/`
- Owner server settings: `/server/` (Owner only; includes Django Admin / Service Hatch link)
- Library browse: `/library/`
- Book detail: `/library/books/<book_id>/`
- Edit book metadata: `/library/books/<book_id>/edit/`
- Imports: `/imports/`
- Groups: `/groups/`
- Users: `/users/` (Manager/Owner)
- Create user: `/users/new/` (Manager/Owner; temporary password shown once)
- Edit user: `/users/<user_id>/edit/` (Manager/Owner)

Before first-run setup is complete, unauthenticated Product UI routes direct to
`/setup/`. After setup, unauthenticated pages redirect to
`/api-auth/login/?next=...` as usual.

Logout is POST-based via `/api-auth/logout/` (no GET logout links in the product UI).

The product UI code lives in the Django app `web`.

## Authentication (current)

Second Pass Library currently uses Django/DRF built-in authentication for local development and early API testing:

- **Django session authentication** (browser-based development and the DRF browsable API)
- **DRF basic authentication** (convenience for local development/testing)
- **DRF browsable API login/logout** at `/api-auth/login/` and `/api-auth/logout/`
- **Django admin authentication** at `/admin/` (a service hatch; not the product UI)

Practical notes:

- Use `/api-auth/login/` to authenticate in the browsable API.
- Use `/admin/` to access the Django admin (requires an admin/superuser account).
- For non-browser API clients in local development, Basic auth is often the simplest option.
- If Basic auth remains enabled outside `localhost`, use HTTPS so credentials are not sent over plaintext.

Basic auth should not be treated as the final production/client authentication strategy.

## Run checks and tests

```powershell
python manage.py check
python manage.py test
```

Test helpers:

- Prefer `tests/utils/books.py::create_file_backed_book()` when a test needs a normal valid Book. The product invariant is that Books are file-backed.
- Use `create_fileless_book_for_integrity_edge_case()` only for tests that intentionally model inconsistent/out-of-band states.

## Dev/demo fixture world (local only)

Create a richer development/demo world for manual UI testing:

```powershell
python manage.py seed_dev_users
```

The command:

- applies pending migrations before reading the database
- creates a predictable lorem-named Owner only when no active superuser exists
- ensures the configured Public group exists (`Common Room` on a default server)
- ensures about 20 lorem-named demo users and five non-Public library groups
- creates varied reader/curator memberships without removing existing
  memberships, with at least one reader-profile curator for every demo
  non-Public group
- keeps Manager and Librarian demo accounts as broad-role users with their
  normal default Common Room membership, but does not add them to non-Public
  demo groups or assign them curator memberships
- represents demo curators as Reader-role accounts with curator memberships in
  specific non-Public groups
- creates personal, group-owned, and Common Room shelves; shared shelf names
  include the owning group name so they remain distinguishable in combined lists
- deterministically adds 5-10 existing books to each shelf when books are available

The command is non-destructive by default. Existing users with matching
usernames retain their names, email addresses, passwords, flags, and profile
roles. Existing groups and shelves are reused without overwriting their
descriptions or other fields. Re-running with the same seed does not duplicate
memberships, shelves, or shelf items.

Useful options:

```powershell
python manage.py seed_dev_users --seed family-demo
python manage.py seed_dev_users --users 12 --groups 3
python manage.py seed_dev_users --skip-shelves
```

Safety:

- Newly created demo accounts use the predictable password `changeme123`.
- The command refuses to run unless `DEBUG=True` (use `--force` only for local
  development).
- This command is not the normal installation bootstrap path. Fresh installs
  should use the first-run setup page. It remains a development/demo helper
  only.

## Common commands

Import a single EPUB (dev/admin utility):

```powershell
python manage.py import_epub "path\to\book.epub"
```

See also:
- `docs/api.md` (endpoint index)
- `docs/imports.md` (import workflow)
