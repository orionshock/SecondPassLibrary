# Reading

Reading metadata is user-owned and must remain durable/exportable.

Design direction:

- `docs/user-data.md`
- `docs/specs/reading-session-annotation-profile/`
- Current REST examples: `docs/reading-rest-examples.md`

## Sessions

- "Open book for reading" uses lazy active-session creation.
- "Start over" creates a new active session and preserves history.

Sessions are created through the dedicated endpoints below (not via `POST /sessions/`).
The `/sessions/` API exists for listing/retrieving and limited client-safe metadata edits.

Session list/retrieve payloads include a compact summary suitable for session-management UIs:

- `progression` (float 0–1 or null)
- `annotation_count` (non-deleted annotations)
- `book` summary (id/title/authors/series/series_index/cover_url), scoped to the caller’s current book visibility (hidden/inaccessible books do not leak metadata)
- Optional list filters: `?book=<book_id>`, `?status=active|completed|archived`, `?is_active=true|false`

Endpoints:

```text
POST /api/v1/reading/books/<book_id>/open/                    (recommended bootstrap: session + progress + annotations)
GET  /api/v1/reading/books/<book_id>/active-session/
POST /api/v1/reading/books/<book_id>/start-over/          (optional body: {"name": "Second pass"})
GET  /api/v1/reading/sessions/                            (paginated)
GET  /api/v1/reading/sessions/recent/                     (compact recent list; active sessions only; default limit 10)
GET  /api/v1/reading/sessions/<session_id>/
PATCH /api/v1/reading/sessions/<session_id>/              (only while active: {"name": "...", "notes": "..."})
POST /api/v1/reading/sessions/<session_id>/close/          (mark session completed/inactive; idempotent)
```

### Recent sessions

`GET /api/v1/reading/sessions/recent/?limit=10` returns a compact, fast list of the user's **active** reading sessions ordered by `last_activity_at`:

`last_activity_at = max(session.updated_at, progress.updated_at if exists, latest non-deleted annotation.updated_at if any)`

This endpoint is intended for "Continue reading" style UIs. For full session history use `GET /api/v1/reading/sessions/`.

The compact payload includes `session.name` (may be blank) and `session.progression` (float 0–1 or null) alongside the session id/status.

### Active session behavior

- If the user already has an active session for the book, `active-session` returns it even if the user later loses current book access (reading data is user-owned and durable).
- If no active session exists yet, `active-session` creates a new one only when the user can currently view the book.
- If the user cannot view the book and there is no existing active session, the endpoint returns a `404 Not Found` style response (NotFound/anti-leakage behavior).

### Start-over behavior

- `start-over` requires current book access (the user must be able to view the book).
- If the user cannot view the book, the endpoint returns a `404 Not Found` style response (NotFound/anti-leakage behavior).
- `start-over` returns the same bootstrap response shape as `/open/` (session + progress + first page of annotations) so reader clients can immediately continue with the new session id.

### Close behavior

- `close` marks a session as completed (`status=completed`, `is_active=false`) and sets `completed_at` the first time it is closed.
- The endpoint is idempotent: closing an already-closed session returns the current session payload and does not change `completed_at`.
- `close` does not create a new session; the client should call `/open/` when opening another book.
- `start-over` is different: it archives the current active session for the same book and creates a new active session.

## Progress

Progress is one-to-one per session (auto-created if missing). It stores mutable session state such as the current reading location (this is not an Annotation):

```text
GET   /api/v1/reading/sessions/<session_id>/progress/
PUT   /api/v1/reading/sessions/<session_id>/progress/
PATCH /api/v1/reading/sessions/<session_id>/progress/
```

Example payload:

```json
{
  "current_location": {"format": "epub", "cfi": "/6/4", "href": "Text/chapter01.xhtml"},
  "progression": 0.42
}
```

## Current location (JSON conventions)

Current location is flexible JSON. For EPUB, prefer:

```json
{
  "format": "epub",
  "href": "Text/chapter01.xhtml",
  "cfi": "epubcfi(...)",
  "position": 12345,
  "text": {"exact": "...", "prefix": "...", "suffix": "..."}
}
```

Notes:
- `href` is the EPUB internal content document path when available.
- `cfi` is preferred when the client can provide it.
- `progression` is a float between 0 and 1 when available.
- PDF locators are not supported.

## Annotations (highlights, notes, bookmarks)

Annotations are represented externally as W3C-style `Annotation` records, but stored internally in compact/queryable columns:

- `selector_kind` + `selector_value` (currently `epub_cfi`)
- `highlight_text` / `highlight_color`
- `comment_text`

The API reconstructs the W3C-ish `target`/`body` shape from those columns at the boundary.

- List/create/update: `GET/POST/PATCH /api/v1/reading/annotations/` (list is paginated)
- Optional filters: `?book_id=<book_id>` and/or `?session_id=<session_id>`
- Soft-deleted annotations (`is_deleted=true`) are hidden by default; pass `?include_deleted=true` to include them.
- Delete uses soft delete (`is_deleted=true`) instead of hard deletion.

Annotation payloads use canonical fields:

- `motivation`: `highlighting|commenting|bookmarking`
- `target`: W3C-ish `source` + `selector` (EPUB CFI `FragmentSelector`)
- `body`: W3C-ish body/bodies (JSON)
- `profile_version`: currently `0.1.0`

Notes:

- Annotations belong to exactly one reading session.
- The current implementation does not support cross-session promotion/linking (no `derivedFrom` / `sourceSession` behavior).
- `source_import` is reserved for server-side import/provenance. It is not exposed as a normal client-writable field via the public API.
- Unknown/unsupported fields in progress/annotation payloads are rejected; the server is not arbitrary client blob storage.
- Payloads are size-limited as a coarse abuse guard (not a perfect semantic model for very long/multi-part highlights). Oversized payloads return 400 validation errors.

## Client attribution

The Reading API does not model a separate `Device` object. Client/auth identity is represented by `accounts.UserClientSession` (Client API bearer tokens).

Future possibilities:

- Optional client-session attribution fields on reading data (without changing reading data ownership rules).
