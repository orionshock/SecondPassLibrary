# Reading REST API Examples (Current)

These examples document the **current** REST API payloads under `/api/v1/reading/`.

They are **profile-shaped** and versioned, but they are not the SPL native marginalia export file format. Reader clients and external tools should normalize foreign annotation data into these REST shapes when writing through the normal reading APIs.

All reading endpoints require authentication.

Client API bearer tokens may be used for these endpoints:

- Send `Authorization: Bearer <token>` (issued via the Client API PIN/code flow).
- Reading data access is strictly scoped to the token owner (sessions/progress/annotations are user-owned).

## 1) Overview

- Base path: `/api/v1/reading/`
- Payloads use `profile_version: "0.1.0"` (the current server profile version).
- Unknown/client-specific fields are rejected with `400` validation errors.
- The server is **not** arbitrary client blob storage.
- Reader clients must translate their internal state into this shape before saving.

Practical notes:

- Requests should be `Content-Type: application/json`.
- List endpoints are paginated (see `docs/api.md`).

## 1.5) Recent active sessions (compact)

Fetch a compact "continue reading" list:

`GET /api/v1/reading/sessions/recent/?limit=10`

Notes:

- Active sessions only (`is_active=true`, `status=active`).
- Unique by book.
- Ordered by `last_activity_at = max(session.updated_at, progress.updated_at if exists, latest non-deleted annotation.updated_at if any)`.
- Each book includes `cover_url` (string URL) or `null` when no cover is available.

## 2) Get or create active session

Get the current active session for a given book (creating one lazily if needed):

`GET /api/v1/reading/books/<book_id>/active-session/`

Example response:

```json
{
  "id": "9f2f2c5d-8c7e-4f3d-a7c8-8c5b8c0c9c2f",
  "book": "7f4d7d8b-4b9f-4b3f-8c4c-5f7a8b9c0d1e",
  "book_title": "The Left Hand of Darkness",
  "status": "active",
  "name": "",
  "started_at": "2026-05-11T01:32:12Z",
  "completed_at": null,
  "is_active": true,
  "notes": "",
  "created_at": "2026-05-11T01:32:12Z",
  "updated_at": "2026-05-11T01:32:12Z"
}
```

Behavior notes:

- If the user already has an active session for the book, it is returned **even if the user later loses current book access** (reading data is user-owned and durable).
- A new session is created only if the user can **currently** view the book.
- If the user cannot view the book and there is no existing active session, the endpoint returns `404 Not Found` (anti-leakage behavior).

## 2.5) Open book bootstrap (recommended)

Bootstrap a reader client opening a book with a single request:

`POST /api/v1/reading/books/<book_id>/open/`

Behavior notes:

- If an active session already exists, it is returned even if current book access is later lost.
- If no active session exists yet, the server creates one only when the user can currently view the book (otherwise `404`).
- Progress is created if missing.
- The response includes the **first page** of non-deleted annotations for that session.
- To fetch more annotations pages, use: `GET /api/v1/reading/annotations/?session_id=<session_id>&page=...`

Example response:

```json
{
  "profile_version": "0.1.0",
  "session": { "...": "..." },
  "progress": { "...": "..." },
  "annotations": {
    "count": 0,
    "next": null,
    "previous": null,
    "results": []
  }
}
```

## 3) Start over

Close/archive the current active session (if any) and create a new active session:

`POST /api/v1/reading/books/<book_id>/start-over/`

Request body:

```json
{ "name": "Reread 2026" }
```

Example response (`201 Created`):

`start-over` returns the same bootstrap shape as `/open/` (session + progress + first page of annotations):

```json
{
  "profile_version": "0.1.0",
  "session": { "...": "..." },
  "progress": { "...": "..." },
  "annotations": {
    "count": 0,
    "next": null,
    "previous": null,
    "results": []
  }
}
```

Behavior notes:

- Requires current book access (the user must be able to view the book).
- Archives any existing active session for that book (preserves old progress and annotations).
- Creates a new active session.

## 3.5) Close a reading session

Mark a reading session as completed/inactive without creating a new session:

`POST /api/v1/reading/sessions/<session_id>/close/`

Notes:

- Returns the `ReadingSession` payload.
- Idempotent: closing an already-closed session returns the current session payload and does not change `completed_at`.
- After close, progress writes and annotation create/update are rejected (closed-session immutability).
- Soft-delete of annotations remains allowed.

## 4) Save reading progress / current location

Progress is one-to-one per session and stores mutable **session state** like the current location (this is not an Annotation).

`PUT /api/v1/reading/sessions/<session_id>/progress/`

Example request body (explicit selector form):

```json
{
  "profile_version": "0.1.0",
  "current_location": {
    "format": "epub",
    "selector": {
      "type": "FragmentSelector",
      "conformsTo": "http://www.idpf.org/epub/linking/cfi/epub-cfi.html",
      "value": "epubcfi(/6/14!/4/2/6)"
    }
  },
  "progression": 0.42
}
```

Shorthand accepted form (server normalizes to a `FragmentSelector` when `selector` is omitted):

```json
{
  "current_location": {
    "format": "epub",
    "cfi": "/6/14!/4/2/6"
  },
  "progression": 0.42
}
```

Notes:

- Shorthand `current_location.cfi` is preserved as submitted.
- When `current_location.selector` is omitted but `current_location.cfi` is present, the server adds a `current_location.selector` and normalizes `current_location.selector.value` to the `epubcfi(...)` form.
- `current_location` is the canonical "where am I?" session state. `progression` is derived/display metadata only (a normalized scalar hint); it should not be used as a source of truth for resume location or exact positioning.
- When present, `0.0 <= progression <= 1.0` (inclusive). If described as whole-book progress, it is relative to the whole renderable EPUB reading span from first renderable location to last renderable location.
- Closed sessions reject progress writes with `400` validation errors (session is immutable once closed/archived).
- Oversized JSON or unknown fields return `400` validation errors.

## 5) Create bookmark annotation

Bookmarks are stored as Annotations.

`POST /api/v1/reading/annotations/`

Idempotency (recommended):

- Clients SHOULD send an `Idempotency-Key` header for each annotation create request.
- If the client retries the same request with the same key, the server returns the original `201` response (same annotation id) and does not create a duplicate.
- Reusing the same key for a different request returns `409 Conflict`.

Example request body:

```json
{
  "profile_version": "0.1.0",
  "session": "<session_id>",
  "motivation": "bookmarking",
  "target": {
    "selector": {
      "type": "FragmentSelector",
      "conformsTo": "http://www.idpf.org/epub/linking/cfi/epub-cfi.html",
      "value": "epubcfi(/6/14!/4/2/6)"
    }
  },
  "body": []
}
```

Notes:

- Bookmark and current reading location often point into the book similarly, but they differ by lifecycle/intent:
  - Progress/current location is mutable session state.
  - Bookmark is an intentionally saved user artifact (annotation history).
- Annotation `body` is always accepted/returned as a list of objects. If a client submits a single body object, the server coerces it to a list in responses.

## 6) Create highlight annotation

Example request body:

```json
{
  "profile_version": "0.1.0",
  "session": "<session_id>",
  "motivation": "highlighting",
  "target": {
    "selector": {
      "type": "FragmentSelector",
      "conformsTo": "http://www.idpf.org/epub/linking/cfi/epub-cfi.html",
      "value": "epubcfi(/6/14!/4/2/6)"
    }
  },
  "body": [
    {
      "type": "TextualBody",
      "purpose": "highlighting",
      "value": "Selected text from the EPUB.",
      "color": "yellow"
    }
  ]
}
```

Notes:

- Keep highlight body fields within the current profile shape (unknown body fields are rejected).
- Long (but reasonable) selected text is allowed; excessive payloads are rejected.

