# Metadata

## Core objects

- `Book`: canonical, user-facing bibliographic fields (title/authors/series/publisher/language/published date/ISBN/subjects)
- `BookFile`: stored content blob (EPUB), stored content-addressed by checksum (one Book has at most one BookFile)

Notes:
- `Book.subtitle` may be blank.
- `Book.series_index` supports integers or one decimal place (e.g. `5` or `5.1`).
- `BookIdentifier` is editable bibliographic metadata (scheme/value/source/is_primary) and does not automatically rewrite `Book.isbn`.

## Identifiers

- `Book.isbn` is a convenience/display field (prefer ISBN-13 when available), not the only identifier.
- `BookIdentifier` stores external/source identifiers (ISBNs and non-ISBN identifiers like ASIN/DOI/OCLC/LCCN/Open Library IDs/Calibre IDs/EPUB unique identifiers/URI/URN/etc).
- Identifiers imported from EPUB metadata use `source=epub`.

## Import/cleanup philosophy

- Keep `Book` user-facing fields clean and stable.
- If raw imported metadata/provenance is needed later, model it separately (don't overload `Book`).

## Cover art (current)

- `Book.cover_file` stores the current cover image (optional).
- `cover_url` is exposed in Book API payloads and recent reading payloads; it is `null` when no cover exists.
- Covers are validated with Pillow and stored as the original validated bytes (no re-encoding/thumbnails yet).
- EPUB embedded cover extraction is implemented during import (best-effort).
- Cover discovery uses the EPUB package OPF:
  - EPUB3 manifest item with `properties~="cover-image"`
  - EPUB2 `<meta name="cover" content="...">` + manifest lookup
- Unsupported/corrupt/oversized covers are ignored; import still succeeds.
- OPF sidecar cover/metadata support is planned follow-up work.

## Duplicate detection and filenames

- Duplicate EPUB detection is checksum-driven (file SHA-256), not identifier-driven.
- Human-readable download filenames are generated from `Book` metadata (not from the stored content-addressed filename).
