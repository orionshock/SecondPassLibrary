# Reading Session Annotation Profile

This package contains a draft portable JSON-LD profile for EPUB reading-session annotations.

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

Second Pass Library currently stores reading data via REST/JSON APIs using W3C-inspired fields (`motivation`, `target`, `body`, `current_location`, `profile_version`).

The current server export contract is the SPL nested marginalia format in `../marginalia-export.md`. JSON-LD serialization using this profile is not the current server import/export contract.

## Server Import Policy

Server-side marginalia import supports SPL native marginalia exports only. Preview validates and stages the native export with a short-lived import token; apply imports matched visible books as historical sessions, optionally limited to selected export-local sessions.

Foreign/provider-specific formats should be normalized by a client and sent through the normal reading APIs, or converted by an external tool into SPL native marginalia export format before server import.

## Annotation Shape Direction

Use W3C Web Annotation concepts for annotation shape.

Use EPUB CFI as the selector format for EPUB text targets.

## Source Import Metadata (Future)

Future/profile-level direction: when highlights/notes are normalized from external providers (e.g. Kindle CSV exports) into portable profile documents, provenance may be attached to each annotation using `sourceImport`.

In the current server implementation, import provenance is reserved for server-managed/internal use and is not accepted via normal public reading APIs.

## Validation

Draft profile validation lives in `schema.json`.

## Notes

This profile uses `https://secondpasslibrary.local/` as a project-owned placeholder namespace. Replace it if/when Second Pass Library has a real stable documentation namespace.
