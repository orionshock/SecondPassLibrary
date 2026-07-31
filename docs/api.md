# API

All endpoints are under `/api/v1/` and require authentication unless stated otherwise.

## Authentication

All `/api/v1/` endpoints require authentication unless a specific endpoint explicitly documents anonymous access.

Current supported authentication methods:

- Django session authentication for the React Product UI
- Explicit Client API bearer tokens on selected reader-client endpoints
- Session login/logout is provided by `/login/` and `/logout/`; API responses are JSON-only.
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
- `page_size` (optional; default `20`, max `200`)

Endpoint-specific defaults may be smaller. Reading Session lists default to
`10`; explicit positive page sizes remain supported up to the normal maximum.

Response shape:

```json
{
  "count": 123,
  "next": "http://.../?page=2",
  "previous": null,
  "results": []
}
```

## Marginalia Books

The new Marginalia API currently exposes one bounded historical Book
projection:

- `GET /api/v1/marginalia/books/`
- `GET /api/v1/marginalia/books/<book_id>/`
- `GET /api/v1/marginalia/books/<book_id>/sessions/`
- `POST /api/v1/marginalia/books/<book_id>/open/`
- `GET /api/v1/marginalia/books/<book_id>/active-session/`
- `POST /api/v1/marginalia/books/<book_id>/start-over/`
- `GET /api/v1/marginalia/sessions/`
- `GET /api/v1/marginalia/sessions/recent/`
- `GET/PATCH /api/v1/marginalia/sessions/<session_id>/`
- `GET/PUT /api/v1/marginalia/sessions/<session_id>/progress/`
- `POST /api/v1/marginalia/sessions/<session_id>/close/`
- `GET /api/v1/marginalia/sessions/<session_id>/annotations/`
- `POST /api/v1/marginalia/sessions/<session_id>/annotations/batch/`
- `GET /api/v1/marginalia/export/`
- `POST /api/v1/marginalia/export/`
- `POST /api/v1/marginalia/import/preview/`

Marginalia read and lifecycle routes accept Django session or Client API
bearer authentication. Export is session-authenticated only. The caller must
own at least one Marginalia Reading Session for a Book; current Library
visibility is not required. The projection contains only `id`, `title`, ordered
`authors`, optional `series` (including `series_index`), public `cover_url`,
`can_open`, caller-scoped `session_count` and `active_session_count`, and
`last_activity_at`. `can_open` independently reflects current Library
visibility. A historical projection with `can_open=false` can still include the
public cover display URL, but never includes EPUB/file data or download access.

The list uses normal `page`/`page_size` pagination and accepts `q` over title,
author names, and Series name. Default ordering is newest caller-owned
Marginalia activity first. Books without caller-owned Sessions and missing
Books use the same no-leakage `404` detail behavior. See `docs/marginalia.md`
for the full field and ownership contract.

The Book lifecycle routes share a bootstrap response containing canonical Book
context, active Session detail and progress, the complete active-Session
Annotation collection, and the first normal page of closed Sessions. `open/`
accepts optional `name` and `notes` creation defaults and returns `201` when it
creates or `200` when it reuses. `active-session/` is read-only and returns a
null Session when none is active. `start-over/` requires `Idempotency-Key`,
accepts optional final `name`, `notes`, and complete `{cfi, location_label}`
progress, and returns `201`; identical retries replay the stored response while
key reuse with different input returns `409`. All require current Library
authority but return no asset or file data. Library owns asset acquisition and
failure behavior.

The nested Sessions route returns a normally paginated `results` collection
and the canonical selected Book summary in `context.book`. Omitted `status`
means all caller-owned Sessions; `status=active` and `status=closed` select the
two lifecycle states. `q` searches only Session name and notes. Results use
newest Session/progress/non-deleted-annotation activity ordering. Empty filtered
pages retain the Book context, while missing and unowned parent Books return
the normal no-leakage `404`.

The new Marginalia lifecycle has only `active` and `closed`. Opening a Book's
Session returns the existing active Session when present and never closes it
automatically. Creating a later Session requires a prior explicit close; having
only closed Sessions and no active Session is valid.

Saved progress is held atomically on its Reading Session as an opaque CFI,
optional Reader-generated location label, and update timestamp. There is no
numeric progression field or separate progress record. Current list responses
use the progress timestamp for activity ordering but do not expose progress.
Detail and progress responses use `progress: null` or a bounded
`{cfi, location_label, updated_at}` object.

Session detail returns the canonical Marginalia Book summary in `context.book`
and the bounded detail projection in `session`. Only the owner may read it;
current Library visibility is not required. `PATCH` accepts only `name` and
`notes`, only for active Sessions, and returns the same envelope. Closed
Sessions are immutable, and foreign or missing Sessions use the same
no-leakage `404` response.

Progress `GET` is owner-readable for active and closed Sessions without a
current Library-access requirement and never creates state. Progress `PUT`
atomically replaces the complete `{cfi, location_label}` location and assigns
its timestamp on the server. Writes require an active Session plus current
Library authority for the Book. Unknown fields are rejected; progress has no
`PATCH` or `DELETE` route.

Close accepts optional final `name`, `notes`, and complete `progress`, commits
them with the lifecycle change under one row lock, and returns the normal
Session detail envelope. Close without final progress remains available after
Library access loss; final progress requires current Library authority.
Marginalia checks that Library policy but never serves or diagnoses the Book
asset. Empty or identical retries are idempotent, while attempts to alter an
already closed Session return a bounded `SESSION_CLOSED` conflict. Live
timestamps are server-assigned; canonical import may later preserve validated
source timestamps.

