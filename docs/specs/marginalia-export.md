# Second Pass Library Marginalia Export Profile

This document defines the canonical portable archive for user-owned Marginalia.
It is a nested snapshot of Books, Reading Sessions, progress, highlights, notes
on highlights, and bookmarks. It is not a live API response shape.

Profile URI:

```text
https://secondpasslibrary.local/specs/marginalia-export/0.1.0
```

The machine-readable contract is
[`marginalia-export.schema.json`](marginalia-export.schema.json). A complete
example is in [`examples/marginalia-export.json`](examples/marginalia-export.json).

The older `reading-session-annotation-profile/` package is historical,
non-canonical JSON-LD exploration.

## Domain and server boundary

- Marginalia belongs to a user.
- Books contain Reading Sessions.
- Reading Sessions contain one located progress record and annotations.
- Session states are only `active` and `closed`.
- Highlights and bookmarks are the annotation kinds. A note is optional text
  attached to a highlight, not a separate annotation kind.

The Library server stores portable locations but is not an EPUB renderer. It
does not parse CFIs or inspect EPUB content during normal runtime to derive a
display location.

The Reader supplies two location values:

- `value`: the EPUB CFI, treated as an opaque machine anchor.
- `locationLabel`: opaque Reader-generated display and sorting text.

The server stores, returns, and exports `locationLabel` unchanged. Within the
same Book and Reading Session, a Reader must generate labels that are stable and
string-sortable in reading order. A label may append decorative context, for
example `Chapter 08 · 42% · The Blackstaff`.

`locationLabel` belongs to the location layer. It is not selected text, a note,
a title, a color/category, or other user-authored content. The server must not
parse, normalize, infer, or reconstruct it from the CFI or EPUB.

## Marginalia API namespace

The new domain uses `/api/v1/marginalia/`. Live Marginalia and Reader-client
responses may use shapes optimized for their operations; the archive shape in
this document remains the canonical import/export interchange format.

This profile does not specify transport routes or authentication. Implemented
routes are documented in the API documentation rather than inferred from the
archive schema.

## Top-level object

```json
{
  "type": "SecondPassMarginaliaExport",
  "schema_version": "0.1.0",
  "profile": "https://secondpasslibrary.local/specs/marginalia-export/0.1.0",
  "generated_at": "2026-07-29T12:00:00Z",
  "generator": "Second Pass Library",
  "scope": { "type": "all" },
  "books": []
}
```

Books with no exported Sessions are omitted.

## Scope

An all-user archive uses:

```json
{ "type": "all" }
```

A selective archive records whether each Book included all or selected
Sessions:

```json
{
  "type": "selected",
  "books": [
    {
      "book": "sha256:<hash>",
      "session_filter": "selected"
    }
  ]
}
```

Single-Book and single-Session mini-archives use the same canonical Book and
Session objects with a `book` or `session` scope. They do not define a different
export profile.

## Book identity

Every exported Book requires `file_hash`, its content identity, normally
`sha256:<hash>`. Scope references use that same value.

Missing hashes are invalid export data and must be repaired upstream. Importers
must not normalize a missing hash into an alternate identity. The archive does
not duplicate the hash in a separate source-identity field.

Descriptive Book fields include title, authors, and optional Series/catalog
context. Sessions are nested under their Book. The schema is strict and does
not permit arbitrary Book metadata.

## Reading Session

A Reading Session contains:

- export-local `export_session_id`
- `name` and `notes`
- `status`: `active` or `closed`
- `started_at`, `closed_at`, `created_at`, and `updated_at`
- `progress`: a located progress object or `null`
- `annotations`

An active Session has `closed_at: null`. A closed Session has a `closed_at`
timestamp.

## Located progress

Progress is a location, not a standalone percentage:

```json
{
  "location": {
    "type": "FragmentSelector",
    "value": "epubcfi(/6/8!/4/2)",
    "locationLabel": "Chapter 08 · 42%"
  },
  "updated_at": "2026-07-29T12:00:00Z"
}
```

Both the CFI and `locationLabel` are required for exported progress. The label
provides the human-readable location; the server does not recreate a percentage
or label by parsing the CFI.

## Annotations and selectors

Deleted annotations are omitted from an export. Exported annotations remain
nested under their Reading Session and do not repeat Book or Session database
identifiers.

The primary EPUB selector may include `locationLabel`:

```json
{
  "type": "FragmentSelector",
  "value": "epubcfi(/6/8!/4/2)",
  "locationLabel": "Chapter 08 · 42% · The Blackstaff"
}
```

`locationLabel` is optional on an annotation only to permit imported historical
records that predate the field. New Reader writes should supply it for every
located highlight and bookmark. A note uses the location of its containing
highlight; it does not define a separate selector.

When quote repair context exists, `target.selector` is an array whose first
item is the primary FragmentSelector:

```json
[
  {
    "type": "FragmentSelector",
    "value": "epubcfi(/6/8!/4/2)",
    "locationLabel": "Chapter 08 · 42%"
  },
  {
    "type": "TextQuoteSelector",
    "exact": "selected text",
    "prefix": "optional preceding context",
    "suffix": "optional following context"
  }
]
```

The quote selector is a repair hint, not annotation content.

Highlight text uses a `TextualBody` with purpose `describing`. An optional note
on that highlight uses purpose `commenting`. A bookmark has an empty body; its
`locationLabel` supplies the human-readable location. Bookmarks do not acquire
note, title, color, or category fields.
