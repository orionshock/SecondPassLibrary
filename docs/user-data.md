# User Reading Data

Second Pass Library stores user reading data server-side in a W3C Web Annotation-inspired shape.

This document is design direction for reading sessions, progress, and annotations. The canonical draft profile lives in:

- `docs/specs/reading-session-annotation-profile/`
  - Current profile version: `0.1.0`

For practical current REST payload examples for reader-client development, see:

- `docs/reading-rest-examples.md`

## Position

- Reader clients must adapt to the server format if they want to save user data.
- The server does not maintain per-reader proprietary annotation formats.
- Public reading payloads are versioned via `profile_version` and unknown/unsupported fields are rejected.
- Reading payloads are also size-limited as a coarse abuse guard (the server is not arbitrary client blob storage).
- For REST clients, `POST /api/v1/reading/annotations/` supports optional `Idempotency-Key` (recommended) so clients can safely retry create requests without duplicating annotations.
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

Internally, annotations are stored in compact/queryable columns:

- `selector_kind` + `selector_value` (currently `epub_cfi`)
- `highlight_text` / `highlight_color`
- `quote_prefix` / `quote_suffix` (optional quote context for highlight repair/export; each <= 500 chars)
- `comment_text`

The API/export shape remains W3C-ish (`target`/`body`) and is reconstructed at the boundary.

Highlight color:

- `highlight_color` is a semantic token (not a CSS/hex color string).
- Allowed values: `yellow`, `green`, `blue`, `pink`, `purple`, `orange`.
- Color is highlight/quote-only metadata (it applies to the selected-text `TextualBody` with `purpose: "describing"`).
- Note/comment bodies and bookmark-only annotations do not use color.
- For highlight annotations, missing/blank color defaults to `yellow`.

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

## Future possibilities

- JSON-LD export/import of `.reading-session.jsonld` in an `AnnotationCollection` shape.
- Optional provenance (`sourceImport`) for imported annotations/sessions, without changing normal client write semantics.
- Additional W3C-style serialization helpers, without changing the current REST API surface unexpectedly.
