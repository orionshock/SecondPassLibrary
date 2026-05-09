# Development

Practical local development workflow (Windows/PowerShell).

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

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

## Product UI (current)

- App shell/dashboard: `/app/`
- Library browse: `/library/`

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

## Common commands

Import a single EPUB (dev/admin utility):

```powershell
python manage.py import_epub "path\to\book.epub"
```

See also:
- `docs/api.md` (endpoint index)
- `docs/imports.md` (import workflow)
