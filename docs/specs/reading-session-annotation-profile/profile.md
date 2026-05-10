# Reading Session Annotation Profile

Version: 0.1.0  
Status: Draft  
Base model: W3C Web Annotation Data Model  
Primary serialization: JSON-LD  
Primary ebook target: EPUB  
Primary selector: EPUB CFI FragmentSelector

Profile id (project-owned placeholder):

```text
https://secondpasslibrary.local/specs/reading-session-annotations/0.1.0
```

## Purpose

This profile defines a portable annotation/export format for a personal EPUB reading system.

It represents:

- reading sessions
- highlights
- notes
- bookmarks
- current reading location
- book metadata
- immutable previous sessions
- read-only layered previous sessions
- promoted annotations derived from older sessions

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
- An annotation from an older session may be promoted into the current session by creating a new annotation with `derivedFrom`.

### Annotation

Annotations use the W3C Web Annotation Data Model.

Supported motivations:

- `highlighting`
- `commenting`
- `bookmarking`

### Targeting EPUB Content

Every EPUB annotation target should use a `FragmentSelector` whose value is an EPUB CFI.

Required selector shape:

```json
{
  "type": "FragmentSelector",
  "conformsTo": "http://www.idpf.org/epub/linking/cfi/epub-cfi.html",
  "value": "epubcfi(...)"
}
```

Page numbers should not be used as durable anchors.

### Current Reading Location

Current reading location is stored as session state, not as a W3C Annotation, unless an implementation intentionally wants a fully uniform annotation-only model.

Recommended shape:

```json
{
  "type": "FragmentSelector",
  "conformsTo": "http://www.idpf.org/epub/linking/cfi/epub-cfi.html",
  "value": "epubcfi(...)",
  "updated": "2026-05-10T12:00:00Z"
}
```

### Layering Sessions

Layered sessions are referenced by ID.

Layered annotations are read-only overlays.

The active session owns only its own annotations.

### Promoting Old Annotations

When a previous annotation is promoted into the current session, create a new annotation and point to the old one:

```json
{
  "derivedFrom": "urn:uuid:old-annotation-id"
}
```

The old annotation remains immutable.

## Export Format

The recommended export format is a JSON-LD `AnnotationCollection` with profile-specific metadata.

Recommended file extension:

```text
.reading-session.jsonld
```

Recommended media type:

```text
application/ld+json
```

## Required Export-Level Fields

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

## Recommended Book Metadata

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

Recommended matching order:

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

This profile adds a small number of JSON-LD terms:

- `ReadingSession`
- `session`
- `sessionId`
- `sessionStatus`
- `currentLocation`
- `layeredSession`
- `derivedFrom`
- `book`
- `fileHash`
- `epubUniqueIdentifier`
- `schemaVersion`
- `profile`
- `sourceImport`

These terms are defined in `context.jsonld`.

## Source Import Metadata (Recommended)

When annotations originate from an external provider (such as a Kindle export), store import provenance on the annotation.

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

## Compatibility Notes

This profile is designed to be compatible with W3C Web Annotation while remaining practical for an EPUB reader application.

A renderer such as epub.js should be treated as an implementation detail. The canonical server and export representation should remain W3C-compatible JSON-LD.
