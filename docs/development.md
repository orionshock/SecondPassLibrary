# Development

Practical local development workflow (Windows/PowerShell).

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
npm install
```

Note: `requirements.txt` contains runtime dependencies. `requirements-dev.txt`
adds local test/type tooling such as Django/DRF typing packages.
Pillow is included for cover image validation.
EPUB imports also attempt best-effort embedded cover extraction (JPEG/PNG/WebP only).
ZIP imports can also use `metadata.opf` / sidecar `.opf` files (Calibre-style) to bootstrap metadata and cover for new books only.

`npm install` installs the pinned local Pyright dev tool. There is no frontend
build step.

## Related docs

- [API index](api.md)
- [Architecture](architecture.md)
- [Permissions](permissions.md)
- [Imports](imports.md)
- [Reading data](reading.md)
- [Metadata and identifiers](metadata.md)
- [Production startup](deployment.md)

## Media serving (dev)

Cover images (and other user media) are addressed under `MEDIA_URL` (default: `/media/`) and stored under `MEDIA_ROOT` (default: `userdata/media`).

In local development, Django serves only `/media/covers/` so cover images render in the product UI.

Production deployments must handle durable media separately from WhiteNoise.
WhiteNoise serves packaged Product UI assets under `/static/` only. Django
serves only the public cover namespace, `/media/covers/`; stored EPUB files,
imports, exports, marginalia, and other protected user data are never served as
raw media URLs.
Production `collectstatic` output goes to `var/static/`, which is generated and
can be rebuilt. Back up `userdata/`, not `var/static/`.

Optional: copy `.env.example` to `.env` and set environment variables for your shell/session.

## Run server

```powershell
.\scripts\start-dev.ps1
```

The script sets `DJANGO_DEBUG=1` when it is not already set, runs
`python manage.py migrate --noinput`, and only then starts Django's development
server. Set `PYTHON` to override the Python executable. Additional arguments
are passed through to `runserver`, for example:

```powershell
.\scripts\start-dev.ps1 127.0.0.1:8080 --noreload
```

Raw `python manage.py runserver` uses the normal settings defaults. Because
`DEBUG` defaults to false, local development behavior requires either the
development startup script or an explicit `DJANGO_DEBUG=1` in the shell before
running raw `runserver`.

The development script also sets `DJANGO_ALLOWED_HOSTS` to
`localhost,127.0.0.1,[::1]` when it is not already set. Preserve or override
that value in your shell if you need a LAN hostname or IP during development.

For a clean local reset:

1. Stop the server.
2. Delete `userdata/` if the database and all local runtime/user data may be discarded.
3. Run the development startup script.
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
separate curator-managed rooms as a first-class UI feature and enables normal
non-Public group mutation workflows. Product UI does not provide a disable
control after enablement; disabling is a Django admin recovery flow that
consolidates custom group state into Public/Common Room. Once an active Owner
exists, `/setup/` is disabled and normal login at `/api-auth/login/` is used.

Raw `python manage.py runserver` remains available, but it does not create or
migrate the database schema. If using raw `runserver`, set `DJANGO_DEBUG=1` for
local debug/static/media behavior and run `python manage.py migrate --noinput`
first. The setup wizard assumes migrations already exist; it does not create
database tables during an HTTP request.

The setup wizard is not development-only. The same migrated-database/no-active-
Owner condition is used in production. See `docs/deployment.md`.

## Standalone reader dev (React)

The first reader client is expected to be a standalone browser app (e.g. React) running on `http://localhost:5173` during development.

The Django server enables open CORS for API + discovery endpoints only:

- `/.well-known/*`
- `/api/*`

This supports standalone reader clients from arbitrary origins. Cross-origin
cookie credentials are not enabled; clients must use `Authorization: Bearer ...`
tokens for protected API calls. The Product UI remains same-origin and uses
session auth with CSRF.

## Product UI (current)

