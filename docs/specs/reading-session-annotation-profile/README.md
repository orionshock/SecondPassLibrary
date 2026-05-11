# Reading Session Annotation Profile

This package contains a portable JSON-LD profile for EPUB reading-session annotations.

Project: Second Pass Library

Draft profile id (project-owned placeholder):

```text
https://secondpasslibrary.local/specs/reading-session-annotations/0.1.0
```

## Files

- `profile.md` — human-readable profile
- `context.jsonld` — JSON-LD context for app-specific terms
- `schema.json` — JSON Schema validator (draft)
- `types.ts` — TypeScript helper types (draft)
- `examples/` — example annotations and a full reading-session export (draft)

## Current Implementation (Server)

Second Pass Library currently stores reading data via REST/JSON APIs using W3C-inspired fields (`motivation`, `target`, `body`, `current_location`, `profile_version`).

JSON-LD export/import using this profile is future work and is not implemented yet.

## Recommended Canonical Format (Future Export)

Use W3C Web Annotation JSON-LD as the canonical export format.

Use EPUB CFI as the selector format for EPUB text targets.

## Source Import Metadata (Future)

When importing highlights/notes from external providers (e.g. Kindle CSV exports), attach provenance to each annotation using `sourceImport`.

In the current server implementation, import provenance is reserved for server-managed/internal use and is not accepted via normal public reading APIs.

## Recommended Export Extension (Future)

```text
.reading-session.jsonld
```

## Validation (Future)

Draft export validation lives in `schema.json`.

## Notes

This profile uses `https://secondpasslibrary.local/` as a project-owned placeholder namespace. Replace it if/when Second Pass Library has a real stable documentation namespace.
