# Metadata

## Core objects

- `Book`: canonical, user-facing bibliographic fields plus stored EPUB fields.
  `Book` owns `book_file`, `file_format`, `checksum`, `file_size`,
  `source_filename`, and optional `cover_file`.

Notes:
- `Book.subtitle` may be blank.
- `Author.biography` and `Series.summary` are optional catalog description fields.
- Series data is represented by `BookSeries`, which links `Book` to `Series`
  and stores `series_index`.
- `BookIdentifier` is Book-owned editable bibliographic metadata with a public
  `scheme`/`value` shape and an internal normalized value for uniqueness.
- Fileless Books and missing physical EPUB files are repair states, not normal
  product states.
- `CatalogTag` stores a first-created display name, Unicode/casefold-normalized
  identity, and generated unique slug. `BookCatalogTag` explicitly relates tags
  to Books; tags are created lazily and deleted when their final relationship is removed.

## Identifiers

- `BookIdentifier` stores external/source identifiers (ISBNs and non-ISBN identifiers like ASIN/DOI/OCLC/LCCN/Open Library IDs/Calibre IDs/EPUB unique identifiers/URI/URN/etc).
- Book edits replace identifiers through `PATCH /api/v1/library/books/<book_id>/`.
  Omitting the field preserves existing identifiers; an empty list clears them.

## Catalog Tags

- EPUB subjects and existing Calibre tag metadata use the same CatalogTag resolver.
- Book PATCH accepts `catalog_tags` as a complete replacement list of names.
  Omitting it preserves relationships; `[]` clears them.
- Display names preserve the first-created spelling and casing. Matching uses
  Unicode normalization, collapsed whitespace, and casefolding.
- Duplicate-checksum imports return the existing Book without refreshing tags.

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
- ZIP imports can use OPF sidecars (Calibre-style) to bootstrap metadata for
  new books only. Sidecar cover/assets are deferred.

## ZIP OPF sidecars (current)

When importing a `.zip` of EPUBs, the importer can optionally use an OPF sidecar
to bootstrap metadata **for new books only** (not a sync/refresh mechanism).
Sidecar cover/assets are deferred.

Sidecar lookup (per EPUB member), in order:

- `metadata.opf` in the same directory as the EPUB (Calibre-style)
- same-basename `.opf` in the same directory (`Foo.epub` -> `Foo.opf`)
- if there is exactly one `.opf` in the same directory, use it

Metadata precedence:

- A valid OPF sidecar is a full metadata replacement for new imports. It must
  have a real nonblank, non-`Untitled` title before it replaces EPUB metadata.
- Duplicate EPUB checksum imports are still treated as duplicates and do not refresh metadata or covers.

Media serving note:

- Covers are stored under `MEDIA_ROOT/covers` and addressed under `MEDIA_URL` (default: `/media/`).
- Django serves `/media/covers/` narrowly so covers render in direct-server usage.
- Stored EPUB files and other protected media are never served as raw media URLs.

## Duplicate detection and filenames

- Duplicate EPUB detection is checksum-driven (file SHA-256), not identifier-driven.
- Human-readable download filenames are generated from `Book` metadata (not from the stored content-addressed filename).
