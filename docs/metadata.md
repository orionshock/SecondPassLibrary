# Metadata

Second Pass Library keeps bibliographic metadata normalized around a `Book`.
Import behavior is described in [imports.md](imports.md); API field shapes and
routes are described in [api.md](api.md).

## Canonical Book data

`Book` owns both the user-facing bibliographic record and its stored EPUB:

- title, sort title, and optional subtitle
- authors and series relationships
- publisher, language, and description
- published date and date-precision fields
- identifiers
- Catalog Tags
- `book_file`, `file_format`, `checksum`, and `file_size`
- optional `cover_file`

Import source labels are transient diagnostics, not canonical Book metadata or
provenance. Fileless Books and missing physical EPUB files are repair states,
not supported normal product states.

Series membership is represented by `BookSeries`, which links a Book to a
Series and stores its `series_index`. Author biographies and Series summaries
are optional descriptive metadata.

A Series index is null when its position is unknown, or a positive decimal with
at most two fractional digits. It is stored exactly in `DecimalField(max_digits=8,
decimal_places=2)` and compared numerically; `1`, `1.0`, and `1.00` are the same
position. Values that are zero, negative, malformed, or require more than two
fractional digits are invalid and are never rounded into the catalog.

`BookAuthor.position` is the canonical Author order for a Book. The row with
the lowest position, then through-row id, is the primary Author. Library,
search, Group browse, and Shelf Author sorting compare only that Author's
`sort_name` (falling back to `name`); secondary Authors do not affect sorting.

Author and Series names also maintain indexed, non-unique `normalized_name`
values. Normalization applies Unicode NFKC, trims and collapses whitespace, and
case-folds while preserving punctuation. Author and Series UUIDs are their
identities; names and normalized names are descriptive matching/search aids,
not identity constraints. Explicit creation may therefore create another
same-name record. Renaming preserves the UUID and every Book relationship.

Name-based import and inline Series assignment reuse an entity only when one
normalized match exists. No match creates an entity where that workflow already
allows creation. Multiple matches are ambiguous and are rejected through the
workflow's bounded conflict or field-validation result instead of selecting an
arbitrary record. Matching never merges, renames, reassigns, or deletes catalog
entities automatically.

## Dates and identifiers

Published dates retain their known precision instead of inventing missing
month or day values. See the API contract for the current date fields.

`BookIdentifier` stores external identifiers such as ISBN-10, ISBN-13, ASIN,
DOI, OCLC, LCCN, Open Library identifiers, Calibre identifiers, EPUB unique
identifiers, and URI/URN values. Its public shape is `scheme` and `value`; the
normalized value used for uniqueness is internal.

Book metadata edits replace identifiers through the Book metadata endpoint.
Omitting `identifiers` preserves existing identifiers; an empty list clears
them. EPUB duplicate detection remains checksum-based, not identifier-based.

## Catalog Tags

Catalog Tags are controlled, normalized facets. They are the public tagging
contract; there is no legacy Subject model or Subject API. EPUB subject values
and Calibre tag metadata are normalized through the same Catalog Tag resolver.

`CatalogTag` preserves the first-created display spelling and generates a
stable slug from its normalized identity. Matching uses Unicode normalization,
collapsed whitespace, and casefolding. `BookCatalogTag` explicitly relates a
tag to a Book, and an unused tag is removed when its final relationship is
deleted.

The API uses `catalog_tags` for compact Book rows, Book Detail, and Book
metadata writes. `tag=<slug>` is the compact query parameter for filtering by
Catalog Tag slug.

Book PATCH treats `catalog_tags` as a complete replacement when supplied.
Omitting it preserves current relationships; `[]` clears them. Tag list and
detail payloads expose only their documented public fields and viewer-visible
counts. Duplicate-checksum imports return the existing Book without refreshing
its Catalog Tags.

## Stored EPUB and filenames

EPUB bytes are stored through `Book.book_file` under content-addressed storage.
The checksum is the canonical duplicate key. Human-readable download filenames
are generated from current Book metadata rather than retained source filenames
or storage keys.

Stored EPUBs are protected content. Clients download them through the
authenticated API URL provided by Book Detail.

## Covers

`Book.cover_file` stores the current optional cover. Cover URLs are public
display assets, while the EPUB remains an authenticated download.

Cover input is accepted only when it decodes as JPEG, PNG, or WebP and satisfies
the configured 10 MiB and 20-million-pixel limits. Validated original bytes are
stored without re-encoding or thumbnail generation. Storage is
content-addressed, so identical files can be shared. Replacing a cover removes
an old file only after the database change commits and only when no other Book
references it.

Import cover precedence is:

1. a valid, safely resolved cover referenced by the selected ZIP OPF sidecar;
2. a valid cover embedded in the EPUB package;
3. no cover.

Embedded discovery supports the EPUB 3 `cover-image` manifest property and the
EPUB 2 cover metadata/manifest convention. An OPF 2 guide cover reference is
resolved relative to its sidecar.

Missing, unsafe, ambiguous, colliding, corrupt, oversized, or unsupported
sidecar cover input is ignored. Import continues and falls back to embedded
cover extraction when possible. Cover extraction and storage failures are
non-fatal to an otherwise valid metadata import. Duplicate or conflicting Book
imports do not attach or replace a cover.

OPF sidecars may contribute only the supported metadata and a referenced JPEG,
PNG, or WebP cover. Arbitrary sidecar assets are not imported.

## Import relationship

An EPUB must remain valid even when a ZIP supplies a sidecar OPF. For a new
Book, a qualifying sidecar metadata record replaces the embedded metadata
candidate as a whole; it is not merged field by field. Embedded EPUB metadata
is used when no qualifying sidecar is available. Exact sidecar selection,
validation, duplicate/conflict behavior, limits, and operational workflows are
owned by [imports.md](imports.md).

Raw imported metadata is not retained on `Book`. If durable provenance is
needed later, it should be modeled separately rather than overloading the
canonical bibliographic record.
