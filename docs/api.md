# API

All endpoints are under `/api/v1/` and require authentication unless stated otherwise.

## Authentication

All `/api/v1/` endpoints require authentication unless a specific endpoint explicitly documents anonymous access.

Current supported authentication methods:

- Django session authentication (browser-based development + DRF browsable API)
- Explicit Client API bearer tokens on selected reader-client endpoints
- DRF browsable API login/logout via `/api-auth/`
- Optional Django admin authentication via `/admin/` when
  `SECOND_PASS_ENABLE_DJANGO_ADMIN=1` (service hatch; not the product UI)

HTTP Basic authentication is not enabled.

Authentication non-goals (current):

- No email verification
- No email-based password reset
- No MFA
- No OIDC/OAuth/SAML/LDAP provider integration

See `docs/development.md` for practical local usage notes and `docs/architecture.md` for the intentionally-deferred production direction. Session revocation and web/client session tracking are documented in `docs/session-management.md`. Implemented reader-client code authorization is documented in `docs/client-api-auth.md`.

## Browser clients and CORS

CORS is currently open for `/api/` and `/.well-known/` with credentials
disabled. This supports independent browser reader clients that use bearer
tokens from another origin.

The Product UI is a same-origin session/CSRF application and is not CORS-open.
Do not enable cross-origin credentials without a separate auth/security design.

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

2. **Standard DRF serializer validation errors** generally keep DRF's default field-error shape.

Current API errors are not fully normalized. Existing response shapes may
include:

- `{"detail": "..."}`
- field validation errors such as `{"field": ["..."]}`
- selected custom `{"error": {...}}` helper responses

Notes:

- API route misses under `/api/` return JSON `{"detail": "Not found."}` with status `404`. Non-API route misses return styled Product UI HTML error pages.
- Malformed API input should generally return `400 Bad Request`. Malformed UUID path segments under `/api/` may fail URL matching before a view runs; those route-level misses return the JSON 404 shape above.
- Missing objects generally return `404 Not Found`.
- Some endpoints intentionally return `404 Not Found` for resources the user cannot access to avoid leaking existence. This is by design in sensitive user, library, reading, and shelf flows where already established (see `docs/permissions.md`). Do not change these anti-leak 404s to 403 without an explicit product/security decision.
- The `error` envelope is a UI hint for consistent messaging; it does not replace authorization checks on the actual endpoint being called.
- A future API error-envelope cleanup should be separate and treated as contract-impacting.

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
- Current user's Client API sessions:
  - `GET /api/v1/accounts/me/client-sessions/` (active only)
  - `DELETE /api/v1/accounts/me/client-sessions/<id>/` (revoke; sets `revoked_at`)
- Profiles (current user only): `GET /api/v1/accounts/profiles/` (paginated,
  read-only). Profile role, password state, and external identity data cannot be
  changed or deleted through this endpoint.
- Users (Owner/Manager only):
  - `GET /api/v1/accounts/users/` (paginated)
  - `GET /api/v1/accounts/users/<profile_id>/`
  - `PATCH /api/v1/accounts/users/<profile_id>/`
  - `POST /api/v1/accounts/users/` (creates a local Django user and returns a generated temporary password once)
  - `POST /api/v1/accounts/users/<profile_id>/reset-password/` (Manager/Owner only; returns a generated temporary password once)

## Client API

The Client API provides a pairing flow (human code + browser approval) and bearer tokens for reader clients. Client API bearer tokens are valid for:

- `GET /api/v1/accounts/me/` only (not `PATCH`)
- Selected **read-only** Library API endpoints (explicit allow-list; see Library section)
- Shelves API:
  - bearer tokens may read any shelf the token user can view
  - bearer tokens may create/edit/delete and manage items only in the token user's own personal shelves
  - group shelves and other users' shelves are read-only via bearer tokens
  - shelf `can_edit` is computed for the current request context; group shelves report `can_edit: false` to bearer-token clients even when the same user could edit them in the product UI with session auth
- Reading user-data endpoints (sessions/progress/annotations), strictly scoped to the token owner

Client API bearer tokens are intentionally **not** enabled for imports, library mutation endpoints, group membership mutation, or product UI/admin endpoints.
They are also not enabled for marginalia import/export endpoints; reading
import/export remains product UI/session-authenticated only in the current
slice.

Discovery:

- `GET /.well-known/secondpass` returns compact server identity and
  `api_base_url`. It is public discovery and does not include banner text,
  advanced group state, capabilities, or per-endpoint route metadata.
- `GET /api/v1/client-api/discovery/` returns the detailed Client API pairing
  discovery document.
- Authenticated clients should refresh `GET /api/v1/accounts/me/` for current
  user context plus small server context such as `advanced_library_groups_enabled`
  and `banner_text`.

Client API route conventions under `api_base_url`:

- `{api_base_url}client-api/discovery/`
- `{api_base_url}client-api/login-requests/`
- `{api_base_url}client-api/login-requests/{id}/poll/`

Login request / authorization:

- `POST /api/v1/client-api/login-requests/` (anonymous allowed)
- `GET/POST /client-api/authorize/` (browser; requires Django login)
- `GET /api/v1/client-api/login-requests/<id>/poll/` (anonymous allowed; request id is an unguessable UUID)
  - `status=approved` always includes `access_token`; after the token is delivered once, polling returns `status=consumed`.
  - Login request creation returns `interval`, the recommended poll interval in seconds.

User-management payload notes:

