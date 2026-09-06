# Marginalia Export Archive

## Scope

This specification defines the portable archive envelope around the reusable
Marginalia objects in the
[Reading Session and Annotation profile](reading-session-annotation-profile/profile.md).
It does not define alternate Session, progress, location, or annotation shapes.

[marginalia-export.schema.json](marginalia-export.schema.json) is the normative
machine-readable envelope schema. It references the normative reusable profile
[schema](reading-session-annotation-profile/schema.json) by its canonical URI.
The runtime keeps an offline bundled schema beside the archive codec; the
focused contract test composes these two documentation schemas and checks their
semantic parity with that runtime bundle.

The complete valid end-to-end fixture is
[complete-export.json](reading-session-annotation-profile/examples/complete-export.json).
It is validated offline against both documentation schemas and accepted by the
runtime codec during the focused specification check.

## Version and profile

The current envelope version is `0.1.0`, with profile URI:

```text
https://secondpasslibrary.local/specs/marginalia/0.1.0
```

`type`, `schemaVersion`, and `profile` identify this exact contract. Consumers
must not guess at compatibility when one differs. The schema rejects unknown
envelope, Book, Session, progress, location, body, and annotation properties.

## Book identity and review metadata

`fileHash` is the sole portable Book identity. It has the form
`sha256:<lowercase hex>` and is the SHA-256 checksum of the exact uploaded EPUB
bytes, calculated before EPUB parsing and stored on the Library Book. Export
serializes that stored checksum without hashing metadata, extracted files, or a
repacked archive. Locations and quote context belong to those exact bytes. A
hash is unique across one archive. Second Pass Library exports always include
it and reject export when the Book lacks a usable checksum. Import accepts an
entry with no `fileHash` only as an Unmatched Book; absence is never an
instruction to infer identity from metadata. Duplicate supplied hashes remain
an archive integrity failure.

Import checks `fileHash` before any other Book data and has no metadata-only
matching path. A different checksum remains Unmatched even when title, ordered
Author names, ISBN, EPUB UID, Calibre ID, or other metadata describe the same
bibliographic work. Title and ordered Author names are bounded review metadata;
they do not replace the hash. The archive contains no local Book UUID, storage
or download data, permission state, Groups, or Shelves.

## Archive semantics

Complete and selected exports use the same envelope and do not carry a scope
flag. Sessions without non-deleted annotations are excluded by default; the
explicit include-empty option changes which Sessions are present, not their
shape. Deleted annotations are omitted.

Native import consumes this contract. Foreign formats must be converted by a
Reader client or dedicated tool; the Library server does not parse EPUB content,
repair CFIs, or invent location labels while importing Marginalia.

The Unmatched download is a ZIP packaging operation, not another schema. Each
JSON member is a complete single-Session archive conforming to this same
envelope and reusable profile.

Product lifecycle, staged import, replay, and export-limit behavior belong in
[Marginalia](../marginalia.md). Visibility and preservation are immutable policy
in [Marginalia-Linked Books](../marginalia-book-visibility.md), not this
interchange specification.