Session Annotation GET returns all current non-deleted Annotations without
pagination in `{"annotations": [...]}`. It is owner-readable for active and
closed Sessions without current Library access. Canonical rows use
`id`, Session-scoped `client_id`, `kind`, opaque `{cfi, location_label}`
location, timestamps, and a highlight-only body containing `text`, `prefix`,
`suffix`, `color`, and `note`. Bookmarks have no body. Results order nonblank
location labels lexically, then use CFI, creation time, and id as stable
fallbacks for blank labels.

The Session-scoped batch route accepts one to 100 strict `upsert` or `delete`
operations. Upsert creates, updates, or restores by `client_id`; delete
soft-deletes by `client_id`. Session/client-id uniqueness and a transaction
make retries duplicate-safe. The complete batch validates before mutation,
requires an active owned Session and current Library Book authority, and
returns the complete authoritative non-deleted collection in reading order.
Duplicate client ids within one request are rejected. Marginalia consults
Library authority but never inspects or serves the Book asset.

The flat Sessions route returns caller-owned Sessions across all Books with
normal Session-level pagination. It supports `status=active|closed` and `q`
over Session name/notes plus Book title, author names, and Series name. Each row
contains only a bounded Book reference: `id`, `title`, public `cover_url`, and
independently computed `can_open`. It does not repeat the canonical full
Marginalia Book summary or expose Library file/download data.

It also accepts `has_annotations=true|false`. `true` means at least one
non-deleted Annotation; `false` means none; omission does not filter. Filtering
occurs before pagination/counting, and soft-deleted rows do not count.

Complete `GET /api/v1/marginalia/export/` and selective
`POST /api/v1/marginalia/export/` return canonical JSON attachments. GET
accepts optional `include_empty_sessions`; POST accepts:

```json
{
  "reading_session_ids": ["<session-uuid>"],
  "include_empty_sessions": false
}
```

Selected IDs must be nonempty, unique, and caller-owned. Missing or foreign
IDs return no-leakage `404` without partial output. Empty Sessions are excluded
by default; explicit inclusion applies identically to complete and selective
exports. No surviving Sessions, a missing Book checksum, or conflicting Book
hashes returns bounded `409`. Current Library access is not required.

Successful responses use `application/json; charset=utf-8` and attachment
filename `YYYYMMDD-second-pass-marginalia.json`, with the server-local date.
Archive `generatedAt` remains precise. The canonical archive has no scope field
and contains no file/download projection.

`POST /api/v1/marginalia/import/preview/` is session-authenticated only and
accepts multipart `file` plus optional `include_empty_sessions` (default
`false`). Uploads are bounded at 25 MiB and validated by the canonical runtime
archive codec. A successful response is not an import; it creates no Marginalia
records and returns an opaque two-hour `import_token`, the staged policy,
summary and matched/unmatched counts, bounded warnings, and explicit Book and
Reading Session candidate identities. Example candidate structure:

```json
{
  "import_token": "<opaque-token>",
  "include_empty_sessions": false,
  "can_apply": true,
  "summary": {
    "book_count": 1,
    "reading_session_count": 1,
    "annotation_count": 12
  },
  "matched_book_count": 1,
  "unmatched_book_count": 0,
  "unmatched_reading_session_count": 0,
  "unmatched_downloadable_reading_session_count": 0,
  "warnings": [],
  "books": [{
    "candidate_id": "book-000001",
    "file_hash": "sha256:<checksum>",
    "title": "Book title",
    "authors": ["Author"],
    "match": {"status": "matched", "book_id": "<local-book-uuid>"},
    "reading_sessions": [{
      "candidate_id": "reading-session-000001",
      "source_reading_session_id": "source-session-1",
      "source_status": "active",
      "will_import_as_status": "closed",
      "annotation_count": 12,
      "will_import": true,
      "possible_duplicate": false
    }]
  }]
}
```

Matching is exact `fileHash` against currently accessible Library Books. No
metadata fallback or EPUB/CFI inspection occurs. Empty Sessions are omitted
unless explicitly included; that stored choice governs future Apply and
unmatched-download behavior. Multiple accessible Books with one checksum, no
surviving Sessions, malformed archives, and staging failures return bounded
errors without leaving a stage. Apply and unmatched download are not yet
exposed under the canonical Marginalia API.

The Dashboard-oriented `GET /api/v1/marginalia/sessions/recent/` route returns
`{"results": [...]}` without pagination. It defaults to the 10 most recently
active caller-owned Sessions; `limit` is bounded from 1 through 50 and
`include_closed=true` includes closed Sessions. Activity ordering uses Session,
progress, and non-deleted Annotation updates before applying the database
limit. Rows are not deduplicated by Book and expose only Session id, name,
status, last activity, and the bounded Book id/title/cover/`can_open` reference.

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

Managed user list queries are server-filtered and paginated. `q` searches
username, first name, last name, display name, and management-visible email.
`role` accepts `owner`, `manager`, `librarian`, and `reader`; `curator` is also
available when advanced Library Groups are enabled and means any user with a
curator membership, not a global account role. `is_active` accepts `true` or
`false`. `ordering` accepts `username`, `name`, `role`, and `is_active`, with a
leading `-` for descending order. Name ordering uses last name, first name,
username, and id. Role ordering uses Owner, Manager, Librarian, Reader rank,
then username/id. The default is `username`. Invalid filter or ordering values
return `400`. Existing `page` and `page_size` pagination applies after filters.

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
They are also not enabled for Marginalia Export or the old reading
import/export workflows; these remain Product UI/session-authenticated.

Discovery:

- `GET /.well-known/secondpass` returns compact server identity and
  `api_base_url`. It is public discovery and does not include banner text,
  advanced group state, capabilities, or per-endpoint route metadata.
