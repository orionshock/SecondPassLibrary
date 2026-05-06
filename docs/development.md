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
