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
- ZIP imports can also use OPF sidecars (Calibre-style) to bootstrap metadata and cover for new books only.

## ZIP OPF sidecars (current)

When importing a `.zip` of EPUBs, the importer can optionally use an OPF sidecar to bootstrap metadata and cover **for new books only** (not a sync/refresh mechanism).

Sidecar lookup (per EPUB member), in order:

- `metadata.opf` in the same directory as the EPUB (Calibre-style)
- same-basename `.opf` in the same directory (`Foo.epub` -> `Foo.opf`)
- if there is exactly one `.opf` in the same directory, use it

Metadata precedence:

- OPF sidecar values win when present; missing fields fall back to EPUB metadata.
- Duplicate EPUB checksum imports are still treated as duplicates and do not refresh metadata or covers.

Media serving note:

- Covers are stored under `MEDIA_ROOT` and addressed under `MEDIA_URL` (default: `/media/`).
- In development, Django serves `MEDIA_URL` only when `DEBUG=True` as a convenience.
- In production, deployments should serve `MEDIA_ROOT` at `MEDIA_URL` outside Django.

## Duplicate detection and filenames

- Duplicate EPUB detection is checksum-driven (file SHA-256), not identifier-driven.
- Human-readable download filenames are generated from `Book` metadata (not from the stored content-addressed filename).