- Dashboard: `/dashboard/`
- Owner server settings: `/server/` (Owner only; includes Django Admin / Service Hatch link)
- Library browse: `/library/`
- Book detail: `/library/books/<book_id>/`
- Edit book metadata: `/library/books/<book_id>/edit/`
- Imports: `/imports/`
- Groups: `/groups/`
- Users: `/users/` (Manager/Owner)
- Create user: `/users/new/` (Manager/Owner; temporary password shown once)
- Edit user: `/users/<profile_id>/edit/` (Manager/Owner)

Before first-run setup is complete, unauthenticated Product UI routes direct to
`/setup/`. After setup, unauthenticated pages redirect to
`/api-auth/login/?next=...` as usual.

Logout is POST-based via `/api-auth/logout/` (no GET logout links in the product UI).

The product UI code lives in the Django app `web`.

## Error-handling checks

Product UI and API missing-route behavior intentionally differ:

- Product UI missing pages return styled HTML error pages.
- `/api/` missing routes return JSON 404 responses shaped as `{"detail": "Not found."}`.
- Product UI error-page tests should run with `DEBUG=False`.
- API route-level 404 tests should assert JSON content type and response body.

Useful focused checks:

```powershell
.\.venv\Scripts\python.exe manage.py test tests.core.test_api_route_errors --keepdb
.\.venv\Scripts\python.exe manage.py test tests.core.product_ui.contracts.test_error_pages --keepdb
.\.venv\Scripts\python.exe tools\static_hygiene.py
.\.venv\Scripts\python.exe -m ruff check .
```

## Authentication (current)

Second Pass Library currently uses Django/DRF built-in authentication for local development and early API testing:

- **Django session authentication** (browser-based development and the DRF browsable API)
- **Client API bearer token authentication** on selected reader-client endpoints
- **DRF browsable API login/logout** at `/api-auth/login/` and `/api-auth/logout/`
- **Django admin authentication** at `/admin/` (a service hatch; not the product UI)

Practical notes:

- Use `/api-auth/login/` to authenticate in the browsable API.
- Use `/admin/` to access the Django admin only when
  `SECOND_PASS_ENABLE_DJANGO_ADMIN=1` is set. The local production helper sets
  this for operator testing only when the variable is unset and respects an
  explicit `0`; the settings default leaves the route unregistered.
- Use the admin recovery action to disable advanced library groups after use;
  do not manually flip `advanced_library_groups_enabled` false.
- HTTP Basic authentication is not enabled. Non-browser reader clients should use
  the Client API bearer-token flow where supported.

## Run Checks And Tests

```powershell
python manage.py check
python manage.py test
npm run typecheck
```

`npm run typecheck` runs Pyright with a conservative Django-friendly baseline.
It is intended to catch ordinary Python mistakes without treating Django's
dynamic model/runtime attributes as hard errors.
If PowerShell blocks `npm.ps1`, use `npm.cmd run typecheck`.