- `GET /api/v1/client-api/discovery/` returns the detailed Client API pairing
  discovery document.
- Authenticated clients should refresh `GET /api/v1/accounts/me/` for current
  user context and `GET /api/v1/server/info/` for server-wide display context.

Client API route conventions under `api_base_url`:

- `{api_base_url}client-api/discovery/`
- `{api_base_url}client-api/login-requests/`
- `{api_base_url}client-api/login-requests/{id}/poll/`
- `{api_base_url}client-api/pairing/lookup/` (authenticated Product UI session)
- `{api_base_url}client-api/pairing/decision/` (authenticated Product UI session)

Login request / authorization:

- `POST /api/v1/client-api/login-requests/` (anonymous allowed)
- Login-request creation returns `authorize_url` rooted at `/profile/client-pairing` with the human code prefilled.
- React pairing approval looks up and approves/denies a code through the authenticated pairing endpoints. Client API discovery and login-request responses do not advertise a separate browser authorization page.
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

- Owner may create `manager`, `librarian`, or `reader`. Manager may create only `librarian` or `reader`; other callers are denied. Owner is not a creatable managed role.
- The temporary password is never stored except via Django's normal password hash.
- The password is not emailed and is not shown by any list/detail endpoint after creation.
- Newly-created managed users are marked `must_change_password=true` (force change on first login).

### `GET /api/v1/accounts/me/` response

`/accounts/me/` is the current-user context endpoint for authenticated clients:

- Who am I?
- What global role do I have?
- Am I an Owner?
- Which LibraryGroups am I a member of?
- Which group memberships are marked as curator/steward relationships?

It includes a `groups` array listing the caller's `LibraryGroupMembership`s.

Each `groups[]` item includes:

- `id`, `name`
- `is_public_group`
- `is_curator: true` only for curator memberships; omitted otherwise

Example `groups[]` item:

```json
{
  "id": "631947a3-ffe9-45b4-9373-b48c81a4fdd4",
  "name": "Fantasy Club",
  "is_public_group": false,
  "is_curator": true
}
```

`/accounts/me/` uses sparse true-only capability flags. `is_owner`, `must_change_password`, `can_access_django_admin`, and `groups[].is_curator` are present only when true and omitted otherwise. First-party SDKs normalize missing flags to stable `false` booleans for application code.

Global `role` and `is_owner` describe broad account authority. `groups[].is_curator` describes explicit stewardship on that exact membership. It is not a global role and there is no derived group-id bootstrap list. `can_access_django_admin` is included only for an Owner when Django Admin is enabled; it exposes neither raw settings nor an admin route manifest.

Additional identity fields:

- `first_name`, `last_name`
- `must_change_password` (force change via product UI redirect)

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
- `POST /api/v1/shelves/` (create; user-owned or group-owned depending on permissions; `name` is required and limited to 255 characters)
- `GET /api/v1/shelves/<id>/`
- `PATCH /api/v1/shelves/<id>/` (partial update; name/description/visibility only)
- `PUT /api/v1/shelves/<id>/` (unsupported; returns `405`)
- `DELETE /api/v1/shelves/<id>/`
- Items:
  - `GET /api/v1/shelves/<id>/items/` (paginated; books are filtered through access policy)
  - `GET /api/v1/shelves/<id>/items/?view=edit` (editor inventory; all stored slots with safe unavailable placeholders)
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
  - `GET /api/v1/shelves/?ordering=-name` orders by shelf name Z-A, then stable id fallback.
  - `GET /api/v1/shelves/?ordering=item_count` orders by lowest viewer-visible item count first, then name/id fallback.
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
  shelves are omitted from list responses and return `404` from direct detail
  when this viewer-scoped count is zero. Shelf owners still see their own empty
  shelves. Librarian+ roles do not bypass this user-owned shelf rule. Visible
  group-owned shelves remain readable when empty because their visibility is
  determined by group scope rather than item count. Session and bearer reads
  use the same policy.
- Shelf create returns the same complete Shelf summary shape as list/detail,
  including `item_count: 0` for the new empty shelf.
- User-owned shelves include `owner_user` as a compact user object with `profile_id` and `username`; group-owned shelves have `owner_user: null`.
- Shelves include `created_by` as the same compact user object when known. Shelf item `added_by` uses this shape too. These compact user objects do not include Django auth user database ids, email addresses, or profile/admin metadata.
- Shelf item payloads include a compact `book` object that includes `cover_url` (or `null`) when a cover is available.
- The nested Shelf item `book` uses the same compact Book shape as Library browse
  and Group Book lists: `id`, title/sort title/subtitle, ordered Authors,
  Series with `series_index`, `catalog_tags`, language, publisher, precision-aware
  publication components, `cover_url`, and `file_format`. It excludes Groups,
  identifiers, description, detailed file/download metadata, checksum, and
  storage/source/provenance fields. Shelf item id, shelf id, position, and
  `added_by` remain fields of the Shelf item rather than the nested Book.
- Normal Shelf item reads return only viewer-visible Books. Their pagination
  `count` is the visible item count and every result has a compact `book`.
- `view=edit` is available only when the request context can edit the Shelf.
  Readable but non-editable Shelves return `403`; unreadable Shelves remain
  `404`. Its pagination operates over every stored ShelfItem slot, so `count`
  is the total stored count. The envelope also includes
  `visible_item_count` and `unavailable_item_count`. Results remain in stored
  position order; any supplied ordering other than `position` returns `400` in
  this representation. Unknown `view` values return `400`.
