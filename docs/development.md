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

In local development (`DEBUG=True`), Django serves `MEDIA_URL` (`/media/`) from `MEDIA_ROOT` so cover images render in the product UI.

Production deployments should serve `MEDIA_ROOT` at `MEDIA_URL` via the front-end web server (Django should not serve media in production).

Optional: copy `.env.example` to `.env` and set environment variables for your shell/session.

## Migrate

```powershell
python manage.py migrate
```

## Create superuser

```powershell
python manage.py createsuperuser
```

## Run server

```powershell
python manage.py runserver
```

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

If you are not authenticated, these pages redirect to `/api-auth/login/?next=...`.

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

## Dev seed users (local only)

Create predictable development users/groups for manual UI testing:

```powershell
python manage.py seed_dev_users
```

Credentials (DEV ONLY):

- Users: `owner`, `manager`, `librarian`, `reader`, `curator`, `outsider`
- Password: `changeme123`

Safety:

- The command refuses to run unless `DEBUG=True` (use `--force` only for local development).

## Common commands

Import a single EPUB (dev/admin utility):

```powershell
python manage.py import_epub "path\to\book.epub"
```

See also:
- `docs/api.md` (endpoint index)
- `docs/imports.md` (import workflow)
