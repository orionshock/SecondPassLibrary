# Draft Reading Session Annotation Profile

This package contains historical/draft JSON-LD exploration for EPUB
reading-session annotations. It is not the canonical Second Pass Library
Marginalia Profile.

Project: Second Pass Library

Draft profile id (project-owned placeholder):

```text
https://secondpasslibrary.local/specs/reading-session-annotations/0.1.0
```

## Files

- `profile.md` - human-readable profile
- `context.jsonld` - JSON-LD context for app-specific terms
- `schema.json` - JSON Schema validator (draft)
- `types.ts` - TypeScript helper types (draft)
- `examples/` - example annotations and a full reading-session export (draft)

## Current Implementation (Server)

Second Pass Library currently stores reading data in a compact
reading-session-centered model. The live annotation REST API uses SPL-native
fields such as `kind`, `selector`, `quote`, `highlight_text`,
`highlight_color`, and `comment_text`; it does not use this draft JSON-LD
shape.

The canonical server import/export contract is the Second Pass Library
Marginalia Profile in `../marginalia-export.md`. JSON-LD serialization using
this draft profile is not the current server import/export contract.

## Server Import Policy

Server-side marginalia import supports Second Pass Library Marginalia Profile
files only. Preview validates and stages the native export with a short-lived
import token; apply imports matched visible books as historical sessions,
optionally limited to selected export-local sessions.

Foreign/provider-specific formats should be normalized by a client and sent
through the normal reading APIs, or converted by an external tool into the SPL
Marginalia Profile before server import.

## Annotation Shape Direction

W3C Web Annotation concepts may influence annotation shape, but Second Pass
Library is not targeting W3C compliance.

Use EPUB CFI as the selector format for EPUB text targets.

## Source Import Metadata (Future)

Future/profile-level direction: when highlights/notes are normalized from external providers (e.g. Kindle CSV exports) into portable profile documents, provenance may be attached to each annotation using `sourceImport`.

In the current server implementation, import provenance is reserved for server-managed/internal use and is not accepted via normal public reading APIs.

## Validation

Draft JSON-LD profile validation lives in `schema.json`. It does not validate
the canonical SPL Marginalia Profile.

## Notes

This profile uses `https://secondpasslibrary.local/` as a project-owned placeholder namespace. Replace it if/when Second Pass Library has a real stable documentation namespace.
