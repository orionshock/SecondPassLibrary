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

## Error responses

Second Pass Library uses two broad categories of error responses:

1. **Project-specific custom errors** (hand-crafted responses from views/services) use a consistent envelope:

```json
{
  "error": {
    "code": "SOME_STABLE_CODE",
    "message": "Human readable message.",
    "detail": "Optional technical/context detail.",
    "hint": "Optional user/admin hint."
  }
}
```

2. **Standard DRF serializer validation errors** generally keep DRF's default field-error shape for now.

Notes:

- Some endpoints intentionally return `404 Not Found` for resources the user cannot access to avoid leaking existence. This is by design in a few places (see `docs/permissions.md`).
- The `error` envelope is a UI hint for consistent messaging; it does not replace authorization checks on the actual endpoint being called.

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
- `PATCH /api/v1/accounts/me/` (self-profile fields only)
- Profiles (current user only): `GET /api/v1/accounts/profiles/` (paginated)
- Users (Owner/Manager only):
  - `GET /api/v1/accounts/users/` (paginated)
  - `GET /api/v1/accounts/users/<id>/`
  - `PATCH /api/v1/accounts/users/<id>/`
  - `POST /api/v1/accounts/users/` (creates a local Django user and returns a generated temporary password once)

User-management payload notes:

- Managed users now include a read-only `groups[]` membership summary for that user (group id/name/slug, membership_role, is_public_group).
- Membership editing remains on the LibraryGroup membership endpoints, not on `/accounts/users/`.
- User creation does **not** accept password fields; the system generates a temporary password and returns it only in the create response.

### `POST /api/v1/accounts/users/`

Create a local Django user (Manager/Owner only) and return a temporary password **once**.

Request fields:

- `username` (required; unique)
- `email` (optional; blank allowed)
- `first_name` (optional)
- `last_name` (optional)
- `role` (optional; `manager|librarian|reader`; default `reader`)
- `is_active` (optional; default `true`)

Response shape:

```json
{
  "user": { "username": "newuser", "role": "reader", "...": "..." },
  "temporary_password": "generated",
  "message": "Show this password now. It will not be shown again."
}
```

Notes:

- The temporary password is never stored except via Django's normal password hash.
- The password is not emailed and is not shown by any list/detail endpoint after creation.

### `GET /api/v1/accounts/me/` response

`/accounts/me/` is intended to be the UI bootstrap endpoint for authenticated clients:

- Who am I?
- What global role do I have?
- What broad capabilities do I have? (UI hints)
- Which LibraryGroups am I a member of?
- Which groups do I curate (if any)?

The response includes a `capabilities` object that provides **high-level UI hints only**. Authorization is still enforced by the specific endpoint policies; clients must not assume that a `true` capability guarantees any particular request will succeed.

Current `capabilities` keys:

- `can_manage_users`
- `can_manage_library`
- `can_import_books`
- `can_create_library_groups`
- `can_manage_group_memberships` (broad, role-level)
- `can_manage_group_identity` (broad, role-level; Public remains protected)
- `can_edit_group_presentation` (broad; includes scoped curator power when applicable)
- `can_access_imports`

It also includes a `groups` array listing the caller's `LibraryGroupMembership`s.

Each `groups[]` item includes:

- `id`, `name`, `slug`
- `membership_role` (`reader` / `curator`)
- `is_public_group`

If the user is a curator of any non-Public group, `curated_group_ids` lists the group IDs where they have scoped curator powers.

### `PATCH /api/v1/accounts/me/`

Self-profile update endpoint (no auth redesign; no password handling).

Allowed fields:

- `email`
- `first_name`
- `last_name`

Any attempt to patch other fields is rejected (400) using the project error envelope (`UNSAFE_FIELD`).

## Library

- Authors: `GET /api/v1/library/authors/` (paginated), `GET /api/v1/library/authors/<id>/`
- Series: `GET /api/v1/library/series/` (paginated), `GET /api/v1/library/series/<id>/`
- Books: `GET /api/v1/library/books/` (paginated), `GET /api/v1/library/books/<id>/`
- Book files: `GET /api/v1/library/book-files/` (paginated), `GET /api/v1/library/book-files/<id>/`
- Download: `GET /api/v1/library/book-files/<id>/download/`

Book payload notes:

- Books now include a read-only `groups[]` summary (assigned LibraryGroups).
- For Manager/Librarian/Owner, `groups[]` includes all assigned groups.
- For Readers/Curators, `groups[]` includes only groups the caller can view (Public or direct membership).

## Imports

- `POST /api/v1/library/imports/`
- `GET /api/v1/library/imports/` (paginated)
- `GET /api/v1/library/imports/<id>/`

See `docs/imports.md` for details.

## Groups (LibraryGroups)

LibraryGroups are access scopes, not shelves. Group book lists still filter each book through `can_view_book(user, book)`.

- `GET /api/v1/library/groups/` (paginated)
- `GET /api/v1/library/groups/<group_id>/`
- `PATCH /api/v1/library/groups/<group_id>/` (presentation only: `description`)
- `GET /api/v1/library/groups/<group_id>/books/` (paginated)
- `POST /api/v1/library/groups/<group_id>/books/` body: `{"book": "<book_id>"}`
- `DELETE /api/v1/library/groups/<group_id>/books/<book_id>/`
- Memberships (Manager/Owner only):
  - `GET /api/v1/library/groups/<group_id>/memberships/` (paginated)
  - `POST /api/v1/library/groups/<group_id>/memberships/` body: `{"user": "<user_id>", "role": "reader|curator"}`
  - `PATCH /api/v1/library/groups/<group_id>/memberships/<membership_id>/` body: `{"role": "reader|curator"}`
  - `DELETE /api/v1/library/groups/<group_id>/memberships/<membership_id>/`

Public restrictions:

- Public memberships cannot be removed via the API.
- Public cannot have Curators; membership role remains `reader`.

See `docs/permissions.md` for the visibility/curation rules.

## Reading

- Active session: `GET /api/v1/reading/books/<book_id>/active-session/`
- Start over: `POST /api/v1/reading/books/<book_id>/start-over/`
- Devices: `GET /api/v1/reading/devices/` (paginated), `GET /api/v1/reading/devices/<id>/`
- Sessions (read + limited metadata edits): `GET /api/v1/reading/sessions/` (paginated), `GET /api/v1/reading/sessions/<id>/`, `PATCH /api/v1/reading/sessions/<id>/` (only `name`, `notes`)
- Progress: `GET/PUT/PATCH /api/v1/reading/sessions/<session_id>/progress/`
- Annotations: `GET /api/v1/reading/annotations/` (paginated; soft-deleted items are hidden by default; pass `?include_deleted=true` to include them)

## Core

- Health check: `GET /api/v1/health/`

See `docs/reading.md` for details.
