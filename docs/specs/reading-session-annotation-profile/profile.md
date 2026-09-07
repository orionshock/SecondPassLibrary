# Marginalia Interchange Profile

Version: `0.1.0`

Profile: `https://secondpasslibrary.local/specs/marginalia/0.1.0`

## Scope

This profile defines portable Reading Sessions, progress, locations, highlights,
and bookmarks. Exact fields, types, bounds, required properties, lifecycle
conditions, and annotation variants are normative in [schema.json](schema.json).
This document explains semantic rules that are awkward or impossible to express
in JSON Schema.

Second Pass Library's general lifecycle, import, and export behavior belongs in
[Marginalia](../../marginalia.md). Visibility and preservation are immutable
policy in [Marginalia-Linked Books](../../marginalia-book-visibility.md). The
archive envelope and Book identity belong in
[Marginalia Export Archive](../marginalia-export.md).

## Session identity and lifecycle

A Reading Session is `active` or `closed`. An active Session has a null
`closedAt`; a closed Session has a date-time `closedAt`. The schema enforces
those conditions. These values describe the source archive lifecycle;
destination import policy may create historical closed Sessions
as documented in [Marginalia](../../marginalia.md#import-workflow).

`sourceReadingSessionId` is stable and unique across one source archive. It is
used for selection, diagnostics, deterministic packaging, and replay-safe
correlation. It is not a destination database primary key, and the archive does
not expose a local Session UUID through a generic `id` field.

The complete archive demonstrates an active Session. The separate
[closed Session fixture](examples/closed-session.json) exists because its
non-null close time and null progress are materially different conditions.

## Locations and progress

Every saved location uses an opaque CFI and may include a Reader-generated
`locationLabel`. Progress, highlights, and bookmarks all use this pair. The CFI
is the durable anchor. The label is persisted display text and must not be used
for navigation, identity, Book or Session matching, or annotation anchoring.

The server stores and transfers both values without parsing, normalizing,
repairing, or deriving them from EPUB content. Progress also carries its own
update time. Product list responses may include summaries, but those are not
interchange fields.

### Saved location labels

The live Reader chrome and a saved `locationLabel` serve different purposes.
While a Book is open, the Reader may show transient rendition context such as
`Dedication • p1/2 • 1%`. The page fragment applies only to that live rendition
and must not be persisted as location identity.

Newly generated saved labels use this form:

```text
PPP% - Label
```

`PPP` is the zero-padded whole-Book percentage from `000` through `100`. The
suffix is chosen in this order:

1. a useful TOC or section label, when available;
2. `Start` or `End` at the corresponding Book boundary;
3. a stable spine ordinal such as `Chapter 08`;
4. `Location`.

Examples:

- `000% - Start`
- `001% - Dedication`
- `003% - PROLOGUE`
- `014% - Chapter 08`
- `042% - Location`
- `099% - End`
- `100% - End`

Saved labels must not contain rendition page fragments such as `p1/2`, spine
hrefs, raw CFIs, Session IDs, or timestamps. Those values are transient
rendering details, machine anchors, or unrelated metadata.

Historical labels remain valid. A value such as `Chapter 08 - 01%` is still
opaque display text and must not be migrated, parsed, or reformatted
automatically. Clients and servers must accept both historical values and the
new `PPP% - Label` style without treating either form as identity.

Second Pass Library currently uses a nonblank label as the first lexical sort
key for annotation display, followed by CFI, creation time, and stable identity.
This compares the entire string; it does not parse the percentage or infer EPUB
position. There is no canonical numeric progression field.

## Annotation semantics

The only annotation kinds are `highlight` and `bookmark`. Each annotation
belongs to one Reading Session and inherits that Session's user and Book
context.

A highlight has a body. Selected `text` and `color` are required. Optional
prefix and suffix contain immediate quote context for Reader-side anchor
verification or repair; an optional note is user-authored prose attached to the
highlight. They are not selected text and must not be concatenated into the
visible quotation. Supported color tokens are `yellow`, `green`, `blue`, `pink`,
`purple`, and `orange`. There is no standalone note annotation kind and no
second selector/body representation.

A bookmark has no body. It cannot carry selected text, quote context, color, or
a note. Its location label is the only human-readable location companion. The
[invalid bookmark fixture](examples/invalid-bookmark-with-body.json) is retained
specifically to prove this closed-shape rule.

`clientAnnotationId` is a stable Reader-generated identity unique within one
Reading Session. It supports correlation and retry-safe synchronization; it is
not the server's Annotation primary key. It is an opaque, nonblank string of at
most 255 characters rather than a UUID-typed field, although Readers should
normally generate a UUID v4. Reusing the same identity within one Session
targets the same logical annotation, including restoration after a prior soft
deletion. The same value may be used in another Session without collision.

Soft deletion is server state rather than an interchange variant. Deleted
annotations are omitted from archives and current collections.
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
