# Reading

Reading metadata is user-owned and must remain durable/exportable.
Losing current book visibility does not hide a user's existing sessions or
annotations from that user, but it does stop live reading activity for that
book until access is restored.

Access concepts are intentionally separate:

- Marginalia ownership controls whether existing sessions, progress, and annotations remain visible/exportable to their owner.
- Current book visibility controls whether the user can open/continue the book, create a new session, write progress, or create/update/delete annotations.
- Book-file download access follows current book visibility and never follows marginalia ownership alone.
- `can_open` in session summary/detail payloads reports whether the related book is currently visible enough for open/continue/per-book navigation.

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

- `progression` (float 0-1 or null; derived/display metadata, not canonical location state)
- `annotation_count` (non-deleted annotations)
- `book` summary (id/title/authors/series/series_index/cover_url), scoped to the caller's current book visibility (hidden/inaccessible books do not leak metadata)
- `can_open` (boolean), true when the caller currently has book visibility for open/continue/per-book navigation
- `book_id` as the stable book identifier; the old summary-only `book_title` compatibility field is no longer returned
- Optional list filters: `?book=<book_id>`, `?status=active|completed|archived`, `?is_active=true|false`, `?q=<text>`
- When `?book=<book_id>` is present for a visible book, the paginated response includes `context.book` even when no sessions exist. Malformed book ids return 400; nonexistent or inaccessible book ids return 404.
- `q` searches session `name` and `notes`, plus currently visible book metadata (`title`, `subtitle`, authors, series). It does not search annotation bodies, ISBNs, identifiers, marginalia export payloads, or arbitrary client blobs. A session can match by its own name/notes even if the related book is no longer visible, but hidden/inaccessible book metadata is not searchable and remains redacted in results.

Reading activity overlays are intentionally exposed under `/api/v1/reading/`, not under `/api/v1/library/books/`. Library/catalog payloads stay focused on book metadata and visibility.

Endpoints:

```text
POST /api/v1/reading/books/<book_id>/open/                    (recommended bootstrap: session + progress + annotations)
GET  /api/v1/reading/books/<book_id>/active-session/
POST /api/v1/reading/books/activity-summary/
POST /api/v1/reading/books/<book_id>/start-over/          (optional body: {"name": "Second pass"})
GET  /api/v1/reading/sessions/                            (paginated)
GET  /api/v1/reading/sessions/recent/                     (compact recent list; active sessions only; default limit 10, max 50)
GET  /api/v1/reading/sessions/<session_id>/
PATCH /api/v1/reading/sessions/<session_id>/              (only while active: {"name": "...", "notes": "..."})
POST /api/v1/reading/sessions/<session_id>/close/          (mark session completed/inactive; idempotent)
```

### Book-filter context

`GET /api/v1/reading/sessions/?book=<book_id>` returns the normal paginated session list plus a `context` object when the book id is valid and visible:

```json
{
  "count": 0,
  "next": null,
  "previous": null,
  "context": {
    "book": {
      "id": "7f4d7d8b-4b9f-4b3f-8c4c-5f7a8b9c0d1e",
      "title": "Blood Rites",
      "authors": ["Jim Butcher"],
      "series": {
        "id": "6b9d2c11-7f4e-4f40-9c3f-3ee21c2eae33",
        "name": "Dresden Files"
      },
      "series_index": "6.0",
      "cover_url": null
    }
  },
  "results": []
}
```

### Activity summary

`POST /api/v1/reading/books/activity-summary/` accepts up to 100 book ids:

```json
{
  "books": [
    "7f4d7d8b-4b9f-4b3f-8c4c-5f7a8b9c0d1e",
    "2f0f4598-2467-4c5c-bf85-44cb3560ad88"
  ]
}
```

It returns one row for each requested, well-formed, visible book, deduplicated in first-request order. Well-formed nonexistent or inaccessible ids are omitted to avoid existence leaks; malformed ids, missing/invalid `books`, and batches over 100 return 400.

```json
{
  "results": [
    {
      "book": "7f4d7d8b-4b9f-4b3f-8c4c-5f7a8b9c0d1e",
      "session_count": 3,
      "active_session_count": 1,
      "active_session_id": "9f2f2c5d-8c7e-4f3d-a7c8-8c5b8c0c9c2f",
      "latest_session_id": "9f2f2c5d-8c7e-4f3d-a7c8-8c5b8c0c9c2f",
      "latest_session_updated_at": "2026-05-11T01:32:12Z"
    },
    {
      "book": "2f0f4598-2467-4c5c-bf85-44cb3560ad88",
      "session_count": 0,
      "active_session_count": 0,
      "active_session_id": null,
      "latest_session_id": null,
      "latest_session_updated_at": null
    }
  ]
}
```

