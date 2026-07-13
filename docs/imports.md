# Imports

Second Pass Library is EPUB-first. Product imports are intended to be API-mediated.
Operator-only management commands are available for direct local imports from a
host/container filesystem path.

## API-mediated imports (synchronous uploads)

Import books with a multipart upload field named `file`:

```text
POST /api/v1/library/imports/
```

### Permissions

Library imports are currently intended for library managers only:

- Owner / Manager / Librarian can import books.
- Readers cannot import books (they receive `403 Forbidden`).
- Import history is not stored. The import endpoint returns the result of the
  synchronous import request.

### Supported uploads

- A single `.epub`
- A simple `.zip` containing `.epub` files (non-EPUB entries are ignored)
  - ZIP imports may include OPF sidecars (Calibre-style) to bootstrap metadata for **new books only**.
  - Sidecar lookup (per EPUB member), in order:
    - `metadata.opf` in the same directory as the EPUB
    - same-basename `.opf` in the same directory (`Foo.epub` -> `Foo.opf`)
    - if there is exactly one `.opf` in the same directory, use it
  - A valid OPF sidecar is a full metadata replacement and takes precedence over EPUB metadata.
  - OPF 2 guide cover references are resolved relative to the sidecar. A valid
    sidecar JPEG, PNG, or WebP cover takes precedence over the embedded EPUB
    cover; missing or invalid sidecar covers fall back to the embedded cover.
    Cover extraction is best-effort and never invalidates an otherwise valid
    book import.
  - Duplicate EPUB checksum imports are still returned as duplicates and do not refresh metadata or covers.

### Resource limits

Uploads are app-limited before parser/checksum work to keep untrusted files from consuming unbounded local resources:

- Single EPUB upload: 200 MiB
- ZIP upload: 1 GiB
- ZIP entries: 5,000 total entries
- EPUB member inside a ZIP: 200 MiB uncompressed
- Total EPUB members inside a ZIP: 2 GiB uncompressed
- Marginalia JSON import: 25 MiB

Large library migrations should be split into smaller ZIP batches. These limits are independent of any reverse-proxy upload limits.

### Response shape

The import response is transient and cannot be retrieved later:

```json
{
  "source_type": "zip",
  "source_label": "bundle.zip",
  "counts": {
    "imported": 1,
    "duplicate": 0,
    "conflict": 0,
    "failed": 1,
    "skipped": 0
  },
  "items": [
    {
      "status": "imported",
      "source_label": "book.epub",
      "book_id": "59ebfe48-3a75-4650-a4cd-5db1d32f5598",
      "safe_message": "Imported EPUB."
    },
    {
      "status": "failed",
      "source_label": "bad.epub",
      "safe_message": "Invalid or unsupported EPUB file."
    }
  ]
}
```

The response does not include operator details or local filesystem paths. There
is no stored import history and no import detail endpoint.

### Unsupported (non-goals)

- Calibre sync/import of `metadata.db` (Second Pass Library is not a Calibre sync target)
- PDF

## Marginalia import policy

Server-side marginalia import supports preview and a minimal apply path for
Second Pass Library Marginalia Profile files only.

Foreign/provider-specific annotation formats should not be imported directly by
the server. A reader client should normalize foreign annotations and submit them
through the normal reading session/progress/annotation APIs, or an external tool
can convert them into the SPL native marginalia profile before server import.

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

Preview stores a short-lived staged copy under `userdata/imports/staged/` and returns an `import_token`. Staged files are filesystem-only, expire after roughly 24 hours, and are deleted after successful apply. Operators can remove expired staged previews explicitly with `python manage.py cleanup_staged_imports`. No import jobs or import history are stored.

The apply endpoint is Django session-authenticated only. Client API bearer tokens are rejected. It requires the preview `import_token`, re-validates the staged payload against the schema, and imports matched sessions from file-hash-matched visible local books. It does not create import jobs and does not accept direct file uploads.

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

## Storage

- Temporary import staging lives under `userdata/imports/` during request
  processing and is cleaned after the synchronous import completes.
- Final stored EPUB files are written through `Book.book_file`; `Book` also owns
  `file_format`, `checksum`, `file_size`, and optional `cover_file`.
- Source filenames exist only as transient import diagnostics and are not stored
  as Book or file provenance.
- Product policy: Books are import-only and file-backed. Fileless metadata-only
  Books are not a supported normal state.

## Operator management command

`python manage.py import_library <path>` is the operator-only host-side import
path. It supports:

- one local `.epub` file
- one local `.zip` archive
- one non-recursive directory containing `.epub` and `.zip` files

It shares the same service path as the upload API:

- single EPUB import
- EPUB member discovery
- ZIP OPF sidecars for new books
- duplicate detection by EPUB checksum
- safe per-item errors
- the same ZIP archive, entry-count, per-member EPUB, and total EPUB payload limits

The command does not create durable import history or database ImportJob records.
It prints per-item results and a summary for the immediate run. Duplicate items
do not fail the command; failed or conflicting items produce a nonzero exit.
