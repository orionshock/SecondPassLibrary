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

Authentication non-goals (current):

- No email verification
- No email-based password reset
- No MFA
- No OIDC/OAuth

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
- `POST /api/v1/accounts/me/change-password/`
- Profiles (current user only): `GET /api/v1/accounts/profiles/` (paginated)
- Users (Owner/Manager only):
  - `GET /api/v1/accounts/users/` (paginated)
  - `GET /api/v1/accounts/users/<id>/`
  - `PATCH /api/v1/accounts/users/<id>/`
  - `POST /api/v1/accounts/users/` (creates a local Django user and returns a generated temporary password once)
  - `POST /api/v1/accounts/users/<id>/reset-password/` (Manager/Owner only; returns a generated temporary password once)

User-management payload notes:

- Managed users now include a read-only `groups[]` membership summary for that user (membership_id, group id/name, membership_role, is_public_group).
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
- Newly-created managed users are marked `must_change_password=true` (force change on first login).

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

- `id`, `name`
- `membership_role` (`reader` / `curator`)
- `is_public_group`

If the user is a curator of any non-Public group, `curated_group_ids` lists the group IDs where they have scoped curator powers.

Additional identity fields:

- `first_name`, `last_name`
- `must_change_password` (force change via product UI redirect)

### `PATCH /api/v1/accounts/me/`

Self-profile update endpoint (no auth redesign; no password handling).

Allowed fields:

- `email`
- `first_name`
- `last_name`

Any attempt to patch other fields is rejected (400) using the project error envelope (`UNSAFE_FIELD`).

### `POST /api/v1/accounts/me/change-password/`

Self password change endpoint.

## Shelves

Shelves are presentation/organization and **do not** grant book access. LibraryGroups still control access.

Endpoints:

- `GET /api/v1/shelves/` (paginated; visible shelves)
- `POST /api/v1/shelves/` (create; user-owned or group-owned depending on permissions)
- `GET /api/v1/shelves/<id>/`
- `PATCH /api/v1/shelves/<id>/` (name/description/visibility only)
- `DELETE /api/v1/shelves/<id>/`
- Items:
  - `GET /api/v1/shelves/<id>/items/` (paginated; books are filtered through access policy)
  - `POST /api/v1/shelves/<id>/items/` (add book)
  - `PATCH /api/v1/shelves/<id>/items/<item_id>/` (position only)
  - `DELETE /api/v1/shelves/<id>/items/<item_id>/`

Request:

```json
{ "current_password": "...", "new_password": "...", "confirm_password": "..." }
```

Rules:

- Requires authentication.
- Verifies `current_password` via Django `check_password()`.
- Sets the new password via Django `set_password()` and runs configured password validators.
- Updates the current session hash so the user stays logged in.
- Clears `UserProfile.must_change_password` when the change succeeds.

### `POST /api/v1/accounts/users/<id>/reset-password/`

Managed password reset (temporary password shown once).

Response shape:

```json
{
  "username": "someuser",
  "temporary_password": "generated",
  "copy_block": "Username: someuser\nPassword: generated",
  "message": "Show this password now. It will not be shown again."
}
```

Rules:

- Uses a generated secure temporary password (never stored/logged in plaintext).
- Sets `target.profile.must_change_password=true`.
- Manager can reset Librarian/Reader only (never Owner/Manager).
- Owner can reset Manager/Librarian/Reader.
- Managed reset cannot be used to reset your own password; use `/profile/password/` + `POST /accounts/me/change-password/`.

## Library

