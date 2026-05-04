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

## Reading API basics

All reading endpoints are under `/api/v1/reading/` and require authentication (session auth in dev).

### Active session (lazy creation)

Open/continue reading for a book:

- `GET /api/v1/reading/books/<book_id>/active-session/`

If the authenticated user has no active `ReadingSession` for that book, this endpoint creates one. Sessions are not created when browsing/listing books.

### Start over (preserves history)

Start a new session for the same book:

- `POST /api/v1/reading/books/<book_id>/start-over/`
- Optional body: `{"name": "Second pass"}`

This marks the existing active session (if any) as inactive and creates a new active session. Old sessions, progress, and annotations are preserved.

### Progress (one-to-one per session)

Retrieve/update progress for a session (auto-creates if missing):

- `GET /api/v1/reading/sessions/<session_id>/progress/`
- `PATCH /api/v1/reading/sessions/<session_id>/progress/`

Example payload:

```json
{
  "device": "<device_id>",
  "locator": {"cfi": "/6/4", "chapter": "c1", "offset": 123},
  "progression": 0.42
}
```

`locator` is stored as JSON and is intentionally flexible for now.

### Annotations (highlights, notes, bookmarks)

Highlights, notes, and bookmarks are all stored as `Annotation` records:

- List/create/update: `/api/v1/reading/annotations/`
- Optional filters: `?book_id=<book_id>` and/or `?session_id=<session_id>`
- Delete uses soft delete (`is_deleted=true`) instead of hard deletion.

Example highlight payload:

```json
{
  "session": "<session_id>",
  "device": "<device_id>",
  "kind": "highlight",
  "locator": {"cfi": "/6/6"},
  "selected_text": "A highlighted passage",
  "color": "yellow"
}
```

## Runtime data

All runtime and user-generated data lives under `userdata/` by default (ignored by Git). EPUBs are stored content-addressed under `userdata/media/books/<first2>/<next2>/<sha256>.epub`.
