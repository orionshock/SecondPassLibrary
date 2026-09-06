# Development

Practical local development workflow (Windows/PowerShell).

## Setup

Use Python 3.12 through 3.14; `.python-version` selects the deployment-aligned
Python 3.13 development default. The React workspace uses the Node.js version
in `.node-version` and npm version declared by `frontend/package.json`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Note: `requirements.txt` contains runtime dependencies. `requirements-dev.txt`
adds local test/type tooling such as Django/DRF typing packages.
Pillow is included for cover image validation. Current EPUB, ZIP/OPF metadata,
cover precedence, normalization, and safety rules are in [Imports](imports.md).

The React Product UI has its npm workspace under `frontend/`; see
[Frontend](frontend.md). There is no repository-root npm project.

## Pre-release migration reset

The first-party migration history was flattened before release. Existing
development databases created from the old migration history are intentionally
unsupported. Recreate the database and run the new initial migrations; do not
fake the new initial migrations onto an old database.

Existing files under `userdata/media/` may be retained, but their old database
rows are not reusable. Books must be re-imported into the fresh database before
the retained media can be treated as library content again.

Create normal schema changes with migrations from the current initial state.
Do not add compatibility migrations, fake initial state, or application-level
shims to make databases from the deleted migration history appear compatible.

## Code and fixture boundaries

`Book` owns its EPUB and cover fields directly.
Do not add compatibility re-export modules or wrapper imports for deleted or
renamed modules. Update callers to the current module boundary instead.

Runtime files belong under `userdata/` or a test-isolated temporary root.
Development and other non-Docker deployments may set
`SECOND_PASS_USERDATA_DIR` to a different runtime root. The standard Docker
image deliberately fixes its internal runtime root at `/app/userdata`.
Committed files under `TestFiles/` or `tests/fixtures/` are fixtures only, not
runtime storage or a destination for generated artifacts.

## Related docs

- [API conventions and external contracts](api.md)
- [Architecture](architecture.md)
- [Permissions](permissions.md), with immutable [Advanced/Simple Mode](advanced-library-groups.md)
  and [Book visibility](book-visibility.md) policy
- [Imports](imports.md)
- [Marginalia](marginalia.md), with immutable [visibility and preservation](marginalia-book-visibility.md)
- [Production startup](deployment.md)
- [Operator maintenance and repair](operations.md)
- [Frontend architecture](frontend.md)

## Application logging

Use the standard Python logging module with a module-level logger:
`logging.getLogger(__name__)`. Add a log only when it gives an operator or
developer useful information about runtime behavior. A touched file does not
need a new log merely because it was changed.

Choose the least severe useful level:

- `DEBUG`: expected ignored edge cases, optional enrichment that was skipped,
  and fallback paths useful during development. These are normal conditions,
  not operator alerts.
- `INFO`: successful operator-level actions and concise management-command,
  import, or cleanup summaries. Do not use it for routine request success.
- `WARNING`: recoverable corruption, self-healing, ignored unsafe archive
  members, or failure of a best-effort feature after the requested primary
  action succeeded.
- `ERROR`: an unexpected failure that blocks the requested action. Preserve
  useful exception context where it helps diagnose the failure, without
  exposing sensitive input.

Use structured or consistently bounded messages. Never log secrets, passwords,
authentication or client tokens, email addresses, marginalia content, raw
uploads or payloads, unsafe or absolute paths, file hashes, or storage keys.
For unsafe archive input, log a safe summary or count rather than repeating
attacker-controlled text. Avoid high-volume per-request success messages;
Django and the serving stack already provide request-level diagnostics where
configured.

When reviewing a runtime change, explicitly decide whether logging would help
operate or diagnose it. If not, leave the code quiet and state in the
implementation report that no useful logging was warranted. Deployment output
continues to use standard stdout/stderr logging as described in
[Production startup](deployment.md); application code should not invent its
own file-log directory.

Operator log-level changes and production log review are documented in
[Operations](operations.md).

## Media serving (dev)

Cover images (and other user media) are addressed under `MEDIA_URL` (default: `/media/`) and stored under `MEDIA_ROOT` (default: `userdata/media`).

In local development, Django serves only `/media/covers/` so cover images render in the product UI.

