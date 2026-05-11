# User Reading Data

Second Pass Library stores user reading data server-side in a W3C Web Annotation-inspired shape.

This document is design direction for reading sessions, progress, and annotations. The canonical draft profile lives in:

- `docs/specs/reading-session-annotation-profile/`
  - Current profile version: `0.1.0`

## Position

- Reader clients must adapt to the server format if they want to save user data.
- The server does not maintain per-reader proprietary annotation formats.
- Public reading payloads are versioned via `profile_version` and unknown/unsupported fields are rejected.
- Reading payloads are also size-limited as a coarse abuse guard (the server is not arbitrary client blob storage).
- EPUB is the current target format.
- EPUB CFI (`FragmentSelector`) is the primary selector for text targets.
- The app does not repair, normalize, or beautify user-provided EPUB files.

## Data Types

### Annotations (highlights, notes, bookmarks)

Highlights, notes, and bookmarks are treated as W3C Annotations:

- Highlight: motivation `highlighting`
- Note: motivation `commenting`
- Bookmark: motivation `bookmarking`

Annotations point into a publication using an EPUB CFI selector, and are intentionally saved user artifacts.

### Current reading location vs bookmarks

- Current reading location is mutable **ReadingSession state**, not necessarily an Annotation.
- A bookmark is an intentionally saved Annotation.
- Both point into a publication, but they have different lifecycle rules and intent.

### Sessions

- A user may have one active session per book.
- Closed sessions are immutable (not reopened/mutated).
- New sessions may layer previous sessions as read-only overlays.
- There is no cross-session annotation promotion/linking in the current implementation. Re-highlighting in a new session creates a separate annotation.

### Ownership and durability

- Reading data remains owned by the user even if current book access changes later.
- The library access model may evolve, but user-owned reading metadata should remain recoverable and exportable by its owner.

## Export/import direction

Second Pass Library's interoperability direction is JSON-LD exports in an `AnnotationCollection` shape.

The current draft export extension is:

```text
.reading-session.jsonld
```

## Future implementation notes

### Phase 1 (docs + mapping)

- Document the profile and treat it as canonical direction.
- Map current ReadingSession/Annotation/ReadingProgress models to the profile concepts.
- Add helpers for W3C-style serialization without breaking the current reading API.

### Phase 2 (API alignment)

- Adjust model fields if needed to better represent the profile semantics.
- Expose W3C-style read/write APIs for reading data.
- Preserve unknown fields where practical on future import/export paths (round-trip external imports without data loss). The current public reading APIs reject unknown fields.

### Phase 3 (portability)

- Add export/import of `.reading-session.jsonld`.
- Add `sourceImport` provenance for external imports (e.g. Kindle exports).