- Authors: `GET /api/v1/library/authors/` (paginated), `GET /api/v1/library/authors/<id>/`
- Series: `GET /api/v1/library/series/` (paginated), `GET /api/v1/library/series/<id>/`
- Books: `GET /api/v1/library/books/` (paginated), `GET /api/v1/library/books/<id>/`
- Book files: `GET /api/v1/library/book-files/` (paginated), `GET /api/v1/library/book-files/<id>/`
- Download: `GET /api/v1/library/book-files/<id>/download/`
- Book identifiers (book-scoped):
  - `GET /api/v1/library/books/<book_id>/identifiers/`
  - `POST /api/v1/library/books/<book_id>/identifiers/`
  - `PATCH /api/v1/library/books/<book_id>/identifiers/<identifier_id>/`
  - `DELETE /api/v1/library/books/<book_id>/identifiers/<identifier_id>/`

Book-to-group assignment endpoints (used by Groups UI and Book Edit UI):
- `GET /api/v1/library/groups/<group_id>/books/`
- `POST /api/v1/library/groups/<group_id>/books/` body: `{"book": "<book_id>"}`
- `DELETE /api/v1/library/groups/<group_id>/books/<book_id>/`

Book payload notes:

- Books now include a read-only `groups[]` summary (assigned LibraryGroups).
- For Manager/Librarian/Owner, `groups[]` includes all assigned groups.
- For Readers/Curators, `groups[]` includes only groups the caller can view (Public or direct membership).
- Books include a singular `file` object (or `null`) rather than `files[]`.
- Book write shape: `authors` is a list of Author ids; `series` is a Series id or `null`.
- `series_index` accepts integers or one decimal place (e.g. `5` or `5.1`).
- `subtitle` may be patched to an empty string.
- `identifiers[]` items include `id` and remain read-only on the Book payload; mutate via the book-scoped identifier endpoints.
- Identifier editing does not automatically update `Book.isbn` (edit `isbn` directly if desired).

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
  - `GET /api/v1/library/groups/<group_id>/memberships/` (paginated; readable by group members and by Owner/Manager/Librarian; Public group is readable to any authenticated user)
  - `POST /api/v1/library/groups/<group_id>/memberships/` body: `{"user": "<user_id>", "role": "reader|curator"}`
  - `PATCH /api/v1/library/groups/<group_id>/memberships/<membership_id>/` body: `{"role": "reader|curator"}`
  - `DELETE /api/v1/library/groups/<group_id>/memberships/<membership_id>/`

Public restrictions:

- Public cannot have Curators; membership role remains `reader`.
- Public is default/fallback, not mandatory: membership may be removed when another group remains; removing a user's final membership restores Public.

See `docs/permissions.md` for the visibility/curation rules.

## Reading

- Reading APIs follow the W3C-style direction described in `docs/user-data.md` and `docs/specs/reading-session-annotation-profile/` (import/export is future work; not implemented yet).
- Practical current REST examples for reader clients: `docs/reading-rest-examples.md`
- Active session: `GET /api/v1/reading/books/<book_id>/active-session/`
- Start over: `POST /api/v1/reading/books/<book_id>/start-over/`
- Devices: `GET /api/v1/reading/devices/` (paginated), `GET /api/v1/reading/devices/<id>/`
- Sessions (read + limited metadata edits): `GET /api/v1/reading/sessions/` (paginated), `GET /api/v1/reading/sessions/<id>/`, `PATCH /api/v1/reading/sessions/<id>/` (only `name`, `notes`)
- Progress: `GET/PUT/PATCH /api/v1/reading/sessions/<session_id>/progress/`
- Annotations: `GET /api/v1/reading/annotations/` (paginated; soft-deleted items are hidden by default; pass `?include_deleted=true` to include them)

Reading payload notes:

- Progress uses `current_location` (JSON) as the canonical "where am I?" session state.
- Annotations use canonical `motivation`, `target`, and `body` fields.
- `source_import` is reserved for future server-side import provenance and is not accepted/exposed via normal annotation create/update payloads.
- Reading payloads are versioned via `profile_version` (current: `0.1.0`). If provided on write, it must match the current server-supported version.

## Core

- Health check: `GET /api/v1/health/`

See `docs/reading.md` for details.
