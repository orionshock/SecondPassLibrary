# Imports

Second Pass Library is EPUB-first. Imports are intended to be API-mediated, with a dev/admin management command available for convenience.

## API-mediated imports (staged uploads)

Create an import job (multipart field name is `file`):

```text
POST /api/v1/library/imports/
```

List import jobs:

```text
GET /api/v1/library/imports/
```

Get a specific job:

```text
GET /api/v1/library/imports/<id>/
```

### Supported uploads

- A single `.epub`
- A simple `.zip` containing `.epub` files (non-EPUB entries are ignored)

### Unsupported (by design, for now)

- Calibre/library backup ZIPs
- OPF sidecars
- PDF

## Models

- `ImportJob`: tracks one upload (EPUB or ZIP), counts, and status
- `ImportJobItem`: per-file result entries within a job (imported/duplicate/failed)

## Storage

- Temporary staged imports live under `userdata/imports/`.
- Final stored EPUB files are written to content-addressed storage under `userdata/media/books/<first2>/<next2>/<sha256>.epub`.

## Management command note

`python manage.py import_epub ...` is a dev/admin utility (host-side). The intended product import path is the API upload workflow above.
