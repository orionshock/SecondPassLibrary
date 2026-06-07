# SPL Marginalia Export Format

This is the baseline Second Pass Library marginalia export contract.

It is distinct from the normal Reading API annotation response shape. The normal API is optimized for live client CRUD. This export format is a portable, nested snapshot of user-owned reading data for one book or one session.

Current support is export-only. Import and import preview are future work.

## Routes

Product UI:

```text
GET /reading/export/
```

JSON downloads:

```text
GET /api/v1/reading/export/books/<book_id>/
GET /api/v1/reading/export/books/<book_id>/<session_id>/
```

The export API is Django session-authenticated only. Client API bearer tokens are rejected. Export requires current book visibility and includes only sessions owned by the requesting user. A mismatched book/session URL returns 404.

## Top-Level Object

```json
{
  "type": "SecondPassMarginaliaExport",
  "schema_version": "0.1.0",
  "profile": "https://secondpasslibrary.local/specs/reading-session-annotations/0.1.0",
  "generated_at": "2026-06-06T12:00:00+00:00",
  "generator": "Second Pass Library",
  "scope": {},
  "books": []
}
```

Fields:

- `type`: always `SecondPassMarginaliaExport`.
- `schema_version`: export schema version; current value is `0.1.0`.
- `profile`: reading-session annotation profile URI used by annotation/progress payloads.
- `generated_at`: export generation timestamp.
- `generator`: exporting application name.
- `scope`: describes the export route scope.
- `books`: exported books. Current routes export exactly one book.

## Scope

Book export:

```json
{
  "type": "book",
  "book": "book:sha256:<hash>"
}
```

Session export:

```json
{
  "type": "session",
  "book": "book:sha256:<hash>",
  "session": "session-1"
}
```

When a book file checksum is not available, `book` may fall back to an internal book identifier. Importers should prefer `book:sha256:<hash>` when present.

## Book Object

Book objects contain book-level context once. Annotations inherit book context from nesting and do not repeat full book metadata.

Fields:

- `title`
- `subtitle`
- `authors`
- `series`
- `series_index`
- `language`
- `isbn`
- `epub_unique_identifier`
- `source`: `book:sha256:<hash>` when available
- `file_hash`: `sha256:<hash>` when available
- `sessions`

`source` and `file_hash` appear before `sessions` when present.

## Session Object

Sessions use export-local identifiers, not SPL database ids.

Fields:

- `export_session_id`: `session-1`, `session-2`, etc.
- `name`
- `status`
- `started_at`
- `completed_at`
- `created_at`
- `updated_at`
- `notes`
- `progress`
- `annotations`

`progress` is either a progress object or `null`.

## Progress Object

Fields:

- `current_location`
- `progression`
- `profile_version`
- `updated_at`

`current_location` is the server's stored EPUB locator JSON. `progression` is a derived/display scalar, not a substitute for the canonical current location.

## Annotation Object

Annotations do not include SPL database annotation ids and do not include a database session id. They inherit book and session context from nesting.

Deleted annotations are excluded from exports. Exported annotation objects still include `is_deleted`, currently `false`, for explicit state.

Fields:

- `motivation`: array of W3C-style motivations.
- `target.selector`: selector object or selector array.
- `body`: W3C-style bodies.
- `is_deleted`
- `created_at`
- `updated_at`

## Selectors

EPUB CFI is the default FragmentSelector format for this export profile.

When only an EPUB CFI exists:

```json
{
  "type": "FragmentSelector",
  "value": "epubcfi(...)"
}
```

The export intentionally omits repetitive `conformsTo` on EPUB CFI FragmentSelectors. The profile defines EPUB CFI as the default FragmentSelector format.

When quote context exists, `target.selector` is an array:

```json
[
  {
    "type": "FragmentSelector",
    "value": "epubcfi(...)"
  },
  {
    "type": "TextQuoteSelector",
    "exact": "selected text",
    "prefix": "optional preceding context",
    "suffix": "optional following context"
  }
]
```

`TextQuoteSelector` context is an anchoring/repair hint. It is not a separate annotation body.

## Bodies

Highlight text exports as:

```json
{
  "type": "TextualBody",
  "purpose": "describing",
  "value": "selected text",
  "color": "yellow"
}
```

Notes/comments export as:

```json
{
  "type": "TextualBody",
  "purpose": "commenting",
  "value": "note text"
}
```

Bookmarks may have an empty `body` array.
