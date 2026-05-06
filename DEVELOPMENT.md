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

## Permissions design (future)

See `docs/permissions.md` for the intended future permission model (roles, groups, and policy direction). This is documentation-only and does not reflect all current behavior yet.

## Import an EPUB

```powershell
python manage.py import_epub "path\to\book.epub"
```

Note: `import_epub` is a dev/admin utility (host-side). The intended product import path is the API upload endpoint below.

## Import via API (staged uploads)

Supported uploads:
- A single `.epub`
- A simple `.zip` containing `.epub` files (non-EPUB entries are ignored; Calibre/library backup ZIPs are not supported)

Create an import job (multipart field name is `file`):

```text
POST /api/v1/library/imports/
```

List your import jobs:

```text
GET /api/v1/library/imports/
```

Get a specific job:

```text
GET /api/v1/library/imports/<id>/
```

## Library data model

`Book` contains the canonical, user-facing bibliographic fields (title, authors, series, publisher, language, published date, ISBN, subjects). If we later need raw imported metadata/provenance, it should be modeled separately.

### Identifier Position

- `Book.isbn` is a convenience/display field (prefer ISBN-13 when available), not the only identifier.
- `BookIdentifier` stores external/source identifiers (ISBNs and non-ISBN identifiers like ASIN/DOI/OCLC/LCCN/Open Library IDs/Calibre IDs/EPUB unique identifiers/URI-URN/etc).
- Identifiers imported from EPUB metadata use `source=epub`.
- Duplicate EPUB detection is based on file checksum, not identifiers.

## Format Support Position

Second Pass Library is EPUB-first and EPUB-only for the current implementation.

Do not add PDF support unless explicitly requested. PDF annotation and reading support is intentionally out of scope.

The architecture should remain format-aware rather than hardcoding EPUB assumptions into every model. Prefer fields such as `file_format` and flexible locator JSON over EPUB-specific database columns.

Possible future formats, such as comic archives, should not require a major rewrite, but no code for them should be added now.

## API error responses

Custom API errors (for places where views intentionally return a non-DRF error payload) should use:

```json
{
  "error": {
    "code": "SOME_CODE",
    "message": "Short, user-facing summary.",
    "detail": "Optional detail for debugging or display.",
    "hint": "Optional next step for the user."
  }
}
```

Helper lives in `core/errors.py` (`api_error_payload()` / `api_error_response()`).

## Reading API basics

All reading endpoints are under `/api/v1/reading/` and require authentication (session auth in dev).

## Book API browse/search

`GET /api/v1/library/books/` supports lightweight browse query params:

- `q`: case-insensitive search across title, subtitle, author name, series name, `isbn`, and identifier values
- `author`: filter by author UUID
- `series`: filter by series UUID
- `language`: filter by language code (case-insensitive)
- `has_files`: `true`/`false` to filter books that have at least one `BookFile`
- `ordering`: `title`, `created_at`, `updated_at`, or `published_date` (prefix with `-` for descending)

## LibraryGroup API (access scopes)

LibraryGroups are **access scopes**, not shelves. Shelves are not implemented.

Group visibility is policy-driven:

- Managers/Librarians/Owner can see all groups.
- Readers can see:
  - groups they are a member of
  - `listed` groups (discoverability only)
- `unlisted` groups are only visible to members and Managers/Librarians/Owner.
- Public (`slug="public"`) is visible to all authenticated users.

Discoverability does not grant access. Group book lists still filter each book through `can_view_book(user, book)`.

Endpoints:

```text
GET    /api/v1/library/groups/
GET    /api/v1/library/groups/<group_id>/
GET    /api/v1/library/groups/<group_id>/books/
POST   /api/v1/library/groups/<group_id>/books/         {"book": "<book_id>"}
DELETE /api/v1/library/groups/<group_id>/books/<book_id>/
```

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

### Locator conventions (preferred shape for EPUB)

Locators are flexible JSON for now. For EPUB, prefer a shape like:

```json
{
  "format": "epub",
  "href": "Text/chapter01.xhtml",
  "cfi": "epubcfi(...)",
  "progression": 0.1234,
  "position": 12345,
  "text": {
    "exact": "selected text",
    "prefix": "text before selection",
    "suffix": "text after selection"
  }
}
```

Notes:
- `href` is the EPUB internal content document path when available.
- `cfi` is preferred when the client can provide it.
- `progression` is a float between 0 and 1 when available.
- `position` is optional and client-defined for now.
- `text` quote context helps re-anchor highlights if a CFI fails.
- Do not require every field.
- PDF locators are not supported.

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