- Managed users expose `profile_id` as the public user identifier. They do not expose Django auth user database ids.
- Managed users include a read-only `groups[]` membership summary for that user (group id/name, `is_public_group`, `is_curator`). Membership record ids are not exposed.
- Membership editing remains on the LibraryGroup membership endpoints, not on `/accounts/users/`.
- User creation does **not** accept password fields; the system generates a temporary password and returns it only in the create response.
- Email is optional contact/management metadata. It is not required for local
  login and is not an account identity key. Email is exposed only by the
  authenticated user's self-profile payload and Manager/Owner user-management
  payloads. Generic compact user identities, including group memberships and
  shelves, contain only `profile_id` and `username`.

`GET /api/v1/accounts/user-choices/?q=<text>&exclude_group=<group_uuid>` is a
Manager/Owner-only username selector endpoint. It returns normally paginated
active users as `{profile_id, username}` objects, searches usernames, and may
exclude users who already belong to one LibraryGroup. It does not replace the
full `/api/v1/accounts/users/` management API.

### `POST /api/v1/accounts/users/`

Create a local Django user (Manager/Owner only) and return a temporary password **once**.

Request fields:

- `username` (required; unique)
- `email` (optional contact/management metadata; blank allowed)
- `first_name` (optional)
- `last_name` (optional)
- `role` (optional; `manager|librarian|reader`; default `reader`)
- `is_active` (optional; default `true`)

Response shape:

```json
{
  "user": { "profile_id": "8f8cc870-5f5a-41e7-8cf4-62bc56f0db15", "username": "newuser", "role": "reader", "...": "..." },
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
- Am I an Owner?
- Which LibraryGroups am I a member of?
- Which group memberships are marked as curator/steward relationships?
- Are advanced library groups currently enabled?
- What single server banner text should be shown, if any?

It includes a `groups` array listing the caller's `LibraryGroupMembership`s.

Each `groups[]` item includes:

- `id`, `name`
- `is_public_group`
- `is_curator`

Example `groups[]` item:

```json
{
  "id": "631947a3-ffe9-45b4-9373-b48c81a4fdd4",
  "name": "Fantasy Club",
  "is_public_group": false,
  "is_curator": true
}
```

`/accounts/me/` global `role` and `is_owner` describe broad account authority. `groups[].is_curator` describes explicit stewardship on that exact membership. It is not a global role and there is no derived group-id bootstrap list.

Additional identity fields:

- `first_name`, `last_name`
- `must_change_password` (force change via product UI redirect)

Refreshable server context:

- `advanced_library_groups_enabled` (boolean): reader clients can use this to
  show or hide group browsing UI.
- `banner_text` (string): the current server banner text, or an empty string
  when unset.

Broad Product UI affordances should be derived from `role` and `is_owner`.
Group-scoped curator affordances should use the matching `groups[]` membership
and its `is_curator` flag. Shelf payloads expose the object-specific `can_edit`
hint.

Example response:

```json
{
  "username": "tempor",
  "email": "tempor@example.test",
  "first_name": "Tempor",
  "last_name": "Incididunt",
  "profile_id": "59ebfe48-3a75-4650-a4cd-5db1d32f5598",
  "role": "reader",
  "must_change_password": false,
  "is_owner": false,
  "advanced_library_groups_enabled": false,
  "banner_text": "",
  "groups": [
    {
      "id": "631947a3-ffe9-45b4-9373-b48c81a4fdd4",
      "name": "Fantasy Club",
      "is_public_group": false,
      "is_curator": true
    }
  ]
}
```

### `PATCH /api/v1/accounts/me/`

Self-profile update endpoint (no auth redesign; no password handling).

Allowed fields:

- `email`
- `first_name`
- `last_name`

Any attempt to patch other fields is rejected (400) using the project error envelope (`UNSAFE_FIELD`).

### `POST /api/v1/accounts/me/change-password/`

Self password change endpoint.

Request:

```json
{ "current_password": "...", "new_password": "...", "confirm_password": "..." }
```

Rules:

- Requires authentication.
- Verifies `current_password` via Django `check_password()`.
- Sets the new password via Django `set_password()` and runs configured password validators.
- Updates the current session hash so the user stays logged in.
- Revokes all other Django web sessions for the user (keeps the current session).
- Clears `UserProfile.must_change_password` when the change succeeds.

## Shelves

Shelves are presentation/organization and **do not** grant book access. LibraryGroups still control access.

Endpoints:

- `GET /api/v1/shelves/` (paginated; visible shelves)
- `POST /api/v1/shelves/` (create; user-owned or group-owned depending on permissions)
- `GET /api/v1/shelves/<id>/`
- `PATCH /api/v1/shelves/<id>/` (partial update; name/description/visibility only)
- `PUT /api/v1/shelves/<id>/` (treated the same as `PATCH` for compatibility; partial update)
- `DELETE /api/v1/shelves/<id>/`
- Items:
  - `GET /api/v1/shelves/<id>/items/` (paginated; books are filtered through access policy)
  - `POST /api/v1/shelves/<id>/items/` (add book)
  - `PATCH /api/v1/shelves/<id>/items/<item_id>/` (`{"move": "up|down"}` or `{"position": 0}`)
  - `DELETE /api/v1/shelves/<id>/items/<item_id>/`

List filters:

- `GET /api/v1/shelves/?scope=personal` returns the current user's user-owned shelves, including empty shelves.
- `GET /api/v1/shelves/?scope=shared` returns other users' listed shelves with at least one viewer-visible item.
- `GET /api/v1/shelves/?scope=group` returns visible group-owned shelves, including empty shelves.
- Omitting `scope` and `scope=all` return the same combined visible-shelves list.
- Every scope retains the normal DRF paginated list envelope; no grouped/sections response is introduced. Session and bearer reads use the same scope rules.
- Scope filtering is applied after normal visibility rules; other users' private shelves are excluded from every normal list scope.
- `GET /api/v1/shelves/?owner_group=<group_id>` filters to group-owned shelves for that group (still visibility-scoped to the caller).
- `GET /api/v1/shelves/?book=<book_id>` filters to shelves containing the given book (still visibility-scoped to the caller).
  - When `?book=<book_id>` is provided, shelf rows include `matched_item_id` (the `ShelfItem.id` for that book on that shelf) to support UI removal without extra item lookups.
- Ordering:
  - `GET /api/v1/shelves/?ordering=name` orders by shelf name A-Z, then stable id fallback.
  - `GET /api/v1/shelves/?ordering=-item_count` orders by highest item count first, then name/id fallback.
  - Missing/blank `ordering` defaults to `name`.
  - Invalid ordering values return `400`.
  - Ordering composes with `scope`, `owner_group`, `book`, pagination, and `include_preview_books=true`.
- `scope` accepts only `all`, `personal`, `shared`, or `group`; other supplied values return `400`.
- `owner_group` and `book` must be valid UUIDs when supplied; malformed values return `400`.
- `scope=personal` cannot be combined with `owner_group` and returns `400`.
- `scope=group` may be combined with `owner_group`.

Shelf payload notes:

- Shelves include a read-only `can_edit` boolean computed for the current request context. This is a UI hint; API authorization remains authoritative. Product UI/session-auth requests use normal shelf edit authorization, including allowed group shelf edits. Client API bearer-token requests report `can_edit: true` only for the token user's own user-owned shelves.
- Shelves include a read-only integer `item_count` on list/detail payloads. It
  counts only shelf books visible to the current viewer. Other users' listed
  shelves are omitted from list responses when this viewer-scoped count is
  zero; owners still see their own empty shelves, and visible group-owned
  shelves remain visible when empty.
- User-owned shelves include `owner_user` as a compact user object with `profile_id` and `username`; group-owned shelves have `owner_user: null`.
- Shelves include `created_by` as the same compact user object when known. Shelf item `added_by` uses this shape too. These compact user objects do not include Django auth user database ids, email addresses, or profile/admin metadata.
- Shelf item payloads include a compact `book` object that includes `cover_url` (or `null`) when a cover is available.
- Shelf item positions are stored as contiguous zero-based integers. If multiple items are requested at the same position during add/import-style writes, that cluster is canonicalized by book title, then stable IDs, and later items are bumped.
- Patching an existing item with `position` is a move-to operation: the item is removed from its current list position, inserted at the requested zero-based target (clamped to the list bounds), and all shelf items are renumbered contiguously.
- Shelf item list ordering:
  - `GET /api/v1/shelves/<id>/items/?ordering=position` orders by stored shelf position and is the default.
  - `GET /api/v1/shelves/<id>/items/?ordering=title` orders the response by contained book title.
  - `GET /api/v1/shelves/<id>/items/?ordering=author` orders the response by contained book primary author name using the same author-name ordering convention as book display.
  - Invalid ordering values return `400`.
  - Title/author ordering is response/view ordering only and does not mutate stored `ShelfItem.position`; move/reorder endpoints continue to operate on stored positions.
- Product/UI displays may show one-based labels such as `#1`, `#2`, etc.; the current shelf edit UI reorders with `Move up` / `Move down` buttons plus a one-based `Move to` dropdown and has no drag/drop or per-row numeric position input.
- Client API bearer tokens:
  - may read any shelf the token user can view
  - may create/edit/delete shelves and add/remove/reorder items only for the token user's own personal shelves
  - group shelves and other users' shelves are read-only via bearer tokens and report `can_edit: false`
  - do not bypass book access; `/items/` still filters listed books through normal book visibility
