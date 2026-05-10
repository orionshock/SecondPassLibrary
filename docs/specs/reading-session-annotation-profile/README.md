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
- `schema.json` — JSON Schema validator
- `types.ts` — TypeScript helper types
- `examples/` — example annotations and a full reading-session export

## Recommended Canonical Format

Use W3C Web Annotation JSON-LD as the canonical server/export format.

Use EPUB CFI as the selector format for EPUB text targets.

## Source Import Metadata (Recommended)

When importing highlights/notes from external providers (e.g. Kindle CSV exports), attach provenance to each annotation using `sourceImport`.

Recommended fields:

- `provider` (e.g. `"kindle"`)
- `location` (provider-specific integer when available)
- `date` (ISO-8601 timestamp)
- `match.method` / `match.confidence` (how the selector was produced)

## Recommended Export Extension

```text
.reading-session.jsonld
```

## Validation

Validate full exports against:

```text
schema.json
```

## Notes

This profile uses `https://secondpasslibrary.local/` as a project-owned placeholder namespace. Replace it if/when Second Pass Library has a real stable documentation namespace.