## 7) Create note annotation

`POST /api/v1/reading/annotations/`

Example request body:

```json
{
  "profile_version": "0.1.0",
  "session": "<session_id>",
  "motivation": "commenting",
  "target": {
    "selector": {
      "type": "FragmentSelector",
      "conformsTo": "http://www.idpf.org/epub/linking/cfi/epub-cfi.html",
      "value": "epubcfi(/6/14!/4/2/6)"
    }
  },
  "body": [
    {
      "type": "TextualBody",
      "purpose": "commenting",
      "value": "My note about this passage."
    }
  ]
}
```

## 8) List annotations

`GET /api/v1/reading/annotations/?session_id=<session_id>`

Notes:

- The response is paginated.
- Soft-deleted annotations are hidden by default.
- `include_deleted=true` includes soft-deleted records.
- `book_id=<book_id>` is also supported as a filter.

Example response:

```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "c9c1b4d2-7f6f-4d70-97d5-2b1d4b9c7a11",
      "session": "<session_id>",
      "motivation": "bookmarking",
      "target": {
        "source": { "book_id": "<book_id>", "type": "Book" },
        "selector": {
          "type": "FragmentSelector",
          "conformsTo": "http://www.idpf.org/epub/linking/cfi/epub-cfi.html",
          "value": "epubcfi(/6/14!/4/2/6)"
        }
      },
      "body": [],
      "profile_version": "0.1.0",
      "is_deleted": false,
      "created_at": "2026-05-11T02:05:02Z",
      "updated_at": "2026-05-11T02:05:02Z"
    }
  ]
}
```

## 9) Soft-delete annotation

`DELETE /api/v1/reading/annotations/<annotation_id>/`

Notes:

- Delete is a **soft delete**: it sets `is_deleted=true` and returns `204 No Content`.
- Soft-delete is allowed even for closed sessions (deletion is not treated as "mutating reading content").

## 10) Client attribution

The Reading API does not model a separate device object. Client/auth identity is represented by the Client API bearer token (`accounts.UserClientSession`).

Future possibilities:

- Optional client-session attribution fields on reading data (without changing reading data ownership rules).

## 11) Common validation failures

Examples of common `400` errors you should expect during client integration:

- Unsupported `profile_version`:
  - `"Unsupported profile_version '0.0.1'. Expected '0.1.0'."`
- Unknown top-level field on progress writes:
  - `"Unsupported fields: some_client_field."`
- Unknown `current_location` field:
  - `"Unsupported current_location fields: some_client_field."`
- Unknown `target` / `selector` / `body` fields:
  - `"Unsupported target fields: ..."`
  - `"Unsupported selector fields: ..."`
  - `"Unsupported body fields in body[0]: ..."`
- Oversized payloads:
  - `current_location` exceeds maximum size (bytes)
  - `target` exceeds maximum size (bytes)
  - `body` exceeds maximum size (bytes)
- Invalid/empty `motivation` (required).
- Writing progress or creating/updating annotations on a closed session:
  - `"This reading session is closed."`
- `source_import` is not accepted via the public API (internal-only; unknown fields are rejected).

## 12) Minimal reader-client flow

A minimal integration flow for a reader client:

1. Authenticate.
2. `GET /api/v1/accounts/me/`
3. If `must_change_password` is `true`, send the user to `/profile/password/` (then call `POST /api/v1/accounts/me/change-password/`).
4. `POST /api/v1/reading/books/<book_id>/open/`
5. Periodically `PUT /api/v1/reading/sessions/<session_id>/progress/`
6. `POST /api/v1/reading/annotations/` for bookmarks/highlights/notes
7. `DELETE /api/v1/reading/annotations/<annotation_id>/` for soft delete

## 13) Non-goals (current)

- No EPUB rendering in this server project.
- No JSON-LD import/export yet.
- No client-specific hidden blob fields.
- No PDF support.
