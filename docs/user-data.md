# User Reading Data

Second Pass Library stores user reading data server-side in a compact,
reading-session-centered model. The current annotation API still uses a few
W3C/Web Annotation-influenced field names.

This document is design direction for reading sessions, progress, and annotations. The canonical portable exchange profile lives in:

- `docs/specs/marginalia-export.md`
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

Highlights and bookmarks use SPL annotation records with W3C-influenced
motivation names:

- Bookmark: motivation `bookmarking`
- Highlight: motivation `highlighting`
- Highlight with a user note/comment: motivations `["highlighting", "commenting"]`

Standalone comment-only annotations are not part of the current reader workflow and are rejected on create.

Motivation output:

- The server may output `motivation` as an array for product semantics.
- A highlight with a user note/comment is represented as motivations `["highlighting", "commenting"]`.

Annotations point into a publication using an EPUB CFI selector, and are intentionally saved user artifacts.

Internally, annotations are stored in compact/queryable columns:

- `selector_kind` + `selector_value` (currently `epub_cfi`)
- `highlight_text` / `highlight_color`
- `quote_prefix` / `quote_suffix` (optional quote context for highlight repair/export; each <= 500 chars)
- `comment_text`

The current REST API shape still uses `target`/`body` fields and is reconstructed
at the API boundary. The canonical export/import profile is the
session-centered Second Pass Library Marginalia Profile.

Anchor immutability:

- Annotation anchors are creation-time data and are immutable after creation:
  - EPUB CFI selector (`FragmentSelector`)
  - optional quote context (`TextQuoteSelector` exact/prefix/suffix)
  - `session` and `motivation`
- The API allows editing only user-facing content like note/comment text and highlight color tokens.

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

Second Pass Library's current server export/import contract is the canonical
Second Pass Library Marginalia Profile documented in
`docs/specs/marginalia-export.md`.

Server-side marginalia import supports SPL Marginalia Profile files only.
Preview validates and stages the native export with a short-lived import token;
apply imports matched visible books as historical sessions, optionally limited
to selected export-local sessions. The server should not become an importer for
provider-specific formats such as Kindle/Calibre/vendor annotation dumps.

Foreign annotation sources should be normalized outside the server:

- A reader client can convert foreign annotations into normal reading session/progress/annotation API writes.
- An external tool can convert foreign annotations into the SPL Marginalia
  Profile shape for server preview/apply.

## Future possibilities

- Optional provenance (`sourceImport`) for imported annotations/sessions, without changing normal client write semantics.
- Additional export/serialization helpers, without changing the current REST API
  surface unexpectedly.
