# Marginalia Export Archive

This file defines the portable archive envelope around the canonical
Marginalia objects in
[`reading-session-annotation-profile/profile.md`](reading-session-annotation-profile/profile.md).
It does not define alternate Session, progress, location, highlight, or
bookmark shapes.

Canonical profile URI:

```text
https://secondpasslibrary.local/specs/marginalia/0.1.0
```

The documentation schema is
[`marginalia-export.schema.json`](marginalia-export.schema.json). A complete
example is
[`reading-session-annotation-profile/examples/complete-export.json`](reading-session-annotation-profile/examples/complete-export.json).
Files under `docs/` are documentation only. The executable schema lives beside
the runtime archive codec and neither runtime code nor tests load this copy.

## Envelope

```json
{
  "type": "SecondPassMarginaliaExport",
  "schemaVersion": "0.1.0",
  "profile": "https://secondpasslibrary.local/specs/marginalia/0.1.0",
  "generatedAt": "2026-07-29T12:00:00Z",
  "generator": "Second Pass Library",
  "scope": { "type": "all" },
  "books": []
}
```

`scope.type` is `all` or `selected`. The contained Books and Sessions are the
authoritative description of a selected archive, so scope does not duplicate
their identities.

## Book envelope

```json
{
  "fileHash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "title": "The Example Book",
  "authors": ["Example Author"],
  "readingSessions": []
}
```

`fileHash` is the sole portable Book identity. It is the exact EPUB content
checksum and is required because locations and quote context belong to those
bytes. A missing hash is an export data-integrity failure. Distinct Books with
the same hash are a Library integrity failure and must not be merged.

Title and authors are bounded review metadata only. They are not matching
fallbacks. The archive contains no source-system Book id, storage or download
data, permission state, Groups, or Shelves.

## Import and export policy

Sessions with no non-deleted Annotations are excluded by default. Import and
export workflows expose an explicit `Include empty sessions` option without
changing the archive object shapes.

Native import consumes this envelope and the canonical Marginalia objects.
Foreign formats must be converted by a Reader client or dedicated tool. The
Library server does not parse EPUB content, repair CFIs, or produce
`locationLabel` values.

A complete or selected archive is a JSON attachment. A future unmatched
workflow may package one complete single-Session archive per JSON file inside
a ZIP; each contained JSON document uses this same envelope and contract.
