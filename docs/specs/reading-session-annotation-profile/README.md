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

## Historical implementation context

Second Pass Library stores Marginalia in a Reading-Session-centered model. Live
Marginalia and Reader-client APIs use SPL-native fields; they do not use this
draft JSON-LD shape.

The new Marginalia domain foundation stores an optional `location_label`
beside the CFI on Session progress and annotations. In this draft JSON-LD
profile, the equivalent application term is `locationLabel` on the primary
EPUB CFI selector.

The canonical server import/export contract is the Second Pass Library
Marginalia Profile in `../marginalia-export.md`. JSON-LD serialization using
this draft profile is not the current server import/export contract.

## Archive boundary

The canonical Marginalia archive is the supported native interchange shape.
This historical JSON-LD profile is not an alternate import shape.

Foreign/provider-specific formats should be normalized by a Reader client into
live Marginalia writes, or converted by an external tool into the canonical
Marginalia archive before import.

## Annotation Shape Direction

W3C Web Annotation concepts may influence annotation shape, but Second Pass
Library is not targeting W3C compliance.

Use EPUB CFI as the selector format for EPUB text targets.

`locationLabel` is an optional Reader-generated display and sorting companion
to that CFI. It is opaque, bounded text and is not part of the CFI itself.

## Source Import Metadata (Future)

Future/profile-level direction: when highlights/notes are normalized from external providers (e.g. Kindle CSV exports) into portable profile documents, provenance may be attached to each annotation using `sourceImport`.

Import provenance is reserved for server-managed/internal use and is not a
normal public Marginalia field.

## Validation

Draft JSON-LD profile validation lives in `schema.json`. It does not validate
the canonical SPL Marginalia Profile.

## Notes

This profile uses `https://secondpasslibrary.local/` as a project-owned placeholder namespace. Replace it if/when Second Pass Library has a real stable documentation namespace.
