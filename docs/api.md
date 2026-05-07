# API

All endpoints are under `/api/v1/` and require authentication unless stated otherwise.

## Accounts

- `GET /api/v1/accounts/me/`
- Users (Owner/Manager only): `GET /api/v1/accounts/users/`, `GET /api/v1/accounts/users/<id>/`, `PATCH /api/v1/accounts/users/<id>/`

## Library

- Books: `GET /api/v1/library/books/`, `GET /api/v1/library/books/<id>/`
- Book files: `GET /api/v1/library/book-files/`, `GET /api/v1/library/book-files/<id>/`
- Download: `GET /api/v1/library/book-files/<id>/download/`

## Imports

- `POST /api/v1/library/imports/`
- `GET /api/v1/library/imports/`
- `GET /api/v1/library/imports/<id>/`

See `docs/imports.md` for details.

## Groups (LibraryGroups)

LibraryGroups are access scopes, not shelves. Group book lists still filter each book through `can_view_book(user, book)`.

- `GET /api/v1/library/groups/`
- `GET /api/v1/library/groups/<group_id>/`
- `PATCH /api/v1/library/groups/<group_id>/` (presentation only: `description`, `discoverability`)
- `GET /api/v1/library/groups/<group_id>/books/`
- `POST /api/v1/library/groups/<group_id>/books/` body: `{"book": "<book_id>"}`
- `DELETE /api/v1/library/groups/<group_id>/books/<book_id>/`

See `docs/permissions.md` for the visibility/curation rules.

## Reading

- Active session: `GET /api/v1/reading/books/<book_id>/active-session/`
- Start over: `POST /api/v1/reading/books/<book_id>/start-over/`
- Sessions (read + limited metadata edits): `GET /api/v1/reading/sessions/`, `GET /api/v1/reading/sessions/<id>/`, `PATCH /api/v1/reading/sessions/<id>/` (only `name`, `notes`)
- Progress: `GET/PATCH /api/v1/reading/sessions/<session_id>/progress/`
- Annotations: `/api/v1/reading/annotations/` (soft-deleted items are hidden by default; pass `?include_deleted=true` to include them)

See `docs/reading.md` for details.
