# Reading

Reading metadata is user-owned and must remain durable/exportable.

Design direction:

- `docs/user-data.md`
- `docs/specs/reading-session-annotation-profile/`

## Sessions

- "Open book for reading" uses lazy active-session creation.
- "Start over" creates a new active session and preserves history.

Sessions are created through the dedicated endpoints below (not via `POST /sessions/`).
The `/sessions/` API exists for listing/retrieving and limited client-safe metadata edits.

Endpoints:

```text
GET  /api/v1/reading/books/<book_id>/active-session/
POST /api/v1/reading/books/<book_id>/start-over/          (optional body: {"name": "Second pass"})
GET  /api/v1/reading/sessions/                            (paginated)
GET  /api/v1/reading/sessions/<session_id>/
PATCH /api/v1/reading/sessions/<session_id>/              (only: {"name": "...", "notes": "..."})
```

### Active session behavior

- If the user already has an active session for the book, `active-session` returns it even if the user later loses current book access (reading data is user-owned and durable).
- If no active session exists yet, `active-session` creates a new one only when the user can currently view the book.
- If the user cannot view the book and there is no existing active session, the endpoint returns a `404 Not Found` style response (NotFound/anti-leakage behavior).

### Start-over behavior

- `start-over` requires current book access (the user must be able to view the book).
- If the user cannot view the book, the endpoint returns a `404 Not Found` style response (NotFound/anti-leakage behavior).

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
  "device": "<device_id>",
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
  "progression": 0.1234,
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

Annotations are stored as W3C-style `Annotation` records:

- List/create/update: `GET/POST/PATCH /api/v1/reading/annotations/` (list is paginated)
- Optional filters: `?book_id=<book_id>` and/or `?session_id=<session_id>`
- Soft-deleted annotations (`is_deleted=true`) are hidden by default; pass `?include_deleted=true` to include them.
- Delete uses soft delete (`is_deleted=true`) instead of hard deletion.

Annotation payloads use canonical fields:

- `motivation`: `highlighting|commenting|bookmarking`
- `target`: W3C-ish `source` + `selector` (EPUB CFI `FragmentSelector`)
- `body`: W3C-ish body/bodies (JSON)

## Devices

Devices are user-scoped records intended for client progress attribution and debugging context.

Endpoints:

```text
GET    /api/v1/reading/devices/                 (paginated)
POST   /api/v1/reading/devices/
GET    /api/v1/reading/devices/<device_id>/
PATCH  /api/v1/reading/devices/<device_id>/
DELETE /api/v1/reading/devices/<device_id>/
```
