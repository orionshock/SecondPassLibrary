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

- `progression` (float 0-1 or null; derived/display metadata, not canonical location state)
- `annotation_count` (non-deleted annotations)
- `book` summary (id/title/authors/series/series_index/cover_url), scoped to the caller's current book visibility (hidden/inaccessible books do not leak metadata)
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

The compact payload includes `session.name` (may be blank) and `session.progression` (float 0-1 or null) alongside the session id/status.

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

Annotations are represented externally as W3C-style `Annotation` records, but stored internally in compact/queryable columns:

- `selector_kind` + `selector_value` (currently `epub_cfi`)
- `highlight_text` / `highlight_color`
- `quote_prefix` / `quote_suffix` (optional quote context for highlight repair/export; each <= 500 chars)
- `comment_text`

The API reconstructs the W3C-ish `target`/`body` shape from those columns at the boundary.

Highlight color:

- `highlight_color` is a semantic token (not a CSS/hex color string).
- Allowed values: `yellow`, `green`, `blue`, `pink`, `purple`, `orange`.
- Color is highlight/quote-only metadata (it applies to the selected-text `TextualBody` with `purpose: "describing"`).
- Note/comment bodies and bookmark-only annotations do not use color.
- For highlight annotations, missing/blank color defaults to `yellow`.

- List/create/update: `GET/POST/PATCH /api/v1/reading/annotations/` (list is paginated)
- Optional filters:
  - `?book_id=<book_id>`
  - `?session_id=<session_id>`
  - `?motivation=highlighting|commenting|bookmarking` (may be repeated)
  - `?ordering=created|-created|modified|-modified`
- Soft-deleted annotations (`is_deleted=true`) are hidden by default; pass `?include_deleted=true` to include them.
- Delete uses soft delete (`is_deleted=true`) instead of hard deletion.

Annotation payloads use canonical fields:

- `motivation`: a list of motivations (e.g. `["bookmarking"]`, `["highlighting"]`, `["highlighting", "commenting"]`)
- `target`: W3C-ish `source` + `selector` (EPUB CFI `FragmentSelector`)
- `body`: W3C-ish body/bodies (JSON)
- `profile_version`: currently `0.1.0`

Notes:

- Annotations belong to exactly one reading session.
- The current implementation does not support cross-session promotion/linking (no `derivedFrom` / `sourceSession` behavior).
- Annotation anchors are immutable after creation:
  - `target.selector` (EPUB CFI `FragmentSelector`)
  - optional `TextQuoteSelector` quote context (`exact`/`prefix`/`suffix`)
  - `session`, `book`, and `motivation`
- `PATCH /api/v1/reading/annotations/<id>/` supports only:
  - note/comment body text (`body[]` with `purpose="commenting"`)
  - highlight color token (`body[]` with `purpose="describing"` and `color`)
- Unknown/unsupported fields in progress/annotation payloads are rejected; the server is not arbitrary client blob storage.
- Payloads are size-limited as a coarse abuse guard (not a perfect semantic model for very long/multi-part highlights). Oversized payloads return 400 validation errors.

## Client attribution

The Reading API does not model a separate `Device` object. Client/auth identity is represented by `accounts.UserClientSession` (Client API bearer tokens).

Future possibilities:

- Optional client-session attribution fields on reading data (without changing reading data ownership rules).

## Marginalia export

Current export support is complete for session/book/all scopes. Import support includes preview plus a minimal native apply path for matched visible books.

The baseline export contract is documented in `docs/specs/marginalia-export.md`.

Product UI:

```text
GET /reading/export/
GET /reading/import/
```

Session-authenticated API exports:

```text
GET /api/v1/reading/export/
GET /api/v1/reading/export/books/<book_id>/
GET /api/v1/reading/export/books/<book_id>/?session=<session_id>&session=<session_id>
GET /api/v1/reading/export/books/<book_id>/<session_id>/
POST /api/v1/reading/import/preview/
POST /api/v1/reading/import/apply/
```

Export and import preview endpoints are for the Django product UI/session-authenticated user. They are not enabled for Client API bearer tokens. Exports enforce current book visibility and include only reading sessions owned by the requesting user. The all export includes only visible books with at least one exported session. Mismatched book/session URLs return 404.

The book export route exports all current-user sessions for the book when no `session` query parameters are provided. When repeated `session` parameters are present, it exports only that selected subset and uses `scope.session_filter = "selected"`.

The JSON shape is nested:

```text
export header
  books[]
    sessions[]
      progress
      annotations[]
```

Annotations inherit book and session context from that nesting, so the export does not repeat full book metadata inside every annotation. Session rows use export-local ids such as `session-1`; exported annotations do not include SPL database annotation ids. Deleted annotations are excluded.

EPUB CFI annotation selectors export as `FragmentSelector` values without repeating `conformsTo`; the reading-session annotation profile defines EPUB CFI as the default FragmentSelector format. When quote context is present, export includes a `TextQuoteSelector` with `exact`, `prefix`, and/or `suffix`.

Server-side marginalia import accepts SPL native marginalia exports only. Preview validates the uploaded JSON against the export schema, stages the validated payload in a short-lived filesystem file, returns an `import_token`, summarizes contents, reports visible local book matches, and does not create sessions or annotations. Apply uses the `import_token`, re-validates the staged payload, then imports matched visible books only. Foreign/provider-specific annotation formats should be normalized by a client and written through the normal reading session/progress/annotation APIs, or converted by an external tool into the SPL native export shape before server import.

Current apply creates new historical/imported sessions. Unmatched books are skipped and flagged as unmatched/possibly foreign. The import unit is a reading session; annotation-level selection is not supported. Exported active sessions do not become active local sessions. Possible duplicate sessions/annotations are warnings, not blockers. Apply accepts optional session-level selection/customization JSON using export-local `export_session_id` values; selected sessions may override imported `name` and `notes`.