- Visible `view=edit` rows include the ordinary compact `book` and
  `unavailable: false`. Retained hidden rows contain only ShelfItem identity,
  shelf identity, zero-based position, `unavailable: true`, `book: null`, and
  the bounded compact `added_by` value. They expose no hidden Book identity,
  title, authors, series, cover, tags, identifiers, file, Group, storage,
  source, or provenance data.
- Shelf create, Shelf PATCH, item add, and item PATCH reject unknown fields with
  structured `400` field errors. Shelf PATCH accepts only `name`, `description`,
  and `visibility`; `name`, when supplied, is limited to 255 characters.
- Group-owned Shelf creation requires `owner_group`; omission returns a
  structured `owner_group` field error. Malformed group ids return `400`, while
  missing or inaccessible groups return `404`. A visible group for which the
  caller lacks creation authority remains a permission error. User-owned Shelf
  creation rejects a supplied `owner_group` with a structured field error.
- Shelf item add requires `book` as a UUID. Malformed values return `400`.
  Valid missing Books and Books outside the Shelf editor's eligible Book scope
  both return `404`; lack of authority over the Shelf itself remains `403`.
  Adding a Book already on the Shelf returns `400` under the `book` field.
- Malformed Shelf item ids on PATCH/DELETE return the same bounded `404` as
  missing or unavailable item ids.
- Public/Common Room group shelves use the ordinary group-shelf contract in
  simple and advanced modes. In simple mode they remain manageable by
  Librarian, Manager, and Owner sessions; Public has no Reader curators.
- Deleting a Shelf returns `204` and cascades only its ShelfItem rows. It does
  not delete Books, EPUB/cover assets, reading sessions, annotations, or Book
  group assignments.
- Shelf item positions are stored as contiguous zero-based integers. Item
  mutations lock the Shelf and its stored item rows before calculating or
  changing positions. If multiple items are requested at the same position
  during add/import-style writes, that cluster is canonicalized by book title,
  then stable IDs, and later items are bumped.
- `move=up|down` moves a visible item to the nearest visible slot in that
  direction. Retained unavailable placeholders are locked: the move skips them
  and leaves their stored positions unchanged. A boundary move remains a
  successful no-op. PATCH on an unavailable item returns bounded `404`.
- Patching an existing item with `position` remains a zero-based move-to
  operation when every stored item is available. When unavailable retained
  items exist, direct positioning returns `400` under `position` instead of
  ambiguously moving through locked slots.
- POST with a non-null `position` is likewise rejected under `position` when
  unavailable retained items exist. Omitting `position` appends after all
  stored slots, including unavailable placeholders.
- Shelf item list ordering:
  - `GET /api/v1/shelves/<id>/items/?ordering=position` orders by stored shelf position and is the default.
  - `GET /api/v1/shelves/<id>/items/?ordering=-position` orders by stored shelf position in reverse.
  - `GET /api/v1/shelves/<id>/items/?ordering=title` orders the response by contained book title.
  - `GET /api/v1/shelves/<id>/items/?ordering=-title` orders the response by contained book title descending.
  - `GET /api/v1/shelves/<id>/items/?ordering=author` orders the response by contained book primary author name using the same author-name ordering convention as book display.
  - `GET /api/v1/shelves/<id>/items/?ordering=-author` reverses the author ordering.
  - Invalid ordering values return `400`.
  - Title/author ordering is response/view ordering only and does not mutate stored `ShelfItem.position`; move/reorder endpoints continue to operate on stored positions.
- Product/UI displays may show one-based labels such as `#1`, `#2`, etc. React
  reorder controls remain deferred; the editor representation supplies the
  locked placeholder contract needed for a later safe implementation.
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

- Authors: `GET/POST /api/v1/library/authors/` (GET is paginated), `GET/PATCH/DELETE /api/v1/library/authors/<id>/`
- Series: `GET/POST /api/v1/library/series/` (GET is paginated), `GET/PATCH/DELETE /api/v1/library/series/<id>/`
- Catalog Tags: `GET /api/v1/library/tags/` (paginated), `GET /api/v1/library/tags/<id>/`
- Books: `GET /api/v1/library/books/` (paginated),
  `GET/PUT/PATCH /api/v1/library/books/<id>/`

### Book response shapes

Book list, broad-search, and group-scoped Book results share one compact row
shape:

- `id`, `title`, `sort_title`, and `subtitle`
- `authors`, `series`, and `catalog_tags`
- `language` and `publisher`
- `published_year`, `published_month`, `published_day`, and
  `published_date_precision`
- `cover_url` and top-level `file_format`

Compact rows do not include `file`, `groups`, `identifiers`, descriptions,
checksums, file sizes, download URLs, or storage/source fields.

Book detail, Book metadata PATCH/PUT responses, and cover replacement/clear
responses share the detail shape. It includes normal Book metadata plus
`identifiers`, `catalog_tags`, visibility-scoped `groups`, and `file`. It does
not include top-level `file_format`.

`file` is `null` when no stored file is available. Otherwise it contains only:

```json
{
  "format": "epub",
  "file_size": 123456,
  "checksum": "sha256 checksum",
  "download_url": "/api/v1/library/books/<book_id>/download/"
}
```

Book detail responses include a read-only `groups` array containing only group
assignments visible to the caller. Each summary contains `id`, `name`,
`description`, and `is_public_group`; membership records and users are not
included. In simple mode this array may include Public/Common Room, while
custom groups remain hidden. This API representation does not imply a Product
UI relationship tab: Book Detail hides its Groups tab in simple mode. Book list
rows do not include `groups`.

### Book search

`GET /api/v1/library/books/?q=<term>` is the Books browse-axis search and
matches title and sort title only.