Prefer pytest for focused test runs. Run the smallest package, module, class,
or test that covers the change. Broad suites are intentional, not the default.
Use markers to keep routine runs away from known slow integration areas:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/library/imports/api -q
.\.venv\Scripts\python.exe -m pytest -m "not slow" tests/library -q
.\.venv\Scripts\python.exe -m pytest -m static_contract tests/core/product_ui -q
.\.venv\Scripts\python.exe -m pytest tests/reading/annotations/test_views.py -q --durations=10
```

Marker intent:

- `unit`: no database, pure logic/static parsing.
- `db`: database-backed tests.
- `filesystem`: writes generated files or temp paths.
- `product_ui`: Product UI route/static/template tests.
- `static_contract`: source/static/template contract tests that avoid runtime flows.
- `integration`: broad cross-app or API flow tests.
- `slow`: tests known to be slow enough to avoid in routine focused runs.

`manage.py test` remains available for compatibility checks and legacy workflows.

Targeted Django-runner commands:

Product UI:

```powershell
.\.venv\Scripts\python.exe manage.py test tests.core.product_ui --keepdb
.\.venv\Scripts\python.exe manage.py test tests.core.product_ui.reading.test_sessions_static --keepdb
.\.venv\Scripts\python.exe manage.py test tests.core.product_ui.reading.test_book_marginalia_static --keepdb
.\.venv\Scripts\python.exe manage.py test tests.core.product_ui.reading.test_import_static --keepdb
.\.venv\Scripts\python.exe manage.py test tests.core.product_ui.reading.test_export_static --keepdb
.\.venv\Scripts\python.exe manage.py test tests.core.product_ui.contracts.test_html_entity_contracts --keepdb
```

Reading:

```powershell
.\.venv\Scripts\python.exe manage.py test tests.reading.sessions --keepdb
.\.venv\Scripts\python.exe manage.py test tests.reading.progress --keepdb
.\.venv\Scripts\python.exe manage.py test tests.reading.annotations --keepdb
.\.venv\Scripts\python.exe manage.py test tests.reading.imports --keepdb
.\.venv\Scripts\python.exe manage.py test tests.reading.exports --keepdb
.\.venv\Scripts\python.exe manage.py test tests.reading --keepdb
```

Library:

```powershell
.\.venv\Scripts\python.exe manage.py test tests.library.test_catalog_list_views --keepdb
.\.venv\Scripts\python.exe manage.py test tests.library.test_book_visibility --keepdb
.\.venv\Scripts\python.exe manage.py test tests.library.test_file_views --keepdb
.\.venv\Scripts\python.exe manage.py test tests.library.test_author_series_views --keepdb
.\.venv\Scripts\python.exe manage.py test tests.library.test_book_identifiers --keepdb
.\.venv\Scripts\python.exe manage.py test tests.library --keepdb
```

Hygiene:

```powershell
.\.venv\Scripts\python.exe -m ruff check tests
.\.venv\Scripts\python.exe tools\static_hygiene.py
.\.venv\Scripts\python.exe tools\static_hygiene.py --all
.\.venv\Scripts\python.exe tools\static_hygiene.py --fix-mojibake
.\.venv\Scripts\python.exe tools\static_hygiene.py --fix-line-endings
```

`tools\static_hygiene.py` is the repo check for decorative HTML entities,
mojibake markers, trailing whitespace, LF line endings, and `git diff --check`.
By default it checks touched files only and does not modify files. Use `--all`
for a full tracked-file scan. `--fix-mojibake`, `--fix-trailing-whitespace`,
and `--fix-line-endings` may modify files in the scan set.

Pyright currently excludes tests in the checked-in configuration. For a
report-only type audit, use the local `node_modules\.bin\pyright.cmd` with a
temporary config that includes `tests` and adds the repository root to
`extraPaths`; do not treat this as a required gate until that setup is checked
in deliberately.

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
- requires first-run setup to be complete; it does not create the Owner account
- ensures the configured Public group exists (`Common Room` on a default server)
- ensures about 20 lorem-named demo users
- keeps Manager and Librarian demo accounts as broad-role users with their
  normal default Common Room membership
- never assigns curator flags to the Public/Common Room group
- creates personal shelves and Common Room shelves
- deterministically adds 5-10 existing books to each shelf when books are available
- when advanced library groups are enabled, additionally creates five non-Public
  demo groups, varied ordinary memberships, reader curators, group-owned
  shelves, and custom group book assignments

The command is non-destructive by default. Existing users with matching
usernames retain their names, email addresses, passwords, flags, and profile
roles. Existing shelves are reused without overwriting their
descriptions or other fields. Re-running with the same seed does not duplicate
memberships, shelves, or shelf items. Existing demo groups are reused when
advanced library groups are enabled.

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

Import a single local EPUB (operator-only host/container path):

```powershell
python manage.py import_epub "path\to\book.epub"
```

The command does not support ZIP files or OPF sidecars. It warns but continues
when the file exceeds the normal Product/API single-EPUB upload limit.

Import a local ZIP archive of EPUBs (operator-only host/container path):

```powershell
python manage.py import_books "path\to\books.zip"
```

The command supports ZIP OPF sidecars, uses the same ZIP limits as Product/API
imports, and does not create durable import history. `import_epub` remains the
single-EPUB command.

See also:
- `docs/api.md` (endpoint index)
- `docs/imports.md` (import workflow)
