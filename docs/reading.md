# Reading

Reading metadata is user-owned and must remain durable/exportable.

## Sessions

- “Open book for reading” uses lazy active-session creation.
- “Start over” creates a new active session and preserves history.

Endpoints:

```text
GET  /api/v1/reading/books/<book_id>/active-session/
POST /api/v1/reading/books/<book_id>/start-over/          (optional body: {"name": "Second pass"})
```

## Progress

Progress is one-to-one per session (auto-created if missing):

```text
GET   /api/v1/reading/sessions/<session_id>/progress/
PATCH /api/v1/reading/sessions/<session_id>/progress/
```

Example payload:

```json
{
  "device": "<device_id>",
  "locator": {"cfi": "/6/4", "chapter": "c1", "offset": 123},
  "progression": 0.42
}
```

## Locators (JSON conventions)

Locators are flexible JSON. For EPUB, prefer:

```json
{
  "format": "epub",
  "href": "Text/chapter01.xhtml",
  "cfi": "epubcfi(...)",
  "progression": 0.1234,
  "position": 12345,
  "text": {"exact": "…", "prefix": "…", "suffix": "…"}
}
```

Notes:
- `href` is the EPUB internal content document path when available.
- `cfi` is preferred when the client can provide it.
- `progression` is a float between 0 and 1 when available.
- PDF locators are not supported.

## Annotations (highlights, notes, bookmarks)

Annotations are stored as `Annotation` records:

- List/create/update: `/api/v1/reading/annotations/`
- Optional filters: `?book_id=<book_id>` and/or `?session_id=<session_id>`
- Delete uses soft delete (`is_deleted=true`) instead of hard deletion.