`GET /api/v1/library/search?q=<term>` is the broad library book search. It
is a GET-only, Books-only endpoint, not a mixed-result search. It returns
compact Book rows in the normal paginated envelope and searches
visible Books by title, sort title, subtitle, author names, series name,
identifier values, Catalog Tag names, publisher, and description. Missing or
blank `q` returns an empty page rather than the whole library. Supported
ordering is `title`, `-title`, `author`, `-author`, `series`, and `-series`;
the default is `title`.

Broad library book search supports `exclude_shelf=<shelf_id>` for a manageable
shelf and `exclude_group=<group_id>` for a manageable group. These suppress already
contained/assigned Books after visibility scoping. Unknown or inaccessible
exclusion objects return `404`. Search rows use the Book list shape and never
include download URLs, checksums, storage/source names, file keys, or group
membership data. Session and client bearer GET requests use the same
visibility rules.

Book-to-group assignment endpoints (used by Groups UI and Book Edit UI):

- `GET /api/v1/library/groups/<group_id>/books/`
- `POST /api/v1/library/groups/<group_id>/books/` body: `{"book_id": "<book_id>"}`
- `DELETE /api/v1/library/groups/<group_id>/books/<book_id>/`

The Group Books GET endpoint accepts `exclude_shelf=<shelf_id>` for Add Books
candidate discovery. The Shelf must be readable and owned by the path Group.
Malformed ids return a structured `400`; missing or inaccessible Shelves return
`404`; a readable Shelf owned by another Group (or a user) returns a structured
`exclude_shelf` field error. The exclusion composes with normal Group Book
search, tag/author/series/publisher filters, ordering, and pagination.

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

### EPUB download and covers

Book detail `file` data contains format, size, checksum, and the authenticated
`download_url`. `GET /api/v1/library/books/<book_id>/download/` streams the
caller's visible canonical EPUB as an `application/epub+zip` attachment for
session or bearer authentication. The attachment filename is generated from
the sanitized, bounded Book title; it never uses the content-addressed storage
name. Fileless or unsupported-format Books return bounded `409
BOOK_FILE_UNAVAILABLE`; missing or unreadable storage returns the same bounded
code with `503` and no storage detail when the failure occurs before streaming
starts. A storage read failure after response streaming has begun terminates the
stream and is recorded in the bounded operator log; HTTP status cannot be
replaced after headers have been sent.

The download endpoint currently returns the complete file with `200`; byte
Range requests are not implemented. `cover_url` continues to use the public
display-only `/media/covers/` namespace; a Book detail response returns
`cover_url: null` when its configured cover cannot be found or resolved so the
client can use its normal cover placeholder. Cover mutation remains
session-only.

Author/Series payload notes:

- Author and Series POST/PATCH/DELETE are Django-session-only Librarian+ catalog
  operations. Author writes accept exactly `name`, `sort_name`, and `biography`;
  Series writes accept exactly `name`, `sort_name`, and `summary`. POST requires
  `name`; PATCH is partial and preserves omitted fields. Unknown fields return a
  structured `400` keyed by the rejected field. PUT is unsupported and returns
  `405`. Client bearer credentials remain read-only.
- Author and Series reads are role-scoped without a special query mode.
  Reader sessions and bearer clients receive entities derived from Books visible
  to that caller, so unattached entities are excluded and `book_count` counts
  visible matching Books. Librarian+ sessions receive the full catalog by
  default, including unattached and hidden-only entities, with total attached
  Book counts. Catalog Tag filtering narrows the caller's Book scope before
  deriving entities and counts.
- Names maintain an indexed, non-unique normalized value using Unicode NFKC,
  collapsed whitespace, trim, and case-folding while preserving punctuation.
  Normalized matches are advisory and do not block duplicate creation.
- `sort_name` is writable and drives `ordering=name` when nonblank, with `name`
  as the fallback. Submitting a blank sort name stores the current display name;
  omitting it from PATCH preserves the existing value.
- DELETE returns `204` for an unattached entity. Attached Authors and Series are
  not detached automatically and return bounded `409 AUTHOR_IN_USE` or
  `409 SERIES_IN_USE` errors. React's first lifecycle slice does not expose
  deletion.
- Author display names are not unique in the current catalog model, so POST
  deliberately creates a new Author when the same display name already exists.
  The response uses the normal Author axis shape (`id`, `name`, `sort_name`,
  `biography`, and `book_count`, initially zero). Creation does not assign a
  Book. Client bearer credentials are rejected even for privileged accounts.
- Author and Series payloads include role-scoped `book_count` (read-only):
  total attached Books for Librarian+ sessions and visible matching Books for
  Reader sessions and bearer clients.
- Author and Series list/detail payloads may opt into `preview_books` with
  `include_preview_books=true`; preview items are visibility-scoped and use
  the reusable preview shape described below. Tags do not currently attach
  preview books.
- Author list ordering:
  - `name` (default), `-name`, `book_count`, and `-book_count` are supported.
  - Book-count ordering uses the role-scoped `book_count`, then name/id fallback.
  - Invalid ordering values return `400`.
- Series list ordering:
  - `name` (default), `-name`, `book_count`, and `-book_count` are supported.
  - Book-count ordering uses the role-scoped `book_count`, then name/id fallback.
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

Tag endpoints are count/filter facets. They do not accept
`include_preview_books` and do not return `preview_books`.
Clients that need every Catalog Tag for a facet rail should request a large
numeric `page_size` (up to `200`) and follow `next` until it is `null`.

Book, Author, and Series list endpoints accept the compact query parameter
`tag=<slug>`, which filters by Catalog Tag slug. Books are
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