If multiple active sessions somehow exist for the same user/book despite the model invariant, `active_session_id` is the most recently updated active session.

### Recent sessions

`GET /api/v1/reading/sessions/recent/?limit=10` returns a compact, fast list of the user's **active** reading sessions ordered by `last_activity_at`:

`last_activity_at = max(session.updated_at, progress.updated_at if exists, latest non-deleted annotation.updated_at if any)`

This endpoint is intended for "Continue reading" style UIs. For full session history use `GET /api/v1/reading/sessions/`.

The compact payload includes `session.name` (may be blank) and `session.progression` (float 0-1 or null) alongside the session id/status. Active sessions for books the user can no longer view are omitted; they remain available through the full session history endpoints.

### Active session behavior

- `active-session` requires current book access, even when an active session already exists.
- If the user cannot currently view the book, the endpoint returns a `404 Not Found` style response (NotFound/anti-leakage behavior).
- `open` follows the same access rule: it returns or creates an active session only when the user can currently view the book.
- Existing no-access sessions remain visible in session history and export, but are not continue-reading/bootstrap targets.

### Start-over behavior

- `start-over` requires current book access (the user must be able to view the book).
- If the user cannot view the book, the endpoint returns a `404 Not Found` style response (NotFound/anti-leakage behavior).
- `start-over` returns the same bootstrap response shape as `/open/` (session + progress + first page of annotations) so reader clients can immediately continue with the new session id.

### Close behavior

- `close` marks a session as completed (`status=completed`, `is_active=false`) and sets `completed_at` the first time it is closed.
- The endpoint is idempotent: closing an already-closed session returns the current session payload and does not change `completed_at`.
- Closing an existing active session is allowed even if the user has lost current book access.
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

Canonical vs derived state:

- Canonical reading position is `current_location` (for EPUB, an EPUB CFI and/or href-based locator).
- `progression` is a normalized scalar display hint (derived/summary metadata), not canonical navigation state.

`progression` is useful for:

- progress bars
- dashboard cards
- session summaries
- friendly percentages

`progression` should not be used as the source of truth for:

- resume location
- annotation anchoring
- validation of CFI correctness
- cross-device exact positioning

If described as whole-book progress, treat `progression` as relative to the whole renderable EPUB reading span from first renderable location to last renderable location. It is not page count, viewport count, chapter-local progress, or byte offset.

Validation:

- When present, `0.0 <= progression <= 1.0` (inclusive).
- Progress reads are owner-scoped. Progress writes require an owned writable/open session and current access to the session's book.

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
- `progression` is optional derived/display metadata; when present, `0.0 <= progression <= 1.0` (inclusive).
- PDF locators are not supported.

## Annotations (highlights, notes, bookmarks)

The live annotation API uses compact SPL-native fields:

- `selector_kind` + `selector_value` (currently `epub_cfi`)
- `highlight_text` / `highlight_color`
- `quote_prefix` / `quote_suffix` (optional quote context for highlight repair/export; each <= 500 chars)
- `comment_text`

The canonical portable exchange format remains the session-centered Second Pass
Library Marginalia Profile documented in
`docs/specs/marginalia-export.md`.

Highlight color:

- `highlight_color` is a semantic token (not a CSS/hex color string).
- Allowed values: `yellow`, `green`, `blue`, `pink`, `purple`, `orange`.
- Color is highlight-only metadata.
- Note/comment text and bookmark-only annotations do not use color.
- For highlight annotations, missing/blank color defaults to `yellow`.

- List/create/update: `GET/POST/PATCH /api/v1/reading/annotations/` (list is paginated)
- Optional filters:
  - `?book_id=<book_id>`
  - `?session_id=<session_id>`
  - `?motivation=highlighting|commenting|bookmarking` (may be repeated)
  - `?ordering=created|-created|modified|-modified`
- Soft-deleted annotations (`is_deleted=true`) are hidden by default; pass `?include_deleted=true` to include them.
- Delete uses soft delete (`is_deleted=true`) instead of hard deletion.

Annotation payloads use these API fields:

- `kind`: `bookmark` or `highlight`
- `selector`: `{ "kind": "epub_cfi", "value": "epubcfi(...)" }`
- `quote`: optional `{ "exact": "...", "prefix": "...", "suffix": "..." }`
- `highlight_text`
- `highlight_color`
- `comment_text`

Notes:

- Annotations belong to exactly one reading session.
- The current implementation does not support cross-session promotion/linking (no `derivedFrom` / `sourceSession` behavior).
- Annotation anchors are immutable after creation:
  - `selector`
  - optional `quote` context (`exact`/`prefix`/`suffix`)
  - `session`, `book`, and `kind`
- `PATCH /api/v1/reading/annotations/<id>/` supports only:
  - `comment_text`
  - `highlight_color`
- `POST /api/v1/reading/annotations/batch/` creates up to 100 annotations for one session in one all-or-nothing request.
- Unknown/unsupported fields in progress/annotation payloads are rejected; the server is not arbitrary client blob storage.
- Annotation reads are owner-scoped. Annotation create/update/delete require an owned writable/open session and current access to the session's book.
- Payloads are size-limited as a coarse abuse guard (not a perfect semantic model for very long/multi-part highlights). Oversized payloads return 400 validation errors.

## Client attribution

The Reading API does not model a separate `Device` object. Client/auth identity is represented by `accounts.UserClientSession` (Client API bearer tokens).

Future possibilities:

- Optional client-session attribution fields on reading data (without changing reading data ownership rules).

## Marginalia export

Current export support includes a complete archive plus selected archive exports. Import support includes preview plus a minimal native apply path for matched visible books.

The canonical Second Pass Library Marginalia Profile is documented in
`docs/specs/marginalia-export.md`.

Product UI:

```text
GET /reading/export/
GET /reading/import/
```

Session-authenticated API exports:

```text
GET /api/v1/reading/export/
POST /api/v1/reading/export/
POST /api/v1/reading/import/preview/
GET /api/v1/reading/import/unmatched/?import_token=<token>
POST /api/v1/reading/import/apply/
```

Export and import preview/apply endpoints are for the Django product UI/session-authenticated user. They are not enabled for Client API bearer tokens. Exports include owned reading sessions and annotations even when the user no longer has current book visibility. Other-user or mismatched sessions are rejected. Import preview/apply remains stricter and matches visible local books only.

Selected exports post a JSON body to `/api/v1/reading/export/`:

```json
{
  "books": [
    { "book_id": "<uuid>", "sessions": "all" },
    { "book_id": "<uuid>", "sessions": ["<session_uuid>", "<session_uuid>"] }
  ]
}
```

The JSON shape is nested:

```text
export header
  books[]
    sessions[]
      progress
      annotations[]
```

Annotations inherit book and session context from that nesting, so the export does not repeat full book metadata inside every annotation. Session rows use export-local ids such as `session-1`; exported annotations do not include SPL database annotation ids. Deleted annotations are excluded.

EPUB CFI annotation selectors export as `FragmentSelector` values without
repeating `conformsTo`; EPUB CFI is the SPL anchoring format. When quote context
is present, export includes a `TextQuoteSelector` with `exact`, `prefix`, and/or
`suffix` as an anchoring/repair hint, not as W3C compliance machinery.

Server-side marginalia import accepts SPL Marginalia Profile files only. Preview validates the uploaded JSON against the export schema, stages the validated payload in a short-lived filesystem file, returns an `import_token`, summarizes contents, reports visible local book matches by file hash only, and does not create sessions or annotations. Apply uses the `import_token`, re-validates the staged payload, then imports matched visible books only. ISBN and title/author fallback matching are intentionally not used for server-side locator import. Foreign/provider-specific annotation formats should be normalized by a client and written through the normal reading session/progress/annotation APIs, or converted by an external tool into the SPL Marginalia Profile shape before server import.

Current apply creates new historical/imported sessions. Unmatched books are skipped and flagged as unmatched/possibly foreign. Matched books receive shallow CFI-shaped validation: EPUB CFI values must look like `epubcfi(...)`, but the server does not resolve them against EPUB contents. Sessions with malformed locators are excluded from server apply and preserved for Reader-assisted import. Preview exposes an unmatched download for the current user's staged import token; it contains unmatched export books and malformed-locator sessions as native SPL JSON. The import unit is a reading session; annotation-level selection is not supported. Exported active sessions do not become active local sessions. Possible duplicate sessions/annotations are warnings, not blockers. Apply accepts optional session-level selection/customization JSON using export-local `export_session_id` values; selected sessions may override imported `name` and `notes`.
