# Imports

Second Pass Library is EPUB-first. Product imports are synchronous,
session-authenticated workflows for Owner, Manager, and Librarian users.
Operator-only management commands provide the same import behavior for local
host or container paths.

This document owns import metadata precedence, normalization, duplicate
advisories, and file/archive safety. [API](api.md) owns shared HTTP conventions;
active serializers own exact upload and result fields.

## Book import workflow

The Product UI submits a multipart `file` upload to the Library import API.
Readers cannot import Books. The request accepts:

- one `.epub` file
- one `.zip` containing EPUB files and optional matching OPF sidecars

Non-EPUB ZIP entries are ignored unless they are a selected OPF sidecar or its
safely resolved cover image. Imports complete within the request. The system
does not create import jobs or retain import history.

## Metadata identity and normalization

Author and Series UUIDs are canonical identity; their names are deliberately
non-unique. Name matching is only an import/editing convenience: Unicode NFKC,
trimmed and collapsed whitespace, and case-folding produce an advisory
`normalized_name` while preserving punctuation. Zero normalized matches may
create an entity, one may be reused, and multiple matches are ambiguous. The
system never treats normalized equality as authority to merge, rename,
reassign, or delete records. Renaming an Author or Series preserves its UUID
and relationships.

Imported titles, names, tags, identifier schemes, and identifier values are
NFKC-normalized and whitespace-collapsed before persistence or comparison.
Scheme-specific identifier normalization removes ISBN punctuation, folds DOI
URL/prefix forms, and applies the stable casing rules used by the import
service. Display values remain separate from normalized matching values.
Catalog Tag names use the same name normalization as imports but have unique
normalized identity; the first persisted display spelling and stable slug are
retained when later imports reuse a Tag.

The Primary Author is the Author on the lowest `BookAuthor.position`, with the
through-row UUID as deterministic fallback. Primary-author sorting uses only
that Author's sort name/name; secondary Authors do not affect it. Import order,
not alphabetical display order, establishes author positions.

A Series index is absent or an exact positive decimal with at most eight total
digits and two fractional digits. Storage is `Decimal(8,2)` and the wire value
is a fixed two-decimal string. Values are validated exactly and never rounded;
numeric equivalents such as `1`, `1.0`, and `1.00` represent the same index.
Partial publication dates retain their supplied year, month, or day precision
rather than inventing missing components.

## Metadata precedence and persistence

### EPUB and OPF metadata precedence

Every candidate must contain a valid EPUB; an OPF sidecar cannot make an
invalid EPUB importable. Embedded EPUB metadata is the baseline and fallback.

For each EPUB member in a ZIP, sidecar lookup uses this order:

1. `metadata.opf` in the EPUB's directory;
2. a same-basename OPF in that directory (`Foo.epub` and `Foo.opf`);
3. the only OPF in that directory, when exactly one exists.

A safely parsed sidecar with a real, nonblank, non-`Untitled` title replaces
the embedded metadata candidate for a new Book. This is a whole-record
replacement, not a field-by-field merge or a later synchronization mechanism.
Missing, malformed, oversized, or non-qualifying sidecars fall back to embedded
EPUB metadata.

Calibre/OPF Series indexes are whitespace-trimmed and parsed as exact decimals.
Positive values with at most two fractional digits are preserved through
preview, persistence, and result output. Blank, malformed, zero, negative, or
over-precision values are treated as an unknown Series position; the Book and
Series metadata remain importable, and the value is never rounded.

Imports are create-only at the Book boundary. A checksum duplicate returns the
existing Book without changing metadata, identifiers, Catalog Tags, EPUB bytes,
or cover; import does not refresh it from newer embedded or sidecar metadata.
For a new Book, the import may reuse an unambiguous Author, Series, or Catalog
Tag and creates only the new Book's relationships. An identifier collision with
another Book is advisory conflict detection, not proof that records should be
merged, and the candidate is not partially applied.

The selected metadata record supplies the new Book's scalar fields, ordered
Authors, optional Series relationship, identifiers, and Catalog Tags. It is
not blended with an existing Book. Metadata edits outside import follow their
own explicit replacement semantics: supplied relationship collections replace
their prior values, omission preserves them, and an explicit empty collection
clears them.

### Cover import behavior

Embedded EPUB cover extraction is best-effort. A selected sidecar may reference
a JPEG, PNG, or WebP cover; OPF 2 guide references are resolved relative to the
sidecar. A valid sidecar cover takes precedence over an embedded cover.

Missing, unsafe, ambiguous, colliding, invalid, unsupported, or oversized
sidecar cover input is ignored and embedded extraction is attempted. Covers
must be valid JPEG, PNG, or WebP images no larger than 10 MiB or 20 million
decoded pixels. Valid original bytes are stored by content hash and may be
shared by multiple Books. Cover validation or storage failure does not
invalidate an otherwise valid Book import. Arbitrary sidecar assets are not
imported, and duplicate/conflicting Book candidates do not acquire a cover.

## Limits and archive safety

Application limits are enforced before untrusted input reaches expensive
parser or checksum work:

- compressed EPUB, whether uploaded directly or read from a batch ZIP: 200 MiB
- EPUB entries: 2,000
- expanded EPUB member: 100 MiB
- aggregate expanded EPUB contents: 1 GiB
- per-member EPUB compression ratio: 100:1
- encrypted EPUB members, unsafe member names, and normalized duplicate names are rejected
- batch ZIP upload: 1 GiB
- batch ZIP entries: 5,000
- EPUB member expanded from a batch ZIP: 200 MiB
- total EPUB members expanded from a batch ZIP: 2 GiB
- marginalia JSON import: 25 MiB

Large migrations should be split into smaller ZIP batches. Reverse-proxy
limits may impose a lower ceiling.

Archive members and sidecar references are resolved without exposing or
trusting unsafe filesystem paths. Import result messages use safe source labels
and do not return local paths, storage keys, or internal parser details.

## Book import results

The API returns a transient batch summary with per-item `imported`, `duplicate`,
`conflict`, `failed`, or `skipped` status. Each item may include its safe source
label, resulting Book ID, and a bounded message. Results cannot be retrieved
after the request; there is no import detail endpoint.

Source names exist only for immediate diagnostics and are not retained as Book
metadata or provenance. Final EPUB and cover files are stored through the
fields owned by `Book`.

## Operator import command

`python backend/manage.py import_library <path>` imports:

- one local `.epub`
- one local `.zip`
- one non-recursive directory containing `.epub` and `.zip` files

It uses the same import services, checksum duplicate handling, OPF sidecar
behavior, cover precedence, archive limits, and bounded per-item failures as
the Product UI/API path. It prints only the current run's item results and
summary. Duplicate items do not fail the command; failed or conflicting items
produce a nonzero exit.

Temporary request and batch staging lives under `userdata/imports/` and is
cleaned according to the relevant synchronous or staged workflow. No database
ImportJob or durable Book-import history is created.

## Unsupported import behavior

The following are intentionally unsupported:

- PDF import
- Calibre `metadata.db` synchronization
- arbitrary OPF sidecar assets beyond a supported referenced cover
- sidecar-driven refresh of an existing checksum-duplicate Book
- metadata-only or normally fileless Books