- Book lists accept `author=<author_uuid>` and `series=<series_uuid>`. Malformed
  UUIDs return `400`. A well-formed UUID that is missing, deleted, or has no
  caller-visible matching Books returns the normal empty paginated response;
  the response does not reveal whether the catalog entity exists. These filters
  compose with `tag`, `q`, `ordering`, `page`, and `page_size`.

- `GET /api/v1/library/books/?ordering=title` orders by title A-Z and is the default for general book browsing and author-filtered book browsing.
- `GET /api/v1/library/books/?ordering=author` orders by primary/first author name A-Z using the existing author-name display convention, then title/id fallback.
- `GET /api/v1/library/books/?ordering=series` orders by series name A-Z, then `series_index`, title, and id fallback.
- `GET /api/v1/library/books/?series=<series_id>` defaults to `series_index` ordering.
- `GET /api/v1/library/books/?series=<series_id>&ordering=series_index` orders by `series_index` ascending, nulls last, then title/id fallback.
- Book list ordering accepts `title`, `author`, `series`, `series_index`, and
  `publisher`, plus the descending `-` form of each value.
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

Book endpoints do not attach `preview_books` because they already return Books.
Catalog Tag endpoints do not accept the preview option and remain count/filter
facets without preview cards.

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

Book write and media notes:

- Books include a singular `file` object (or `null`) rather than `files[]`.
- Books include `cover_url` (string URL) or `null` when no cover is available. `cover_url` points under `/media/covers/` and is part of the normal product/API contract. Cover files are public display assets; EPUB content is delivered through authenticated app/API endpoints.
- Book PATCH/PUT accepts only `title`, `sort_title`, `subtitle`, `description`,
  `publisher`, `language`, `published_year`, `published_month`,
  `published_day`, `published_date_precision`, `authors`, `series`,
  `series_index`, `identifiers`, and `catalog_tags`. Unknown or read-only fields
  return structured `400` field errors instead of being ignored. In particular,
  cover, file, checksum, group, storage/source, and timestamp fields are not
  writable through this endpoint.
- `sort_title` is writable and may be blank. PATCH and PUT both retain partial
  update semantics: omitted writable fields preserve their current values.
- Book write shape: `authors` is a list of Author ids; `series` is an existing Series id, `null`, or `{ "name": "New series" }` to create and assign a series atomically.
- Duplicate Author ids are deduplicated server-side while preserving the first
  occurrence order. An empty list clears all Author relationships.
- `series_index` accepts only values greater than zero with at most one decimal
  place (for example `5` or `5.1`). Book list/detail responses serialize a
  present index with one decimal place (`5.0`, `5.1`). Null clears the index;
  omission preserves it. A non-null index without a target Series is a field
  validation error. Clearing `series` removes the BookSeries relationship.
- `subtitle` may be patched to an empty string.
- Publication dates are validated against their declared precision. Year
  precision requires only a year; month precision requires year/month and no
  day; day precision requires all components. Month/day values must form a real
  Python calendar date, so impossible dates such as `2025-02-31` are rejected.
  Blank precision retains the established no-precision behavior.
- `identifiers[]` response items include `id`, `scheme`, and `value`.
- Items in compact and detail `catalog_tags[]` contain `id`, `name`, and
  generated `slug`; see the canonical response shapes above.
- Book PATCH accepts `identifiers` as a complete replacement list of
  `{"scheme": "...", "value": "..."}` objects. Omitting `identifiers`
  preserves existing rows; `identifiers: []` clears them. Identifier row ids
  are response-only and are not accepted in write objects. Unknown nested
  identifier fields are rejected rather than ignored.
- Identifier PATCH schemes are the canonical values `isbn_10`, `isbn_13`,
  `asin`, `doi`, `oclc`, `lccn`, `openlibrary`, `calibre`, `epub_uid`,
  `publisher`, `uri`, `uuid`, and `other`. Scheme aliases recognized while
  importing EPUB metadata are normalization inputs for import only; they are
  not Book PATCH values.
- Book PATCH accepts `catalog_tags` as a complete replacement list of names.
  Omitting it preserves current tags; `catalog_tags: []` clears them.
- Scalar metadata, Authors, BookSeries relationship data, identifiers, and
  Catalog Tags are updated atomically through the single Book detail PATCH/PUT
  endpoint. Validation failure in any supplied field rolls back the complete
  update.

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
- A primary cover storage failure returns bounded `503
  BOOK_COVER_UNAVAILABLE` without exposing storage paths or backend exception
  text. Failure to delete an old cover after a successful replace or clear is
  best-effort operator cleanup: the mutation remains successful and the
  cleanup failure is logged.

## Imports

- `POST /api/v1/library/imports/`

Library imports are synchronous and session-authenticated for Librarian+ users.
`POST` returns a transient import result with source labels, counts, and safe
per-item results. Import history is not stored and there are no list/detail
import-history endpoints. Client API bearer tokens are rejected.

Each item contains `status`, `source_label`, and bounded `safe_message`. When
an item is associated with a Book (including imported, duplicate, and conflict
results), it also contains the existing `book_id`, `title`, an ordered `authors`
array of display-name strings, and optional `series` and decimal-string
`series_index` fields. Failed or skipped items without a Book omit those Book
summary fields. These summaries do not include checksums, storage identities,
filesystem paths, or archive internals.

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

Group creation and metadata updates accept only `name` and `description`.
Create requires `name`; PATCH is partial. Supplied names are trimmed, must be
nonblank, and may contain at most 255 characters. Descriptions may be blank,
and duplicate group names are allowed. Unknown fields return structured `400`
errors. Group metadata uses PATCH; PUT is unsupported and returns `405`.

Group list ordering:

- `GET /api/v1/library/groups/?ordering=name` orders by group name A-Z and is the default.
- `GET /api/v1/library/groups/?ordering=-name` orders by group name Z-A.
- Invalid ordering values return `400`.
- Public/Common Room is not forced to the top by this endpoint.

Group book ordering:

Group book list responses use the normal `{count, next, previous, results}`
pagination envelope. React owns any UI paging state built on this API.

- `GET /api/v1/library/groups/<group_id>/books/?ordering=title` orders by title A-Z and is the default.
- `GET /api/v1/library/groups/<group_id>/books/?ordering=author` orders by primary/first author name A-Z using the existing author-name display convention, then title/id fallback.
- `GET /api/v1/library/groups/<group_id>/books/?ordering=series` orders by series name A-Z, then `series_index`, title, and id fallback.
- Group Book ordering accepts the normal Book-list values: `title`, `author`,
  `series`, `series_index`, and `publisher`, plus the descending `-` form of
  each value.
- Invalid ordering values return `400`.
- Memberships (Manager/Owner only):
  - `GET /api/v1/library/groups/<group_id>/memberships/` (paginated; readable by group members and by Owner/Manager/Librarian)
  - `POST /api/v1/library/groups/<group_id>/memberships/` body: `{"user_id": "<profile_id>", "is_curator": true}`
  - `PATCH /api/v1/library/groups/<group_id>/memberships/<user_id>/` body: `{"is_curator": false}`
  - `DELETE /api/v1/library/groups/<group_id>/memberships/<user_id>/`

Membership POST accepts only `user_id` and `is_curator`; membership PATCH
accepts only `is_curator`. These endpoints do not accept or change global user
roles. Global role changes belong to the managed Users API. Unknown membership
fields, including `role`, return structured `400` errors.

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

`GET /api/v1/library/groups/?book=<book_uuid>` filters the paginated Group
list to caller-visible Groups containing that Book. The filter composes with
`q`, `ordering`, pagination, and `include_preview_books=true`; response rows
retain the normal Group-list shape. A malformed UUID returns structured `400`
under `book`. A well-formed missing or caller-inaccessible Book, or a Book with
no caller-visible matching Groups, returns an empty paginated page so the
collection filter does not disclose Book existence. Simple mode continues to
restrict the Group API to Public/Common Room.

Public restrictions:

- Public cannot have curator assignments. Membership POST/PATCH with
  `is_curator=true` returns `400` with an `is_curator` field error.
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

- Marginalia uses the canonical native Session, location, progress, highlight,
  and bookmark shapes documented in
  `docs/specs/reading-session-annotation-profile/`. The archive envelope is
  documented separately in `docs/specs/marginalia-export.md`.
