# API

All endpoints are under `/api/v1/` and require authentication unless stated otherwise.

## Authentication

All `/api/v1/` endpoints require authentication unless a specific endpoint explicitly documents anonymous access.

Current supported (development) authentication methods:

- Django session authentication (browser-based development + DRF browsable API)
- DRF basic authentication (convenience for local development/testing)
- DRF browsable API login/logout via `/api-auth/`
- Django admin authentication via `/admin/` (service hatch; not the product UI)

Basic auth is enabled for convenience and should not be treated as the final production/client authentication strategy.

See `docs/development.md` for practical local usage notes and `docs/architecture.md` for the intentionally-deferred production direction.

## Pagination

List endpoints are paginated by default using page-number pagination.

Query params:

- `page` (1-based)
- `page_size` (optional; default `50`, max `200`)

Response shape:

```json
{
  "count": 123,
  "next": "http://.../?page=2",
  "previous": null,
  "results": []
}
```

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
