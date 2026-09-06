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

Normalized names support deterministic lookup; they do not prove entity
identity. Import relationship resolution therefore follows one policy for both
Authors and Series:

- zero normalized matches creates a new Author or Series;
- exactly one normalized match reuses that existing entity;
- two or more normalized matches produce an import `conflict` without creating
  the Book or choosing, merging, or creating another matching entity.

An ambiguity conflict identifies the incoming name and matching entity type.
The operator must resolve the ambiguous catalog records or adjust the source
metadata, then retry the import. Distinct Authors and Series may legitimately
retain the same normalized name; the importer does not impose global name
uniqueness as a shortcut around that ambiguity.

Imported titles, names, tags, identifier schemes, and identifier values are
NFKC-normalized and whitespace-collapsed before persistence or comparison.
Scheme-specific identifier normalization removes ISBN punctuation, folds DOI
URL/prefix forms, and applies the stable casing rules used by the import
service. Display values remain separate from normalized matching values. Book
identifiers are repeatable metadata, not Book identity: the same ISBN, EPUB
UID, Calibre ID, or other scheme/value may be attached to multiple Books. An
identical normalized identifier may appear only once within one Book.
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

### Book description HTML contract

`Book.description` follows the shared [sanitized limited HTML](api.md#sanitized-limited-html)
contract. Do not infer additional supported markup from Calibre output;
Calibre-style comments are a source-compatibility motivation, not the authority
for this contract.

The server owns this security boundary through the `nh3` policy in
`backend/core/rich_text.py`. Every normal description write
sanitizes before persistence, including EPUB/library import, Book metadata
edits through the API/Product UI, and Django Admin edits. The database stores
only the sanitized representation. API serializers return that stored value
unchanged: there is no read-time sanitizer, plain-text conversion, or markup
reinterpretation at projection time. Imported and operator-edited metadata is
untrusted regardless of its source.

After sanitization, the complete serialized description must not exceed
25,000 characters. Markup counts toward the limit. An over-limit import
candidate fails without truncating or partially persisting the Book.

When this contract was introduced, a temporary pre-release data migration
normalized existing stored Book descriptions with the same effective policy.
That migration is historical implementation context, not a compatibility
promise or a second policy owner.

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

Imports are create-only at the Book boundary. The EPUB SHA-256 checksum is the
only authoritative duplicate-file identity. An exact checksum duplicate
returns the existing Book without changing metadata, identifiers, Catalog
Tags, EPUB bytes, or cover; import does not refresh it from newer embedded or
sidecar metadata. For a new Book, the import may reuse an unambiguous Author,
Series, or Catalog Tag and creates only the new Book's relationships. Identifier
metadata already attached to another Book is attached to the new Book normally
and does not produce a warning, error, or conflict.

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
imported, and checksum-duplicate or genuinely conflicting Book candidates do
not acquire a cover. A new Book whose identifier metadata overlaps another
Book imports normally and may acquire its own cover.

## Limits and archive safety

Application limits are enforced before untrusted input reaches expensive
parser work. Product UI/API imports use tighter limits because parsing occurs
in the web process:

- uploaded EPUB: 64 MiB compressed, 1,000 entries, 32 MiB per expanded member,
  256 MiB aggregate expanded contents, and 50:1 per-member compression ratio;
- encrypted EPUB members, unsafe member names, and normalized duplicate names are rejected
- Product UI/API upload: 128 MiB
- uploaded batch ZIP: 2,000 entries, 64 MiB per expanded EPUB, 256 MiB
  aggregate expanded EPUBs, and 50:1 outer ZIP compression ratio;
- marginalia JSON import: 25 MiB

Trusted local CLI imports retain the larger established ceilings: 200 MiB
compressed EPUBs, 2,000 EPUB entries, 100 MiB per expanded member, 1 GiB
aggregate expanded EPUB contents, 100:1 EPUB member ratio, 5,000 outer ZIP
entries, 200 MiB per outer EPUB member, and 2 GiB aggregate outer EPUB data.

Large migrations should use the local CLI commands below. Reverse-proxy limits
may impose a lower ceiling on the Product UI/API upload.

Archive members and sidecar references are resolved without exposing or
trusting unsafe filesystem paths. Import result messages use safe source labels
and do not return local paths, storage keys, or internal parser details.

## Book import results

The API returns a transient batch summary with per-item `imported`, `duplicate`,
`conflict`, `failed`, or `skipped` status. Each item may include its safe source
label, resulting Book ID, and a bounded message. Results cannot be retrieved
after the request; there is no import detail endpoint.

`duplicate` means an exact EPUB checksum match. A relationship `conflict`
means normalized Author or Series lookup found multiple possible existing
entities and the importer refused to guess. Shared Book identifier metadata
does not produce either outcome.

Source names exist only for immediate diagnostics and are not retained as Book
metadata or provenance. Final EPUB and cover files are stored through the
fields owned by `Book`.

## Operator import commands

The three local commands use the same per-candidate validation, metadata,
cover, duplicate, persistence, and Public Group pipeline as Product UI/API
imports. Candidates run sequentially and print a permanent result immediately;
duplicates do not fail the command, while failures and conflicts produce a
nonzero exit.

`import_library_folder_of_zip <path>` preserves the existing workflow for one
EPUB, one per-Book ZIP, or a recursively scanned directory of EPUB/ZIP files.
Each ZIP retains the existing nested EPUB, OPF, and referenced-cover semantics.
Discovery is path-sorted. The source is limited to 100,000 EPUB/ZIP files and
500 GiB of source files; each ZIP retains the existing member-count,
per-EPUB, and aggregate expanded-EPUB limits.

`import_library_aio_zip <zip>` reads one large nested ZIP without bulk
extraction. A logical directory must contain exactly one EPUB and may contain
`metadata.opf` and an adjacent or OPF-referenced cover. Ambiguous directories
fail individually; metadata-only directories are skipped. The outer ZIP is
limited to 20 GiB compressed, 250,000 members, 100,000 logical candidates, and
500 GiB of EPUB members. Encrypted, unsafe, colliding, and excessively
compressed members remain rejected. The ordinary 200 MiB per-EPUB limit still
applies.

`import_library_tree <directory>` recursively reads the same logical candidate
shape directly from a local or mounted tree. It does not follow symlinks and
enforces source-root containment, 100,000 candidates, and 500 GiB of EPUB
files. For a read-only Docker bind mount, run an ephemeral application
container, for example:

```sh
docker compose run --rm --no-deps --user secondpass \
  -v /host/library:/import:ro --entrypoint python secondpasslibrary \
  manage.py import_library_tree /import
```

All modes retain the per-EPUB, OPF, cover, image, and internal archive safety
limits. They report destination free space and stop before the next candidate
when less than 1 GiB plus that candidate's compressed size would remain.
Ctrl+C stops nonzero with the last completed candidate. Rerun the same command;
completed Books are resolved by existing checksum duplicate detection. There
is no durable checkpoint or exact resume index.

These are generic EPUB/OPF/cover source adapters. They do not read Calibre
`metadata.db`, depend on Calibre, or interpret other metadata databases.

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
