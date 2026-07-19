# Imports

Second Pass Library is EPUB-first. Product imports are synchronous,
session-authenticated workflows for Owner, Manager, and Librarian users.
Operator-only management commands provide the same import behavior for local
host or container paths.

Normalized metadata and cover meaning are described in
[metadata.md](metadata.md). Exact HTTP fields and responses are described in
[api.md](api.md).

## Book import workflow

The Product UI submits a multipart `file` upload to the Library import API.
Readers cannot import Books. The request accepts:

- one `.epub` file
- one `.zip` containing EPUB files and optional matching OPF sidecars

Non-EPUB ZIP entries are ignored unless they are a selected OPF sidecar or its
safely resolved cover image. Imports complete within the request. The system
does not create import jobs or retain import history.

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

Checksum duplicate detection takes precedence over metadata refresh. A
duplicate returns the existing Book without changing metadata, identifiers,
Catalog Tags, EPUB bytes, or cover. A new candidate whose identifiers conflict
with an existing Book is reported as a conflict rather than partially applied.

### Cover import behavior

Embedded EPUB cover extraction is best-effort. A selected sidecar may reference
a JPEG, PNG, or WebP cover; OPF 2 guide references are resolved relative to the
sidecar. A valid sidecar cover takes precedence over an embedded cover.

Missing, unsafe, ambiguous, colliding, invalid, unsupported, or oversized
sidecar cover input is ignored and embedded extraction is attempted. Cover
validation or storage failure does not invalidate an otherwise valid Book
import. Arbitrary sidecar assets are not imported. See
[metadata.md](metadata.md) for validation, storage, and serving rules.

## Limits and archive safety

Application limits are enforced before untrusted input reaches expensive
parser or checksum work:

- single EPUB upload: 200 MiB
- ZIP upload: 1 GiB
- ZIP entries: 5,000
- EPUB member in a ZIP: 200 MiB uncompressed
- total EPUB members in a ZIP: 2 GiB uncompressed
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

Source names exist only for immediate diagnostics. They are not stored as a
Book `source_filename`, file provenance, or canonical metadata. Final EPUB and
cover files are stored through the fields owned by `Book`.

## Operator import command

`python manage.py import_library <path>` imports:

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

## Marginalia import

Marginalia import is a separate, session-only Product UI workflow. Client API
bearer tokens cannot call its preview or apply endpoints.

Preview validates a Second Pass Library Marginalia Profile, summarizes its
books, reading sessions, and annotations, and matches only visible local Books
by EPUB file hash. It does not write database records. Foreign/provider-specific
formats must first be normalized by a reader client or external conversion
tool.

A successful preview creates a short-lived staged file under
`userdata/imports/staged/` and returns an import token. Staged files expire
after roughly 24 hours, are deleted after successful apply, and can be cleaned
with `python manage.py cleanup_staged_imports`.

Apply revalidates the staged profile and can import all matched sessions or a
selection of sessions. Selection uses export-local book/session identifiers;
it may override an imported session's name and notes. Annotation-level
selection is not supported.

Apply follows these rules:

- match by file hash only, never ISBN or title/author fallback;
- import only Books visible to the requesting user;
- skip and report unmatched Books without creating local Books;
- accept only shallow `epubcfi(...)` locator validation server-side;
- create new historical/inactive sessions, including exported active sessions;
- report possible duplicates as warnings without overwriting existing data.

Marginalia staging is filesystem-only. It does not create import jobs or import
history.

## Unsupported import behavior

The following are intentionally unsupported:

- PDF import
- Calibre `metadata.db` synchronization
- arbitrary OPF sidecar assets beyond a supported referenced cover
- sidecar-driven refresh of an existing checksum-duplicate Book
- metadata-only or normally fileless Books
- raw serving of stored EPUB files from `/media/books/`
- a separate `BookFile` import model or endpoint
