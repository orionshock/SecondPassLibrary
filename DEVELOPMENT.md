# Development

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

## Import an EPUB

```powershell
python manage.py import_epub "path\to\book.epub"
```

## Runtime data

All runtime and user-generated data lives under `userdata/` by default (ignored by Git). EPUBs are stored content-addressed under `userdata/media/books/<first2>/<next2>/<sha256>.epub`.

