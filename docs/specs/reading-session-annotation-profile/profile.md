# Marginalia Interchange Profile

Version: `0.1.0`

Profile: `https://secondpasslibrary.local/specs/marginalia/0.1.0`

## Scope

This profile defines portable Reading Sessions, progress, locations, highlights,
and bookmarks. Exact fields, types, bounds, required properties, lifecycle
conditions, and annotation variants are normative in [schema.json](schema.json).
This document owns semantic meaning that is awkward or impossible to express in
JSON Schema.

Second Pass Library's general lifecycle, import, and export behavior belongs in
[Marginalia](../../marginalia.md). Visibility and preservation are immutable
policy in [Marginalia-Linked Books](../../marginalia-book-visibility.md). The
archive envelope and Book identity belong in
[Marginalia Export Archive](../marginalia-export.md).

## Session identity and lifecycle

A Reading Session is `active` or `closed`. An active Session has a null
`closedAt`; a closed Session has a date-time `closedAt`. The schema enforces
those conditions. These values describe the source archive lifecycle;
destination import policy may deliberately create historical closed Sessions
as documented in [Marginalia](../../marginalia.md#import-workflow).

`sourceReadingSessionId` is stable and unique across one source archive. It is
used for selection, diagnostics, deterministic packaging, and replay-safe
correlation. It is not a destination database primary key, and the archive does
not expose a local Session UUID through a generic `id` field.

The canonical complete archive demonstrates an active Session. The separate
[closed Session fixture](examples/closed-session.json) exists because its
non-null close time and null progress are materially different conditions.

## Locations and progress

Every located value uses an opaque CFI plus an optional Reader-generated
`locationLabel`. The same pair locates progress, highlights, and bookmarks.
The server stores and transfers these values without parsing, normalizing,
repairing, or deriving them from EPUB content.

`locationLabel` is a display and sorting companion, not an anchor or numeric
progress value. A Reader should keep it stable and lexically sortable in reading
order within one Book and Session. Decorative context may be appended, but the
label is not selected text, a title, a note, or an annotation category.

Progress is the Session's current located state and includes its own update
time. A percentage may appear as Reader-authored display text in
`locationLabel`; there is no canonical numeric progression field. Product list
projections may expose summaries, but those are not interchange fields.

## Annotation semantics

The only annotation kinds are `highlight` and `bookmark`. Each annotation
belongs to one Reading Session and inherits that Session's user and Book
context.

A highlight has a body. Selected `text` and `color` are required. Optional
prefix and suffix contain immediate quote context for Reader-side anchor
verification or repair; an optional note is user-authored prose attached to the
highlight. Supported color tokens are `yellow`, `green`, `blue`, `pink`,
`purple`, and `orange`. There is no standalone note annotation kind and no
second selector/body representation.

A bookmark has no body. It cannot carry selected text, quote context, color, or
a note. Its location label is the only human-readable location companion. The
[invalid bookmark fixture](examples/invalid-bookmark-with-body.json) is retained
specifically to prove this closed-shape rule.

`clientAnnotationId` is a stable Reader-generated identity unique within one
Reading Session. It supports correlation and retry-safe synchronization; it is
not the server's Annotation primary key. Reusing the same identity targets the
same logical annotation, including restoration after a prior soft deletion.

Soft deletion is server state rather than an interchange variant. Deleted
annotations are omitted from archives and authoritative current collections.
Consumers must not invent a portable tombstone shape outside a separately
defined synchronization contract.

## Ordering and replay meaning

Archive arrays are emitted deterministically. Author order is meaningful.
Sessions and annotations use stable runtime ordering so identical archive input
and state render consistently. Annotation reading order prefers nonblank
location labels, then falls back to opaque CFI, creation time, and identity; it
does not claim to reconstruct EPUB spine order.

Portable identities make retries correlatable, but the profile does not define
a cross-server sync protocol. Product-level import replay and duplicate policy
are documented in [Marginalia](../../marginalia.md).

## Compatibility

Consumers must validate against the advertised profile and schema version.
Unknown properties are rejected rather than ignored. Changes to required
fields, bounds, lifecycle conditions, annotation variants, or identity meaning
require coordinated schema, runtime, fixture, and client updates.

The focused specification contract test validates all retained examples and
semantically composes the reusable profile with the archive envelope before
comparing it to the runtime's offline bundled schema. Documentation and runtime
therefore cannot drift silently while preserving their intentionally different
reference layouts.