- Shelf list/detail payloads support the reusable `include_preview_books=true` opt-in described under [Preview books](#preview-books).

Example user-owned shelf payload excerpt:

```json
{
  "owner_type": "user",
  "owner_user": {
    "profile_id": "8f8cc870-5f5a-41e7-8cf4-62bc56f0db15",
    "username": "manager"
  },
  "owner_group": null,
  "created_by": {
    "profile_id": "8f8cc870-5f5a-41e7-8cf4-62bc56f0db15",
    "username": "manager"
  }
}
```

### `POST /api/v1/accounts/me/web-sessions/logout-others/`

Revoke other Django web sessions for the current user (keeps the current session).

Response shape:

```json
{ "message": "Other web sessions logged out." }
```

Rules:

- Requires authentication.
- Does not expose session keys, IP addresses, or user agents.
- Deletes the other sessions from Django's session store and removes their `UserWebSession` tracking rows.

### `POST /api/v1/accounts/users/<profile_id>/reset-password/`

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
- Revokes all Django web sessions for the target user.
- Manager can reset Librarian/Reader only (never Owner/Manager).
- Owner can reset Manager/Librarian/Reader.
- Managed reset cannot be used to reset your own password; use `/profile/password/` + `POST /accounts/me/change-password/`.

## Library

- Authors: `GET /api/v1/library/authors/` (paginated), `GET/PATCH /api/v1/library/authors/<id>/`
- Series: `GET /api/v1/library/series/` (paginated), `GET/PATCH /api/v1/library/series/<id>/`
- Catalog Tags: `GET /api/v1/library/tags/` (paginated), `GET /api/v1/library/tags/<id>/`
- Books: `GET /api/v1/library/books/` (paginated), `GET/PATCH /api/v1/library/books/<id>/`

Book detail responses include a read-only `groups` array containing only group
assignments visible to the caller. Each summary contains `id`, `name`,
`description`, and `is_public_group`; membership records and users are not
included. In simple mode this array may include Public/Common Room, while
custom groups remain hidden. This API representation does not imply a Product
UI relationship tab: Book Detail hides its Groups tab in simple mode. Book list
rows do not include `groups`.

Book list rows, broad-search rows, and group-scoped Book rows use the compact
Book shape. Catalog Tags are returned as `tags`, and the stored format is
returned as top-level `file_format`. These rows do not include `catalog_tags`,
`identifiers`, `groups`, or the detail `file` object.

Book detail, Book PATCH, and cover-mutation responses use the detail shape.
Catalog Tags are returned as `catalog_tags`; identifiers and visibility-scoped
`groups` are included; and file metadata is returned only through `file` (or
`null` when no file is stored). Detail responses do not repeat compact-row
`tags` or top-level `file_format`.

`GET /api/v1/library/books/?q=<term>` is the Books browse-axis search and
matches title and sort title only.

`GET /api/v1/library/search?q=<term>` is the broad library book search. It
returns normal Book list rows in the normal paginated envelope and searches
visible Books by title, sort title, subtitle, author name, series name,
identifier value, Catalog Tag name, publisher, and description. Missing or
blank `q` returns an empty page rather than the whole library. Supported
ordering is `title`, `-title`, `author`, `-author`, `series`, and `-series`;
the default is `title`.

Broad library book search supports `exclude_shelf=<shelf_id>` for a manageable shelf and
`exclude_group=<group_id>` for a manageable group. These suppress already
contained/assigned Books after visibility scoping. Unknown or inaccessible
exclusion objects return `404`. Search rows use the Book list shape and never
include download URLs, checksums, storage/source names, file keys, or group
membership data. Session and client bearer GET requests use the same
visibility rules.

Book-to-group assignment endpoints (used by Groups UI and Book Edit UI):

- `GET /api/v1/library/groups/<group_id>/books/`
- `POST /api/v1/library/groups/<group_id>/books/` body: `{"book_id": "<book_id>"}`
- `DELETE /api/v1/library/groups/<group_id>/books/<book_id>/`

Client API bearer token support (read-only allow-list):

- `GET /api/v1/library/books/`
- `GET /api/v1/library/search?q=<term>`
- `GET /api/v1/library/books/<id>/`
- `GET /api/v1/library/books/<id>/download/`
- `GET /api/v1/library/authors/`
- `GET /api/v1/library/authors/<id>/`
- `GET /api/v1/library/series/`
- `GET /api/v1/library/series/<id>/`
- `GET /api/v1/library/tags/`
- `GET /api/v1/library/tags/<id>/`
- `GET /api/v1/library/groups/`
- `GET /api/v1/library/groups/<group_id>/`
- `GET /api/v1/library/groups/<group_id>/books/`
- `GET /api/v1/library/groups/<group_id>/authors/`
- `GET /api/v1/library/groups/<group_id>/series/`
- `GET /api/v1/library/groups/<group_id>/tags/`

Bearer credentials are read-only under `/api/v1/library/` regardless of the
account's role. Unsafe methods on mixed read/write views require Django session
authentication before the existing role and object authorization checks run.
This includes Book metadata and tag updates, cover replacement/clear, group
create/update/delete, group assignment mutation, membership mutation, and
imports. Membership reads are also session-only management data.

All bearer catalog and group queries retain the authenticated account's normal
visibility. Hidden-only details return `404`; counts, filters, previews, and
pagination are calculated after visibility scoping. Group routes require exact
group visibility. When advanced groups are disabled, Public/Common Room remains
available and custom group routes return `404`.

Book detail `file` data contains format, size, checksum, and the authenticated
`download_url`. `GET /api/v1/library/books/<book_id>/download/` streams the
caller's visible canonical EPUB as an `application/epub+zip` attachment for
session or bearer authentication. The attachment filename is generated from
the sanitized, bounded Book title; it never uses the content-addressed storage
name. Fileless or unsupported-format Books return bounded `409
BOOK_FILE_UNAVAILABLE`; missing or unreadable storage returns the same bounded
code with `503` and no storage detail.

The download endpoint currently returns the complete file with `200`; byte
Range requests are not implemented. Raw `/media/books/` paths remain
inaccessible and are never exposed. `cover_url` continues to use the public
display-only `/media/covers/` namespace; cover mutation remains session-only.

Author/Series payload notes:

- Author payloads include optional `biography`; Series payloads include optional `summary`. Librarian+ may PATCH `name` and the respective prose field on the detail endpoint; readers remain read-only.
- Author and Series payloads include `book_count` (read-only). `book_count` is scoped to books visible to the current caller (readers and bearer tokens do not learn about inaccessible books).
- Author and Series list/detail payloads may opt into `preview_books` with
  `include_preview_books=true`; preview items are visibility-scoped and use
  the reusable preview shape described below. Tags do not currently attach
  preview books.
- Author list ordering:
  - `GET /api/v1/library/authors/?ordering=name` orders by author name A-Z and is the default.
  - `GET /api/v1/library/authors/?ordering=-book_count` orders by highest visible `book_count` first, then name/id fallback.
  - Invalid ordering values return `400`.
- Series list ordering:
  - `GET /api/v1/library/series/?ordering=name` orders by series name A-Z and is the default.
  - `GET /api/v1/library/series/?ordering=-book_count` orders by highest visible `book_count` first, then name/id fallback.
  - Invalid ordering values return `400`.

Catalog Tag browse endpoints:

- `GET /api/v1/library/tags/`
- `GET /api/v1/library/tags/<tag_id>/`
- `GET /api/v1/library/groups/<group_id>/tags/`

Tag list endpoints accept `q`, `ordering`, `page`, and `page_size`. `q`
matches the tag's catalog name, including its internal normalized and sort forms.
`ordering` accepts `name`, `-name`, `book_count`, and `-book_count`, and
defaults to `name`. Responses use normal pagination and each tag has exactly:

```json
{
  "id": "tag UUID",
  "name": "Science Fiction",
  "slug": "science-fiction",
  "book_count": 12
}
```

Global tag results and `book_count` include only books visible to the caller.
Group tag results and counts are additionally scoped to books assigned to that
exact visible group. In simple mode, Public/Common Room group tags remain
readable while custom-group tag routes return `404`. Tag endpoints accept
Django session authentication and Client API bearer authentication. Tag detail
is GET-only; there is no standalone tag create, update, or delete API, and
bearer authentication grants no tag mutation capability. Catalog Tag
relationships are mutated only through Book PATCH `catalog_tags`.

Book, Author, and Series list endpoints accept the compact query parameter
`tag=<tag-slug>`, which filters by Catalog Tag slug. Books are
filtered to books directly carrying that tag. Authors and Series are filtered
to records with at least one caller-visible tagged book, and their `book_count`
reflects that filtered visible-book context. Group-scoped Book, Author, and
Series lists apply the same filter within the exact visible group. Unknown or
inaccessible slugs return an empty paginated result without revealing whether
the tag exists. UUID values are not accepted as tag filters; clients should use
the stable `slug` returned by tag payloads.

Book list ordering:

- Book `q` search matches only `title` and the internal `sort_title` value.
  Authors, Series, identifiers, tags, publisher, subtitle, and description do
  not participate in Book-axis text search; use their dedicated axes or filters.

- `GET /api/v1/library/books/?ordering=title` orders by title A-Z and is the default for general book browsing and author-filtered book browsing.
- `GET /api/v1/library/books/?ordering=author` orders by primary/first author name A-Z using the existing author-name display convention, then title/id fallback.
- `GET /api/v1/library/books/?ordering=series` orders by series name A-Z, then `series_index`, title, and id fallback.
- `GET /api/v1/library/books/?series=<series_id>` defaults to `series_index` ordering.
- `GET /api/v1/library/books/?series=<series_id>&ordering=series_index` orders by `series_index` ascending, nulls last, then title/id fallback.
- Invalid ordering values return `400`.
- Time-based book ordering is intentionally not part of the public sorting contract in this pass.

### Preview books

Several browse/context endpoints support optional bounded book-cover previews:

- `GET /api/v1/shelves/?include_preview_books=true`
- `GET /api/v1/shelves/<id>/?include_preview_books=true`
- `GET /api/v1/library/authors/?include_preview_books=true`
- `GET /api/v1/library/authors/<author_id>/?include_preview_books=true`
- `GET /api/v1/library/series/?include_preview_books=true`
- `GET /api/v1/library/series/<series_id>/?include_preview_books=true`
- `GET /api/v1/library/groups/?include_preview_books=true`
- `GET /api/v1/library/groups/<group_id>/?include_preview_books=true`
- `GET /api/v1/library/groups/<group_id>/authors/?include_preview_books=true`
- `GET /api/v1/library/groups/<group_id>/series/?include_preview_books=true`

Book and Catalog Tag endpoints do not currently attach `preview_books`; Book
payloads already represent concrete books, and Tag payloads remain count-only.

Request behavior:

- `include_preview_books` accepts truthy values `1`, `true`, `yes`, `y`, and `on`, case-insensitive after trimming.
- Absent or false-like values omit `preview_books`; default payloads remain unchanged.
- The option can be combined with normal parent endpoint pagination (`page`, `page_size`) and normal endpoint filters.
- Parent endpoint pagination shape does not change. `preview_books` is attached to each parent row on the current page and is capped independently of parent `page_size`.

Response shape when opted in:

```json
{
  "id": "parent-id",
  "name": "Parent name",
  "preview_books": [
    {
      "id": "59ebfe48-3a75-4650-a4cd-5db1d32f5598",
      "title": "Example Book",
      "cover_url": null
    }
  ]
}
```

Preview item rules:

- Each preview item contains only `id`, `title`, and `cover_url`.
- `cover_url` is an absolute URL when a cover exists, otherwise `null`.
- Preview items are context hints, not full Book objects.
- Preview items never include file/download URLs, reading data, marginalia, permission internals, groups, shelves, authors, or series payloads.
- At most 6 preview books are returned per parent item.

Visibility and auth:

- Preview books are visibility-scoped before limiting or sampling.
- Readers and Client API bearer tokens only receive preview books visible to their user.
- Shelves do not grant book access; inaccessible shelf items are omitted from previews.
- Group previews use books assigned to that exact group and do not leak hidden assigned books.
- Author and Series previews use books in the matching visible axis. Group-scoped
  Author and Series previews are additionally limited to the exact visible group.
- Public/Common Room previews do not leak hidden books.
- Session auth and bearer auth use the same `request.user` book visibility behavior for preview selection.
- Inaccessible parent resources remain inaccessible as before.

Ordering:

- Group previews are sample-like/random visible books assigned to that exact group. Contents and order may change between requests; clients must not rely on stable order or stable membership.
- Author previews are deterministic by book sort title, title, and id.
- Series previews are deterministic by series index, book sort title, title, and id.
- Shelf previews are stable by shelf item order: `position`, then deterministic fallback.

Client guidance:

- Treat `preview_books` as optional and feature-detect it per endpoint.
- Do not use `preview_books` as a substitute for fetching a full book list or book detail.
- Render a placeholder when `cover_url` is `null`.
- If a preview cover is interactive, clients may open the preview book detail by `id` or open the parent context, but should not infer file/download capability from the preview item.

Book payload notes:

- Book detail payloads include visibility-scoped `groups` summaries. Compact
  Book list, search, and group-scoped Book rows do not include `groups`.
- Books include a singular `file` object (or `null`) rather than `files[]`.
- Books include `cover_url` (string URL) or `null` when no cover is available. `cover_url` points under `/media/covers/` and is part of the normal product/API contract. Cover files are public display assets; raw book media such as `/media/books/...` is not public and EPUB/book content should be delivered only through authenticated app/API endpoints.
- Book write shape: `authors` is a list of Author ids; `series` is an existing Series id, `null`, or `{ "name": "New series" }` to create and assign a series atomically.
- `series_index` accepts integers or one decimal place (e.g. `5` or `5.1`).
- `subtitle` may be patched to an empty string.
- `identifiers[]` response items include `id`, `scheme`, and `value`.
- Compact Book rows use `tags[]`; Book detail and PATCH use `catalog_tags[]`.
  Items in either representation include `id`, `name`, and generated `slug`.
- Compact Book rows expose top-level `file_format`. Book detail exposes file
  metadata only through `file.format`, `file.file_size`, `file.checksum`, and
  authenticated `file.download_url`.
- Book PATCH accepts `identifiers` as a complete replacement list of
  `{"scheme": "...", "value": "..."}` objects. Omitting `identifiers`
  preserves existing rows; `identifiers: []` clears them.
- Book PATCH accepts `catalog_tags` as a complete replacement list of names.
  Omitting it preserves current tags; `catalog_tags: []` clears them.
- Metadata, authors, BookSeries relationship data, identifiers, and Catalog Tags are updated
  transactionally through the single Book detail PATCH endpoint.

Book cover mutation is deliberately separate from metadata PATCH:

- `POST /api/v1/library/books/<book_id>/cover/` accepts multipart field
  `cover` and returns the updated Book detail payload.
- `DELETE /api/v1/library/books/<book_id>/cover/` clears the cover and returns
  the updated Book detail payload. Clearing an empty cover is an idempotent
  success.
- Both operations are session-authenticated and Librarian+ only. Client bearer
  authentication is not accepted.
- Upload content must decode as JPEG, PNG, or WebP and remain within the 10 MiB
  and 20-million-pixel limits. Filenames and supplied MIME types are ignored
  for validation.
- Cover mutation does not change EPUB files, checksums, bibliographic metadata,
  identifiers, groups, shelves, or reading data.

## Imports

- `POST /api/v1/library/imports/`

Library imports are synchronous and session-authenticated for Librarian+ users.
`POST` returns a transient import result with source labels, counts, and safe
per-item results. Import history is not stored and there are no list/detail
import-history endpoints. Client API bearer tokens are rejected.

See `docs/imports.md` for details.

## Groups (LibraryGroups)

LibraryGroups are access scopes, not shelves. Group book lists still filter each
book through current visibility from `library.queries`.

When advanced LibraryGroups are disabled, the group API exposes only the
configured Public/Common Room group. Public list/detail, browse, preview,
book-assignment, and membership operations retain their normal role checks.
The designated Public group's name and description are not writable through
the normal Group PATCH endpoint; the Owner manages them through Server
Settings. Custom group IDs return `404`, and group creation is unavailable. The
feature-state change does not delete or rewrite existing custom-group data.

- `GET /api/v1/library/groups/` (paginated)
- `POST /api/v1/library/groups/` (Owner/Manager only; creates a group)
- `GET /api/v1/library/groups/<group_id>/`
- `PATCH /api/v1/library/groups/<group_id>/` (`name` and/or `description` for a
  custom group; Manager/Owner may rename, while existing curator authority
  governs description updates; designated Public returns `403`)
- `DELETE /api/v1/library/groups/<group_id>/` (Manager/Owner for custom groups;
  designated Public cannot be deleted)
- `GET /api/v1/library/groups/<group_id>/books/` (paginated)
- `POST /api/v1/library/groups/<group_id>/books/` body: `{"book_id": "<book_id>"}`
- `DELETE /api/v1/library/groups/<group_id>/books/<book_id>/`

Group list ordering:

- `GET /api/v1/library/groups/?ordering=name` orders by group name A-Z and is the default.
- Invalid ordering values return `400`.
- Public/Common Room is not forced to the top by this endpoint.

Group book ordering:

Group book list responses use the normal `{count, next, previous, results}`
pagination envelope. Product UI Group View and Group Edit URLs retain the
current `page` and supported book filters while paging.

- `GET /api/v1/library/groups/<group_id>/books/?ordering=title` orders by title A-Z and is the default.
- `GET /api/v1/library/groups/<group_id>/books/?ordering=author` orders by primary/first author name A-Z using the existing author-name display convention, then title/id fallback.
- `GET /api/v1/library/groups/<group_id>/books/?ordering=series` orders by series name A-Z, then `series_index`, title, and id fallback.
- Invalid ordering values return `400`.
- Memberships (Manager/Owner only):
  - `GET /api/v1/library/groups/<group_id>/memberships/` (paginated; readable by group members and by Owner/Manager/Librarian)
  - `POST /api/v1/library/groups/<group_id>/memberships/` body: `{"user_id": "<profile_id>", "is_curator": true}`
  - `PATCH /api/v1/library/groups/<group_id>/memberships/<user_id>/` body: `{"is_curator": false}`
  - `DELETE /api/v1/library/groups/<group_id>/memberships/<user_id>/`

Membership payloads use the generic username-only compact user identity and do
not expose Django auth user database ids:

```json
{
  "user": {
    "profile_id": "8f8cc870-5f5a-41e7-8cf4-62bc56f0db15",
    "username": "reader"
  },
  "is_curator": true,
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z"
}
```

Membership record ids are intentionally not public identifiers. Create bodies and
PATCH/DELETE routes use the user's `profile_id` as `user_id`.

Group book assignment mutation responses are deliberately compact and contain
only `id`, `group_id`, and `book_id`. They do not expose `added_by`.

Group list/detail payloads contain group data and Public identity, without
request-specific capability fields:

```json
{
  "id": "631947a3-ffe9-45b4-9373-b48c81a4fdd4",
  "name": "Fantasy Club",
  "description": "Epic quests, folklore, and imagined worlds.",
  "is_public_group": false
}
```

Product UI group-shelf eligibility comes from `/api/v1/accounts/me/`: Owner,
Manager, and Librarian may manage shelves for any group returned by the group
list; Readers may manage shelves only for matching non-Public memberships with
`is_curator=true`. Endpoint authorization remains authoritative.

Group list/detail payloads support the reusable `include_preview_books=true` opt-in described under [Preview books](#preview-books).

Public restrictions:

- Public cannot have curator assignments (`is_curator=true` is invalid).
- Public is default/fallback, not mandatory: membership may be removed when another group remains; removing a user's final membership restores Public.
- Public is not universal access; Public group visibility follows normal
  LibraryGroup membership rules.
- Librarian/Manager/Owner users may still manage Public book assignments and
  other permitted Public operations through global authority. Public name and
  description remain Owner-managed through Server Settings only.

See `docs/permissions.md` for the visibility/curation rules.

Authorized Manager/Owner users may delete custom groups through the normal API
and Product UI workflow. The designated Public group cannot be deleted.

## Reading

- Reading annotation APIs use compact SPL-native payload fields. The canonical
  portable exchange format is the session-centered Second Pass Library
  Marginalia Profile documented in `docs/specs/marginalia-export.md`.
- Practical current REST examples for reader clients: `docs/reading-rest-examples.md`
- Client API bearer tokens are allowed for reading endpoints (user-owned data; strictly scoped to the token owner).
- Open book bootstrap: `POST /api/v1/reading/books/<book_id>/open/` (returns active session + progress + first page of annotations)
- Active session: `GET /api/v1/reading/books/<book_id>/active-session/`
- Start over: `POST /api/v1/reading/books/<book_id>/start-over/` (returns the same bootstrap shape as `/open/`)
- Sessions (read + limited metadata edits): `GET /api/v1/reading/sessions/` (paginated; supports `?book=<book_id>`, `?status=active|completed|archived`, `?is_active=true|false`, `?q=<text>`), `GET /api/v1/reading/sessions/<id>/`, `PATCH /api/v1/reading/sessions/<id>/` (only `name`, `notes`; active sessions only). Summary list/detail payloads include `book_id`, `can_open`, and compact `book`, not the legacy `book_title` field. When `?book=<book_id>` is present and the book is visible, list responses include `context.book` even if `results` is empty.
- Recent active sessions (compact): `GET /api/v1/reading/sessions/recent/` (default `limit=10`, max `50`; includes `session.name` and `session.progression`; omits inaccessible-book sessions from continue-reading results)
- Batch activity summary: `POST /api/v1/reading/books/activity-summary/` with `{"books": ["<book_id>"]}` returns per-visible-book current-user session counts and active/latest session ids. This endpoint is read-only in meaning but uses POST for practical batch request size.
- Close session: `POST /api/v1/reading/sessions/<session_id>/close/` (marks the session completed/inactive; idempotent)
- Progress: `GET/PUT/PATCH /api/v1/reading/sessions/<session_id>/progress/` (writes require current access to the session's book)
- Annotations: `GET /api/v1/reading/annotations/` (paginated; soft-deleted items are hidden by default; pass `?include_deleted=true` to include them)
  - Filters: `?book_id=<book_id>`, `?session_id=<session_id>`, `?kind=highlight|bookmark` (may be repeated)
  - Ordering: `?ordering=created|-created|modified|-modified`
  - `POST /api/v1/reading/annotations/` supports optional `Idempotency-Key` for safe retries (recommended).
  - `POST /api/v1/reading/annotations/batch/` creates up to 100 annotations for one session in one all-or-nothing request.
- Marginalia export (Django session-authenticated only; Client API bearer tokens rejected):
  - `GET /api/v1/reading/export/` exports all owned current-user sessions, including sessions for books the user can no longer view.
  - `POST /api/v1/reading/export/` exports selected owned books/sessions, including owned sessions for books the user can no longer view.
- Marginalia import preview (Django session-authenticated only; Client API bearer tokens rejected):
  - `POST /api/v1/reading/import/preview/` accepts one uploaded SPL native marginalia JSON export file, validates it, stages the validated payload in `userdata/imports/staged/`, returns an `import_token`, summarizes contents, and reports visible local book matches by file hash only.
  - `GET /api/v1/reading/import/unmatched/?import_token=<token>` downloads a native SPL JSON subset containing staged preview books that could not be matched to visible local books plus malformed-locator sessions from matched books.
- Minimal marginalia import apply (Django session-authenticated only; Client API bearer tokens rejected):
  - `POST /api/v1/reading/import/apply/` requires an `import_token` from preview, re-validates the staged payload, imports matched sessions for visible local books as historical sessions, skips unmatched books, deletes the staged file after success, and does not accept direct file uploads or foreign/provider formats.
  - Optional multipart `selection` JSON limits import to selected export-local sessions and may override imported session `name`/`notes`.

Reading payload notes:

- Marginalia ownership, current book visibility, book-file download access, and current reading/open capability are separate. Owned sessions/annotations remain visible/exportable to their owner after book access loss; current reading/open activity and book-file downloads still require current book visibility.
- Progress uses `current_location` (JSON) as the canonical "where am I?" session state (for EPUB, an EPUB CFI and/or href-based locator).
- `progression` is derived/display metadata (a normalized scalar hint, `0.0 <= progression <= 1.0` when present), not canonical navigation state. It is useful for progress bars and summaries; it should not be used for resume location, annotation anchoring, CFI correctness validation, or cross-device exact positioning. If described as whole-book progress, it is relative to the whole renderable EPUB reading span from first renderable location to last renderable location (not page count, viewport count, chapter-local progress, or byte offset).
- Session list/retrieve payloads include `progression`, `annotation_count`, `can_open`, and a compact `book` summary scoped to the caller's current book visibility. `can_open=false` means the session remains owned/readable, but the related book is not currently available for open/continue/per-book navigation.
- Session search (`?q=<text>`) trims whitespace and searches session-owned `name`/`notes` plus currently visible book `title`, `subtitle`, authors, and series. It does not search annotation bodies, ISBNs, identifiers, marginalia export payloads, or arbitrary client blobs. User-owned session name/notes can match even when related book access is later lost; hidden/inaccessible book metadata cannot match and remains redacted.
- `open`, `active-session`, `start-over`, progress writes, and annotation writes/deletes require current book access. Existing no-access active sessions may still be renamed/noted and closed by their owner.
- Reading activity overlays live under `/api/v1/reading/`, not `/api/v1/library/books/`; catalog book list/detail payloads do not include user-specific session counts, progress, latest session ids, or annotation counts.
- Annotation API payloads use `kind`, `selector`, optional `quote`,
  `highlight_text`, `highlight_color`, and `comment_text`. Internally,
  annotations are stored in compact columns (`selector_kind`/`selector_value`
  plus highlight/comment fields).
- Annotation reads are owner-scoped and remain available after book access loss; annotation writes/deletes require current access to the session's book and an open session.
- Highlight color is a semantic token on highlights. Allowed: `yellow`, `green`, `blue`, `pink`, `purple`, `orange`. Missing/blank highlight color is accepted on create and normalizes to `yellow`; blank highlight color is rejected on PATCH.
- Progress/location payloads are versioned via `profile_version` (current: `0.1.0`). If provided on write, it must match the current server-supported version. Annotation payloads do not include `profile_version`.
- Marginalia import apply is intentionally minimal: no stored import jobs and no annotation-level selection. The product UI supports session-level selection and session name/notes customization.
- Server-side marginalia import is intended for SPL Marginalia Profile files
  only. Foreign/provider-specific formats should be normalized by a client
  through the normal reading APIs or converted by an external tool into the SPL
  Marginalia Profile shape first.
- Marginalia apply imports visible local books matched by file hash only, skips unmatched books, creates new historical/imported sessions, never imports exported active sessions as active local sessions, and treats duplicate findings as warnings rather than blockers. ISBN and title/author fallback matching are intentionally not used for server-side locator import.
- Server-side apply performs shallow CFI-shaped validation only: EPUB CFI values must look like `epubcfi(...)`; the server does not resolve CFIs against EPUB content. Sessions with malformed locators are excluded from server apply and preserved for Reader-assisted import. The import unit is a session; annotation-level selection is not supported. Session selection uses export-local session ids, not SPL database ids.
- Unmatched import download is Product UI/session-authenticated, tied to the current user's staged preview token, and intended for Reader-assisted re-anchoring when the original book file is missing, different, or has malformed locators.
- Export JSON follows the Second Pass Library Marginalia Profile and is nested
  as `books[] -> sessions[] -> annotations[]`; annotations inherit book/session
  context from nesting, annotations belong to reading sessions, and marginalia
  belongs to the user.
- All-scope export uses `scope.type = "all"` and omits books with no exported sessions.
- Selected export uses `scope.type = "selected"` with per-book `session_filter` values of `"all"` or `"selected"`.
- Selected export request body shape is `{"books": [{"book_id": "<uuid>", "sessions": "all"}, {"book_id": "<uuid>", "sessions": ["<session_uuid>"]}]}`.
- Exported sessions use export-local ids such as `session-1`; annotations do not include SPL database annotation ids.
- Deleted annotations are excluded from export.

## Core

- Health check: `GET /api/v1/health/`
- Public discovery: `GET /.well-known/secondpass`
  - `server_name`
  - `server_description`
  - `server_version`
  - `server_release`
  - `server_release_date`
  - `api_base_url`
  - does not include banner text, advanced library group state, capabilities,
    or client route manifests
- Owner server settings: `GET/PATCH /api/v1/server/settings/`
  - `server_name`
  - `server_description`
  - `public_group_name`
  - `public_group_description`
  - `advanced_library_groups_enabled`

Advanced library groups are off by default. Owners enable them with
`POST /api/v1/server/settings/advanced-library-groups/enable/`. Normal
`PATCH /api/v1/server/settings/` does not disable or enable this flag; disabling
after enablement is an operator recovery action through Django admin. While
disabled, normal non-Public group mutation endpoints return forbidden.

See `docs/reading.md` for details.