- Practical current REST examples for reader clients: `docs/reading-rest-examples.md`
- Client API bearer tokens are allowed for reading endpoints (user-owned data; strictly scoped to the token owner).
- Open book bootstrap: `POST /api/v1/reading/books/<book_id>/open/` (returns active session + progress + first page of annotations)
- Active session: `GET /api/v1/reading/books/<book_id>/active-session/`
- Start over: `POST /api/v1/reading/books/<book_id>/start-over/` (returns the same bootstrap shape as `/open/`)
- Sessions (read + limited metadata edits): `GET /api/v1/reading/sessions/` (paginated with default page size `10`; supports `?book=<book_id>`, `?status=active|completed|archived`, `?is_active=true|false`, `?q=<text>`), `GET /api/v1/reading/sessions/<id>/`, `PATCH /api/v1/reading/sessions/<id>/` (only `name`, `notes`; active Sessions only). PATCH is owner-scoped and returns the updated detail projection. Summary list/detail payloads include `book_id`, `can_open`, and compact `book`, not the legacy `book_title` field. When `?book=<book_id>` is present and the book is visible, list responses include `context.book` even if `results` is empty.
- Recent active sessions (compact): `GET /api/v1/reading/sessions/recent/` (default `limit=10`, max `50`; includes `session.name` and `session.progression`; omits inaccessible-book sessions from continue-reading results)
- Batch activity summary: `POST /api/v1/reading/books/activity-summary/` with `{"books": ["<book_id>"]}` returns per-visible-book current-user session counts and active/latest session ids. This endpoint is read-only in meaning but uses POST for practical batch request size.
- Close session: `POST /api/v1/reading/sessions/<session_id>/close/` (marks the session completed/inactive; idempotent)
- Progress: `GET/PUT/PATCH /api/v1/reading/sessions/<session_id>/progress/` (writes require current access to the session's book)
- Annotations: `GET /api/v1/reading/annotations/` (paginated; soft-deleted items are hidden by default; pass `?include_deleted=true` to include them)
  - Filters: `?book_id=<book_id>`, `?session_id=<session_id>`, `?kind=highlight|bookmark` (may be repeated)
  - Product-category filter: repeat `?category=bookmark|highlight|highlight_with_note` for OR selection. `highlight` means a highlight without `comment_text`; `highlight_with_note` means a highlight with nonblank `comment_text`. This is separate from `kind=highlight`, which includes both highlight categories.
  - Ordering: `?ordering=created|-created|modified|-modified`
  - Annotation location/CFI ordering is not supported.
  - `POST /api/v1/reading/annotations/` supports optional `Idempotency-Key` for safe retries (recommended).
  - `POST /api/v1/reading/annotations/batch/` accepts Django session or Client
    API bearer authentication and creates up to 100 annotations for one session
    owned by the authenticated user. The Book must currently be visible for
    writes. The request is validated before creation and commits all items or
    none. Success returns `201` with `{"annotations": [...]}`; an optional
    per-item `client_id` is echoed in its corresponding response item.
- Marginalia export (Django session-authenticated only; Client API bearer tokens rejected):
  - `GET /api/v1/reading/export/` exports all owned current-user sessions, including sessions for books the user can no longer view. Empty Sessions (no non-deleted annotations) are excluded unless `include_empty_sessions=true`.
  - `POST /api/v1/reading/export/` exports selected owned books/sessions, including owned sessions for books the user can no longer view. JSON field `include_empty_sessions` has the same default-false behavior.
- Marginalia import preview (Django session-authenticated only; Client API bearer tokens rejected):
  - `POST /api/v1/reading/import/preview/` accepts one uploaded SPL native marginalia JSON export file, validates it, stages the validated payload in `userdata/imports/staged/`, returns an `import_token`, summarizes contents, and reports visible local book matches by file hash only. Multipart field `include_empty_sessions` defaults to false; the token records that choice for Apply and unmatched download.
  - Preview includes `unmatched_downloadable_session_count`, counting unmatched/Reader-required Sessions allowed by the staged empty-Session policy.
  - `GET /api/v1/reading/import/unmatched/?import_token=<token>` downloads `secondpass-marginalia-sessions.zip`. The ZIP has numbered Book directories and one native SPL mini-export JSON file per downloadable Session; each file contains exactly one Book and one Session. Empty Sessions follow the staged preview policy and resulting empty Book directories are omitted. A valid token with no downloadable Sessions returns `409`; downloading does not consume the token or change later apply behavior.
- Minimal marginalia import apply (Django session-authenticated only; Client API bearer tokens rejected):
  - `POST /api/v1/reading/import/apply/` requires an `import_token` from preview, re-validates the staged payload, imports matched sessions for visible local books as historical sessions, skips unmatched books, deletes the staged file after success, and does not accept direct file uploads or foreign/provider formats.
  - Optional multipart `selection` JSON limits import to selected export-local sessions and may override imported session `name`/`notes`.

Reading payload notes:

- Marginalia ownership, current book visibility, book-file download access, and current reading/open capability are separate. Owned sessions/annotations remain visible/exportable to their owner after book access loss; current reading/open activity and book-file downloads still require current book visibility.
- Progress uses `current_location` (JSON) as the canonical "where am I?" session state (for EPUB, an EPUB CFI and/or href-based locator).
- `progression` is derived/display metadata (a normalized scalar hint, `0.0 <= progression <= 1.0` when present), not canonical navigation state. It is useful for progress bars and summaries; it should not be used for resume location, annotation anchoring, CFI correctness validation, or cross-device exact positioning. If described as whole-book progress, it is relative to the whole renderable EPUB reading span from first renderable location to last renderable location (not page count, viewport count, chapter-local progress, or byte offset).
- Session list/retrieve payloads include `progression`, `annotation_count`, `can_open`, and a compact `book` summary scoped to the caller's current book visibility. `can_open=false` means the session remains owned/readable, but the related book is not currently available for open/continue/per-book navigation.
- Session search (`?q=<text>`) trims whitespace and searches session-owned `name`/`notes` plus currently visible book `title`, `subtitle`, authors, and series. It does not search annotation bodies, ISBNs, identifiers, marginalia export payloads, or arbitrary client blobs. User-owned session name/notes can match even when related book access is later lost; hidden/inaccessible book metadata cannot match and remains redacted.
- Session list `?has_annotations=true|false` filters on non-deleted annotation presence. Export uses this filter for candidate selection; normal Marginalia browsing does not apply it by default.
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
- Unmatched import download is Product UI/session-authenticated, tied to the current user's staged preview token, and intended for Second Pass Reader re-anchoring when the original book file is missing, different, or has malformed locators. It is separate from, and does not change, complete or selected Marginalia export.
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
- Authenticated server context: `GET /api/v1/server/info/`
  - accepts session or Client API bearer authentication
  - `server_name`
  - `server_description`
  - `server_banner_message`
  - `advanced_library_groups_enabled`
  - `reading_client_base_url` (normalized root URL or `null` when disabled)
  - `marginalia_profile_uri` (canonical supported Marginalia interchange profile)
  - `public_group` (`id`, `name`, `description`)
  - `server_version`
  - `server_release_date`
  - read-only; contains no user identity, membership, capability, API-base, or
    operator-only configuration fields
- Public discovery: `GET /.well-known/secondpass`
  - `server_name`
  - `server_description`
  - `server_version`
  - `server_release_date`
  - `api_base_url`
  - does not include banner text, advanced library group state, capabilities,
    or client route manifests
- Owner server settings: `GET/PATCH /api/v1/server/settings/`
  - `server_name`
  - `server_description`
  - `server_banner_message`
  - `public_group_name`
  - `public_group_description`
  - `advanced_library_groups_enabled`
  - `reading_client_base_url` (effective normalized value, blank when disabled)
  - `reading_client_base_url_locked` (true when the environment override owns it)

`reading_client_base_url` accepts only an HTTP(S) origin/root URL: a hostname is
required, localhost and explicit ports are allowed, and paths, queries,
fragments, user information, and placeholders are rejected. The nonblank
`SECOND_PASS_READING_CLIENT_BASE_URL` environment setting overrides the stored
value and makes the Owner setting read-only. Public discovery and `/me` do not
include this value.

Advanced library groups are off by default. Owners enable them with
`POST /api/v1/server/settings/advanced-library-groups/enable/`. Normal
`PATCH /api/v1/server/settings/` does not disable or enable this flag; disabling
after enablement is an operator recovery action through Django admin. While
disabled, normal non-Public group mutation endpoints return forbidden.

See `docs/reading.md` for details.