Production deployments must handle durable media separately from WhiteNoise.
WhiteNoise serves packaged Product UI assets under `/static/` only. Django
serves only the public cover namespace, `/media/covers/`; stored EPUB files,
imports, exports, marginalia, and other protected user data are never served as
raw media URLs.
Production `collectstatic` output goes to `backend/var/static/`, which is generated and
can be rebuilt. The canonical backup unit is documented in
[Operations](operations.md#backup-and-restore).

Docker environment examples live at `docker/.env.example`. The local
PowerShell helpers define their own environment in the script files.

## Run server

```powershell
.\scripts\start-dev.ps1
```

The script sets `DJANGO_DEBUG=1`, disables WhiteNoise runtime caching for faster
template/static iteration, runs `python backend/manage.py migrate --noinput`, and then
starts Django on port 8000 and the Product UI Vite server on port 5174. Run `npm.cmd --prefix frontend install` before using it for the first time. Vite uses the proxy configuration
documented in [Frontend](frontend.md) and is stopped when the Django
process exits. The script's Python executable and application environment are
defined in the script and do not inherit configuration choices from the calling
shell. Edit the values near the top of the script when local settings need to
change. Additional arguments are passed through to Django's `runserver`, for
example:

```powershell
.\scripts\start-dev.ps1 --noreload
```

Raw `python backend/manage.py runserver` uses the normal settings defaults. Because
`DEBUG` defaults to false, local development behavior requires either the
development startup script or an explicit `DJANGO_DEBUG=1` in the shell before
running raw `runserver`.

For production-likeness, use `.\scripts\start-local-production.ps1`; it keeps
`DJANGO_DEBUG=0`, builds the React workspace, runs `collectstatic`, and uses
WhiteNoise in manifest-backed mode. After collection it retains the Product UI
index and removes the redundant source-asset copy. It requires `npm.cmd install` to have been
run for `frontend/`, but it does not run a Vite or Node server. It runs one
direct Uvicorn worker against
`secondpass.asgi:application`, matching the Docker application target and
runtime path. Access logs are disabled in both deployment-like paths. Static
and media routing is unchanged: covers remain public display assets, while
EPUB downloads remain authenticated application/API responses. Proxy-header
trust remains deployment-owned and is not broadened by these startup helpers.

The development script sets `DJANGO_ALLOWED_HOSTS` to
`localhost,127.0.0.1,[::1]` and enables the Django Admin service hatch. Edit
the script if a LAN hostname or IP is needed during development.

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
control after enablement; the operator recovery flow is documented in
[Operations](operations.md#admin-and-repair-workflows). Once an active Owner
exists, `/setup/` is disabled and normal Product UI login at `/login/` is used.

Raw `python backend/manage.py runserver` remains available, but it does not create or
migrate the database schema. If using raw `runserver`, set `DJANGO_DEBUG=1` for
local debug/static/media behavior and run `python backend/manage.py migrate --noinput`
first. The setup wizard assumes migrations already exist; it does not create
database tables during an HTTP request.

`start-dev.ps1` and `start-local-production.ps1` start and supervise the Huey
maintenance consumer automatically. When using raw `runserver` or Uvicorn,
start it in a second terminal:

```powershell
python backend/manage.py run_huey
```

The consumer uses `userdata/db/huey.sqlite3`. Existing maintenance management
commands remain synchronous and do not require Huey to be running.

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

## Product UI

The Product UI is the Vite React workspace under `frontend/`. Django serves the
authenticated React shell at `/`; ordinary development should use the Vite
server on port 5174.

Django continues to render `/setup/`, `/login/`, `/logout/`, and the optional
`/admin/` service hatch. DRF browsable pages and `/api-auth/` are disabled.
React owns pairing approval at `/profile/client-pairing`; there are no alternate
Product UI mounts or compatibility routes.

## Error-handling checks

HTML and API missing-route behavior intentionally differs:

- Non-API missing pages return styled HTML error pages.
- `/api/` missing routes return JSON 404 responses shaped as `{"detail": "Not found."}`.
- API route-level 404 tests should assert JSON content type and response body.

Useful focused checks:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/core/test_api_route_errors.py -q
.\.venv\Scripts\python.exe tools\static_hygiene.py
.\.venv\Scripts\python.exe -m ruff check .
```

## Authentication (current)

Second Pass Library currently uses Django/DRF built-in authentication for local development and early API testing:

- **Django session authentication** for the React Product UI
- **Client API bearer token authentication** on selected reader-client endpoints
- **Django admin authentication** at `/admin/` (a service hatch; not the product UI)

Practical notes:

- Use `/login/` for Product UI session authentication. APIs return JSON rather than DRF browsable pages.
- Use `/admin/` to access the Django admin only when
  `SECOND_PASS_ENABLE_DJANGO_ADMIN=1` is set. The local production helper sets
  this for operator testing only when the variable is unset and respects an
  explicit `0`; the settings default leaves the route unregistered.
- Admin repair and recovery procedures are documented in
  [Operations](operations.md#admin-and-repair-workflows).
- HTTP Basic authentication is not enabled. Non-browser reader clients should use
  the Client API bearer-token flow where supported.

## Run Checks And Tests

Run the complete project-owned verification entry point with the active Python
environment:

```powershell
.\.venv\Scripts\python.exe tools\verify.py
```

On Linux, use `.venv/bin/python tools/verify.py`. The VS Code `Verify: all`
task invokes the same script. Individual checks remain available below for
focused work.

```powershell
python backend/manage.py check
python -m pytest
npm --prefix frontend run test:vitest -- tests/app/AppBootstrap.test.tsx
npm --prefix frontend exec -- tsc -b
npm --prefix frontend run build
node frontend/scripts/check-boundaries.mjs
```

Pyright uses the checked-in `pyrightconfig.json` with `backend/` as the Python
import root. The frontend production build runs the TypeScript project checks
before Vite emits the Product UI artifact.

Prefer pytest for focused test runs. Run the smallest package, module, class,
or test that covers the change. Broad suites are intentional, not the default.
When tests change, report each test or coherent test group as an `invariant`,
`contract`, `regression`, or `implementation detail`. Do not weaken an
invariant or contract assertion without explicitly identifying and justifying
the weaker guarantee.
Use the smallest relevant path or node first. The supported broad backend lanes
are explicit selections; unfiltered pytest still runs every test.

```powershell
# Broad developer lane: everything except the measured/inherently slow slice.
.\.venv\Scripts\python.exe -m pytest -m "not slow" -q

# Purpose-based lanes. Markers overlap intentionally.
.\.venv\Scripts\python.exe -m pytest -m security -q
.\.venv\Scripts\python.exe -m pytest -m filesystem -q
.\.venv\Scripts\python.exe -m pytest -m integration -q
.\.venv\Scripts\python.exe -m pytest -m slow -q

# Full backend release/comprehensive run. No tests are excluded by default.
.\.venv\Scripts\python.exe -m pytest -q
```

Marker meanings:

- `security`: owning authentication, authorization, anti-enumeration,
  credential, archive-safety, destructive-operation, and immutable-policy
  boundaries. It is deliberately narrower than every permission assertion.
- `concurrency`: real threads, executors, barriers, or competing transactions.
- `subprocess`: a real server, subprocess, or separate interpreter.
- `filesystem`: behavior whose contract depends on files, media, archive bytes,
  temporary directories, static output, or storage cleanup.
- `integration`: several real application layers whose boundary is not replaced
  by a lower-level test.
- `slow`: tests measured as expensive or inherently unsuitable for the broad
  developer lane. Important cheap tests remain in `not slow`.

Run the concurrency lane with SQLite resource warnings promoted to errors:

```powershell
.\.venv\Scripts\python.exe -X dev -m pytest -q -m concurrency `
  -W "error::ResourceWarning" `
  -W "error::pytest.PytestUnraisableExceptionWarning"
```

Coherent backend domain suites:

```powershell
# Accounts and browser/client security
.\.venv\Scripts\python.exe -m pytest tests/accounts -q

# Core runtime, settings, server shell, static, and media behavior
.\.venv\Scripts\python.exe -m pytest tests/core -q

# Library catalog, Groups, bearer reads, models, queries, and Admin
.\.venv\Scripts\python.exe -m pytest tests/library/catalog tests/library/groups tests/library/bearer `
  tests/library/test_models.py tests/library/test_queries.py tests/library/test_roles.py `
  tests/library/test_admin_book_changelist.py tests/library/test_admin_book_group_assignment.py `
  tests/library/test_admin_book_layout.py tests/library/test_admin_catalog_tag.py -q

# Library imports and stored-file repair
.\.venv\Scripts\python.exe -m pytest tests/library/imports `
  tests/library/test_file_repair.py tests/library/test_admin_file_repair.py -q

.\.venv\Scripts\python.exe -m pytest tests/shelves -q
.\.venv\Scripts\python.exe -m pytest tests/marginalia -q
.\.venv\Scripts\python.exe -m pytest tests/testenv -q
```

Frontend selections remain path-based rather than inventing a second marker
system:

```powershell
# Focused file, SDK workspace, Product UI, then complete Vitest.
npm.cmd --prefix frontend run test:vitest -- --run tests/app/AppBootstrap.test.tsx
npm.cmd --prefix frontend run test:vitest -- --run packages/spl-api
npm.cmd --prefix frontend run test:vitest -- --run tests
npm.cmd --prefix frontend run test:vitest -- --run

npm.cmd --prefix frontend exec -- tsc -b
node frontend/scripts/check-boundaries.mjs
npm.cmd --prefix frontend run build
```

These commands use the dedicated Product UI test root under `frontend/tests/`
and the SDK contract test root under `frontend/packages/spl-api/src/__tests__/`.
The Product UI tree mirrors meaningful production ownership without reproducing
path layers that add no test value.

Use `npm` instead of `npm.cmd` on shells where the executable shim is not
blocked by PowerShell execution policy.

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
.\scripts\seed-dev-users.ps1
```

The command:

- applies pending migrations before reading the database
- requires first-run setup to be complete; it does not create the Owner account
- ensures the configured Public group exists (`Common Room` on a default server)
- ensures about 20 lorem-named demo users
- keeps Manager and Librarian demo accounts as broad-role users with their
  normal default Common Room membership
- never assigns curator flags to the Public/Common Room group
- creates one private `Reading Queue` and one listed `Favorites` shelf for each
  demo user, plus Common Room shelves
- populates managed personal and Group shelves with small, varied selections of
  visible or exact-Group Books when Books are available
- when advanced library groups are enabled, additionally creates five non-Public
  demo groups by default, varied intentional memberships, curators distributed
  across Reader, Librarian, and Manager roles where possible, and 3-4
  group-owned shelves per Group
- gives the named demo Groups simple thematic Catalog Tag profiles; a Book is
  assigned when a normalized profile keyword occurs anywhere in one of its
  normalized tag names, with deterministic fallback Books for small catalogs

The command is non-destructive by default. Existing users with matching
usernames retain their names, email addresses, passwords, flags, and profile
roles. Existing shelves are reused without overwriting their
descriptions or other fields. Re-running with the same seed does not duplicate
memberships, shelves, or shelf items. Existing demo groups are reused when
advanced library groups are enabled.

Useful options:

```powershell
.\scripts\seed-dev-users.ps1 --seed family-demo
.\scripts\seed-dev-users.ps1 --users 12 --groups 3
.\scripts\seed-dev-users.ps1 --skip-shelves
```

Safety:

- Newly created demo accounts use the predictable password `changeme123`.
- The command refuses to run unless `DEBUG=True` (use `--force` only for local
  development).
- This command is not the normal installation bootstrap path. Fresh installs
  should use the first-run setup page. It remains a development/demo helper
  only.

## Local Library import commands

Recurring cleanup and repair commands belong to
[Operations](operations.md). The explicit local source modes are:

```powershell
python backend/manage.py import_library_folder_of_zip "path\to\book.epub"
python backend/manage.py import_library_folder_of_zip "path\to\per-book-archives"
python backend/manage.py import_library_aio_zip "path\to\large-library.zip"
python backend/manage.py import_library_tree "path\to\unpacked-library"
```

All three commands share the Product/API per-candidate importer and do not
create durable import history. See [Imports](imports.md) for pairing, safety,
large-archive, read-only bind-mount, interruption, and rerun behavior.

See also:
- `docs/api.md` (shared conventions and external contracts)
- `docs/imports.md` (import workflow)
