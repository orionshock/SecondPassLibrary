# Marginalia Export Archive

This file defines only the portable archive envelope around the canonical
Marginalia objects in
[`reading-session-annotation-profile/profile.md`](reading-session-annotation-profile/profile.md).
It does not define alternate Session, progress, location, highlight, or bookmark
shapes.

Canonical profile URI:

```text
https://secondpasslibrary.local/specs/marginalia/0.1.0
```

The documentation schema is
[`marginalia-export.schema.json`](marginalia-export.schema.json). It references
the shared Reading Session definition from the canonical profile. A complete
example is
[`reading-session-annotation-profile/examples/complete-export.json`](reading-session-annotation-profile/examples/complete-export.json).

Files under `docs/` are documentation only. Runtime validators belong beside
the code that consumes them.

## Envelope

```json
{
  "type": "SecondPassMarginaliaExport",
  "schema_version": "0.1.0",
  "profile": "https://secondpasslibrary.local/specs/marginalia/0.1.0",
  "generated_at": "2026-07-29T12:00:00Z",
  "generator": "Second Pass Library",
  "scope": { "type": "all" },
  "books": []
}
```

The envelope is export-only. It records the generating application, archive
scope, and Books needed to interpret the nested canonical Sessions.

## Scope

Complete archive:

```json
{ "type": "all" }
```

Selective archive:

```json
{
  "type": "selected",
  "books": [
    {
      "book": "secondpass:book:7152f4b8-ad35-4dd6-9e40-8ae68678e76e",
      "session_filter": "selected"
    }
  ]
}
```

Single-Book and single-Session archives use `book` and `session` scopes. They
contain the same Book and Reading Session shapes as a complete archive.

## Book envelope

Every exported Book requires both:

- `source`: the source-system Book identity used by archive scope and tooling.
- `file_hash`: the exact EPUB content identity, formatted as
  `sha256:<64 hexadecimal characters>`.

The values have distinct jobs. `source` identifies the Book record in its
source system; `file_hash` identifies the bytes against which CFIs and quote
context were created. A missing file hash is invalid archive data and must be
fixed upstream.

Book metadata is descriptive. Sessions are nested once under the Book and use
the canonical shared Session shape unchanged. Annotations do not repeat Book
identity.

## Import boundary

Native import consumes this envelope and the canonical Marginalia objects.
Foreign formats must be converted by a Reader client or dedicated tool. The
Library server does not parse EPUB content to repair CFIs or produce
`locationLabel` values during normal import.

## Packaging

A complete or selected archive is a JSON attachment. Workflows that split
unmatched Sessions may package one complete single-Session archive per JSON
file inside a ZIP; the contained JSON still uses this envelope and canonical
Session shape.
