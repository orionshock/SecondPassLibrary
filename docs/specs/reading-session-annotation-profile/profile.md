# Draft Reading Session Annotation Profile

Version: 0.1.0
Status: Draft / historical / non-canonical
Influence: W3C Web Annotation Data Model
Primary serialization explored here: JSON-LD
Primary ebook target: EPUB
Primary selector: EPUB CFI FragmentSelector

Profile id (project-owned placeholder):

```text
https://secondpasslibrary.local/specs/reading-session-annotations/0.1.0
```

## Purpose

This draft records portable annotation-shape exploration for a personal EPUB
reading system. It is not the canonical Second Pass Library Marginalia Profile.

Second Pass Library note:

- The canonical server import/export contract is the Second Pass Library
  Marginalia Profile documented in `../marginalia-export.md`.
- The current server implementation stores a strict W3C-inspired subset via
  REST/JSON, but W3C/Web Annotation is an influence only.
- Server-side marginalia import preview supports SPL Marginalia Profile files
  only, not arbitrary foreign/provider-specific formats.
- The current server implementation does not support cross-session annotation promotion/linking (`derivedFrom` / `sourceSession`). If a user re-highlights in a later session, it is stored as a separate annotation.

It represents:

- reading sessions
- highlights
- notes
- bookmarks
- current reading location
- book metadata
- immutable previous sessions
- read-only layered previous sessions
- promoted annotations derived from older sessions (future)

The goal is to keep the application data model portable without tying it to a specific EPUB renderer such as epub.js.

## Core Concepts

### Book

A book is identified primarily by a stable file hash when available.

Recommended book identifier:

```text
book:sha256:<hash>
```

Book metadata is included at the collection/session level, not repeated in every annotation.

### Reading Session

A reading session represents one pass or relationship with a book.

Rules:

- A user may have one active session per book.
- Closed sessions are immutable.
- Closed sessions cannot be reopened.
- A new session may layer previous sessions as read-only overlays.
- Cross-session promotion/linking is future profile direction and is not implemented on the server today.

### Annotation

Annotations use a small SPL-owned shape influenced by W3C Web Annotation terms.
This draft should not be read as a W3C compliance target.

Supported motivations:

- `highlighting`
- `commenting`
- `bookmarking`

Motivation cardinality:

- `motivation` MAY be a string or an array of strings.
- For product semantics, highlights with a user note/comment SHOULD use motivations:
  - `["highlighting", "commenting"]`
- Plain highlights SHOULD use `["highlighting"]`.
- Bookmarks SHOULD use `["bookmarking"]`.

Highlight color:

- `color` is highlight/quote-only metadata (not generic annotation metadata).
- It applies only to selected text / quote bodies represented as `TextualBody` with:
  - `purpose: "describing"`
- Note/comment bodies (`purpose: "commenting"`) do not use `color`.
- Bookmark-only annotations do not use `color`.
- Allowed values: `yellow`, `green`, `blue`, `pink`, `purple`, `orange`.
- If omitted or blank on highlight input, it normalizes to `yellow`.
- Normalized output/export highlight bodies should include a real token (no blank values).

Future / v2 consideration:

- A future profile version may introduce a generic `annotation_color` that can apply to highlights, and bookmarks.
- That is intentionally not part of this profile version.

### Targeting EPUB Content

Every EPUB annotation target should use an EPUB CFI `FragmentSelector` as the primary anchor.

Required primary selector shape:

```json
{
  "type": "FragmentSelector",
  "conformsTo": "http://www.idpf.org/epub/linking/cfi/epub-cfi.html",
  "value": "epubcfi(...)"
}
```

Optional quote context (repair/export hint):

- Implementations may also provide `TextQuoteSelector`-style quote context.
- This is intended to help re-anchor highlights when a CFI fails (different file, different CFI, or minor content shifts).
- The EPUB CFI `FragmentSelector` remains the source of truth for exact positioning when it works.

When quote context is present, `target.selector` MAY be an array:

1. EPUB CFI `FragmentSelector` (required; first)
2. `TextQuoteSelector` (optional; second)

`TextQuoteSelector` shape:

```json
{
  "type": "TextQuoteSelector",
  "exact": "selected text",
  "prefix": "optional preceding context",
  "suffix": "optional following context"
}
```

If both are provided, `TextQuoteSelector.exact` SHOULD match the highlight describing body text (`body[].purpose="describing"` value).

Client guidance:

- Clients SHOULD send only nearby text immediately before/after the selected text.
- Quote context is anchoring/repair/export metadata, not display content.
- Clients MAY adapt context length based on the selected text:
  - Short selections may need more surrounding context.
  - Long distinctive selections may need little or no surrounding context.
- The server enforces shape and size limits only (it does not evaluate anchoring quality).
- Maximum lengths: `prefix` <= 500 characters, `suffix` <= 500 characters.

Page numbers should not be used as durable anchors.

### Current Reading Location

Current reading location is stored as session state, not as a W3C Annotation.

Recommended shape:

```json
{
  "type": "FragmentSelector",
  "conformsTo": "http://www.idpf.org/epub/linking/cfi/epub-cfi.html",
  "value": "epubcfi(...)",
  "updated": "2026-05-10T12:00:00Z"
}
```

### Layering Sessions (Future)

Layered sessions are referenced by ID.

Layered annotations are read-only overlays.

The active session owns only its own annotations.

### Promoting Old Annotations (Future)

When/if a previous annotation is promoted into a current session in the future, create a new annotation and point to the old one:

```json
{
  "derivedFrom": "urn:uuid:old-annotation-id"
}
```

The old annotation remains immutable.

## Export And Import Policy

The implemented server export/import format is the canonical Second Pass Library
Marginalia Profile, not this draft JSON-LD profile. See
`../marginalia-export.md`.

Server-side marginalia import supports SPL Marginalia Profile files only.
Preview validates and stages the native export with a short-lived import token;
apply imports matched visible books as historical sessions, optionally limited
to selected export-local sessions.

Foreign/provider-specific formats should be normalized outside the server:

- A reader client can convert foreign annotations into normal reading session/progress/annotation API writes.
- An external tool can convert foreign annotations into the SPL Marginalia
  Profile shape before server import.

JSON-LD serialization may remain useful for interoperability experiments, but it
is not the server import/export contract.

## Draft JSON-LD Collection Fields

- `@context`
- `id`
- `type`
- `profile`
- `schemaVersion`
- `generated`
- `generator`
- `book`
- `session`
- `items`

## Draft JSON-LD Book Metadata

- `id`
- `title`
- `subtitle`
- `author`
- `publisher`
- `publishedDate`
- `language`
- `isbn`
- `fileHash`
- `epubUniqueIdentifier`

## Import Matching Policy

For tools that convert external data into SPL Marginalia Profile files,
recommended matching order is:

1. Exact `fileHash`
2. EPUB unique identifier
3. ISBN
4. Title + author soft match
5. Manual user confirmation

The application should not repair or mutate EPUB files during import.

## EPUB File Policy

The user is responsible for providing a valid, DRM-free EPUB.

The application may:

- validate shallowly
- extract metadata
- calculate file hash
- render the EPUB
- store annotations and reading state

The application should not:

- repair broken EPUB structure
- normalize the EPUB file itself
- remove DRM
- rewrite OPF/package files
- convert other ebook formats into EPUB

## Application-Specific Terms

This draft adds a small number of JSON-LD terms:

- `ReadingSession`
- `session`
- `sessionId`
- `sessionStatus`
- `currentLocation`
- `layeredSession`
- `book`
- `fileHash`
- `epubUniqueIdentifier`
- `schemaVersion`
- `profile`
- `sourceImport` (future)

These terms are defined in `context.jsonld`.

## Source Import Metadata (Future)

When annotations originate from an external provider, provenance may be useful in a future server-managed import flow. It is not accepted through the current public reading APIs.

Recommended shape:

```json
{
  "sourceImport": {
    "provider": "kindle",
    "location": 557,
    "date": "2025-10-28T00:00:00Z",
    "title": "Battle Ground",
    "author": "Jim Butcher",
    "url": "https://read.amazon.com/notebook?...",
    "match": {
      "method": "text-search-to-epub-cfi",
      "confidence": 1.0
    }
  }
}
```

Notes:
- `date` should be an ISO-8601 timestamp (UTC recommended).
- `confidence` is implementation-defined but should be in the range `0.0` to `1.0`.

## Non-Canonical Notes

This draft keeps W3C/Web Annotation concepts visible because they informed the
early annotation vocabulary.

A renderer such as epub.js should be treated as an implementation detail. The
canonical server exchange format is the session-centered Second Pass Library
Marginalia Profile, where books contain sessions, sessions contain progress and
annotations, annotations inherit book/session context from nesting, annotations
belong to reading sessions, and marginalia belongs to the user.
