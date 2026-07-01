# Imports

Second Pass Library is EPUB-first. Imports are intended to be API-mediated, with a dev/admin management command available for convenience.

## API-mediated imports (staged uploads)

Create an import job (multipart field name is `file`):

```text
POST /api/v1/library/imports/
```

### Permissions

Import jobs are currently intended for library managers only:

- Owner / Manager / Librarian can create/list/retrieve import jobs.
- Readers cannot create/list/retrieve import jobs (they receive `403 Forbidden`).

List import jobs:

```text
GET /api/v1/library/imports/   (paginated)
```

Get a specific job:

```text
GET /api/v1/library/imports/<id>/
```

### Supported uploads

- A single `.epub`
- A simple `.zip` containing `.epub` files (non-EPUB entries are ignored)
  - ZIP imports may include OPF sidecars (Calibre-style) to bootstrap metadata and cover for **new books only**.
  - Sidecar lookup (per EPUB member), in order:
    - `metadata.opf` in the same directory as the EPUB
    - same-basename `.opf` in the same directory (`Foo.epub` -> `Foo.opf`)
    - if there is exactly one `.opf` in the same directory, use it
  - OPF values take precedence over EPUB metadata when present.
  - Duplicate EPUB checksum imports are still rejected/skipped and do not refresh metadata or covers.

### Unsupported (non-goals)

- Calibre sync/import of `metadata.db` (Second Pass Library is not a Calibre sync target)
- PDF

## Marginalia import policy

Server-side marginalia import supports preview and a minimal apply path for SPL native marginalia export files only.

Foreign/provider-specific annotation formats should not be imported directly by the server. A reader client should normalize foreign annotations and submit them through the normal reading session/progress/annotation APIs, or an external tool can convert them into the SPL native marginalia export format before server import.

Product UI:

```text
GET /reading/import/
```

Preview API:

```text
POST /api/v1/reading/import/preview/
```

The preview endpoint is Django session-authenticated only. Client API bearer tokens are rejected. It validates the uploaded JSON against `docs/specs/marginalia-export.schema.json`, summarizes books/sessions/annotations, reports visible local book matches by file hash only, and does not write to the database.

Apply API:

```text
POST /api/v1/reading/import/apply/
```

Preview stores a short-lived staged copy under `userdata/imports/staged/` and returns an `import_token`. Staged files are filesystem-only, expire after roughly 24 hours, and are deleted after successful apply. No import jobs or import history are stored.

The apply endpoint is Django session-authenticated only. Client API bearer tokens are rejected. It accepts the preview `import_token`, re-validates the staged payload against the schema, and imports matched sessions from file-hash-matched visible local books. It does not create import jobs. The older file-upload apply path remains available for compatibility, but the product UI uses `import_token`.

Apply may include an optional multipart `selection` field containing JSON. If omitted, all matched sessions are imported. If present, only selected sessions are imported, and each selected session may override the imported session `name` and `notes`.

```json
{
  "books": [
    {
      "source": "book:sha256:...",
      "sessions": [
        {
          "export_session_id": "session-1",
          "selected": true,
          "name": "Imported session name",
          "notes": "Imported session notes"
        }
      ]
    }
  ]
}
```

Selection uses export-local book/session identifiers from the uploaded file, not SPL database ids. Session selection is supported; annotation-level selection is not.

### Marginalia apply policy

Server-side apply follows these rules:

- Import matched books only. A book is matched only when it maps to a visible local book for the requesting user.
- Match marginalia imports by book file hash only. Do not use ISBN or title/author fallback for server-side locator import.
- Perform only shallow CFI-shaped validation server-side: EPUB CFI values must look like `epubcfi(...)`; malformed locator sessions should be sent through Reader-assisted import.
- Skip unmatched books and report them as unmatched/possibly foreign; do not create local books from marginalia imports.
- Treat the import unit as a reading session. Annotation-level selection/import is not supported.
- Create new historical/imported sessions for matched books. Exported active sessions must not become active local sessions; they should import as historical/inactive sessions.
- Treat possible duplicates as warnings, not blockers. Do not silently de-duplicate or overwrite existing sessions/annotations without an explicit future policy.
- Continue to reject Client API bearer tokens for server-side marginalia import.

## Models

- `ImportJob`: tracks one upload (EPUB or ZIP), counts, and status
- `ImportJobItem`: per-file result entries within a job (imported/duplicate/failed)

## Storage

- Temporary staged imports live under `userdata/imports/`.
- Final stored EPUB files are written to content-addressed storage under `userdata/media/books/<first2>/<next2>/<sha256>.epub`.
- Product policy: Books are import-only and file-backed. In normal flows a `Book` is created together with its `BookFile` as one logical import operation; fileless metadata-only Books are not a supported state.

## Management command note

`python manage.py import_epub ...` is a dev/admin utility (host-side). The intended product import path is the API upload workflow above.
