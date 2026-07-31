# Marginalia Interchange Profile

Version: 0.1.0
Profile: `https://secondpasslibrary.local/specs/marginalia/0.1.0`

## Purpose

Marginalia is the domain root. Users read Books; Books accumulate Marginalia;
Marginalia contains Reading Sessions; Reading Sessions own progress and
annotations.

The native objects in this profile are used for Server/Reader communication and
inside portable archives wherever practical. An export adds a Book envelope,
but does not translate Sessions or annotations into a competing shape.

The API namespace is `/api/v1/marginalia/`. Exact implemented routes and
authentication are documented in the API reference.

## Reading Session lifecycle

A Reading Session is either `active` or `closed`.

- A user may have at most one active Session for a Book.
- Opening a Book with an existing active Session returns that Session.
- Opening never closes or replaces a Session automatically.
- Closing is a deliberate operation.
- Closed Sessions are immutable.
- A Book may have only closed Sessions and no active Session.

Canonical Session shape:

```json
{
  "sourceReadingSessionId": "source-reading-session-000001",
  "name": "Current pass",
  "notes": "",
  "status": "active",
  "startedAt": "2026-07-20T12:00:00Z",
  "closedAt": null,
  "createdAt": "2026-07-20T12:00:00Z",
  "updatedAt": "2026-07-29T12:00:00Z",
  "progress": {
    "cfi": "epubcfi(/6/8!/4/2)",
    "locationLabel": "Chapter 08 · 42%",
    "updatedAt": "2026-07-29T12:00:00Z"
  },
  "annotations": []
}
```

`sourceReadingSessionId` is a stable identity within one source archive. It is
used for archive structure, diagnostics, selection, and deterministic
filenames. It is not a destination database primary key. Live contracts should
use explicit local names such as `reading_session_id` when exposing server
identity; the archive never uses a bare `id` property.

## Location

Every located record uses the same object:

```json
{
  "cfi": "epubcfi(/6/8!/4/2)",
  "locationLabel": "Chapter 08 · 42% · The Blackstaff"
}
```

- `cfi` is the opaque machine anchor.
- `locationLabel` is an optional opaque Reader-generated display and sorting
  companion.
- The Reader must keep a label stable and string-sortable in reading order
  within the same Book and Session.
- Decorative context may be appended to a label.
- The server stores, returns, imports, and exports both values unchanged.
- The server does not parse, normalize, infer, reconstruct, or derive either
  value from EPUB content.
- `locationLabel` is not selected text, a title, note, category, or other
  user-authored annotation content.

The same `cfi` and optional `locationLabel` pair locates progress, highlights,
highlights with notes, and bookmarks. Progress carries the pair directly;
annotations carry it in `location`. EPUB page numbers are not durable anchors.

## Progress

Progress is the current located state of a Reading Session:

```json
{
  "cfi": "epubcfi(/6/8!/4/2)",
  "locationLabel": "Chapter 08 · 42%",
  "updatedAt": "2026-07-29T12:00:00Z"
}
```

The canonical interchange representation is not a standalone numeric percent.
The Reader supplies any percentage-like display text as part of
`locationLabel`. The server does not derive percentage from CFI.

List projections may expose separate summary metadata when a product surface
needs it. Such projection fields are not part of the canonical progress object.

## Annotations

Annotation kinds are only `highlight` and `bookmark`. An annotation belongs to
one Reading Session and inherits its user and Book context.

### Highlight

```json
{
  "clientAnnotationId": "reader-highlight-42",
  "kind": "highlight",
  "location": {
    "cfi": "epubcfi(/6/8!/4/2)",
    "locationLabel": "Chapter 08 · 42%"
  },
  "body": {
    "text": "The selected passage",
    "prefix": "Text immediately before ",
    "suffix": " text immediately after.",
    "color": "yellow",
    "note": "This passage explains the central argument."
  },
  "createdAt": "2026-07-28T12:00:00Z",
  "updatedAt": "2026-07-28T12:00:00Z"
}
```

Highlight body rules:

- `text` is required and contains the selected text exactly once.
- `prefix` and `suffix` are optional immediate surrounding text used by a
  Reader to verify or repair an anchor when the CFI does not resolve cleanly.
- `color` is highlight presentation metadata. Supported tokens are `yellow`,
  `green`, `blue`, `pink`, `purple`, and `orange`.
- `note` is optional user-authored prose attached to the highlight.
- The server stores these fields; it does not evaluate anchoring quality or
  search EPUB content during normal runtime.

There is no selector/body duplication and no standalone note annotation kind.

### Bookmark

```json
{
  "clientAnnotationId": "reader-bookmark-17",
  "kind": "bookmark",
  "location": {
    "cfi": "epubcfi(/6/10!/4/2)",
    "locationLabel": "Chapter 09 · 47%"
  },
  "createdAt": "2026-07-29T11:00:00Z",
  "updatedAt": "2026-07-29T11:00:00Z"
}
```

A bookmark has no `body`. It cannot carry highlighted text, quote context,
color, or a note. Its `locationLabel` supplies human-readable location text.
The intentionally invalid
[`examples/invalid-bookmark-with-body.json`](examples/invalid-bookmark-with-body.json)
shows a payload rejected by this rule.

## Storage mapping

The Django model uses snake_case columns while JSON interchange uses camelCase:

| Interchange | Model field |
| --- | --- |
| `sourceReadingSessionId` | archive-local only; never a destination primary key |
| `clientAnnotationId` | `client_id` |
| `progress.cfi` | `progress_cfi` |
| `progress.locationLabel` | `progress_location_label` |
| `progress.updatedAt` | `progress_updated_at` |
| `location.cfi` | `cfi` |
| `location.locationLabel` | `location_label` |
| `body.text` | `highlight_text` |
| `body.prefix` | `quote_prefix` |
| `body.suffix` | `quote_suffix` |
| `body.color` | `highlight_color` |
| `body.note` | `comment_text` |

Soft deletion is server state. Deleted annotations are omitted from archives.
`clientAnnotationId` is the stable Reader-generated identity used for client
correlation and retry-safe synchronization. It is unique within one Reading
Session and maps to `Annotation.client_id`; it is not the local Annotation
database primary key.

## Import and export

Native import/export preserves the objects above. Foreign provider formats must
be converted outside the Library server by a Reader client or dedicated tool.
The Library server does not repair EPUBs, resolve CFIs, or infer locations while
importing Marginalia.

Import and export exclude Sessions without non-deleted Annotations by default.
The workflow-level `Include empty sessions` option includes them explicitly;
it does not change the canonical Session object.

Archive-only Book identity, envelope, and packaging rules are documented
in `../marginalia-export.md`.
