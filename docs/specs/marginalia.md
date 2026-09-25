# Marginalia Interchange Contract

Version: `0.1.0`

Profile: `https://secondpasslibrary.local/specs/marginalia/0.1.0`

## Scope and authority

This format-neutral contract defines portable Reading Sessions, progress,
locations, highlights, and bookmarks. Exact fields, types, bounds, required
properties, lifecycle conditions, and annotation variants are normative in
[marginalia.schema.json](marginalia.schema.json). This document owns semantic
rules that JSON Schema cannot express clearly.

The archive envelope and Book identity belong in
[Marginalia Export Archive](marginalia-export.md). Product lifecycle, import,
and export behavior belongs in [Marginalia](../marginalia.md). Visibility and
preservation are immutable policy in
[Marginalia-Linked Books](../marginalia-book-visibility.md).

## Session identity and lifecycle

A Reading Session is `active` or `closed`. An active Session has a null
`closedAt`; a closed Session has a date-time `closedAt`. The schema enforces
those conditions. These values describe the source archive lifecycle;
destination import policy may create historical closed Sessions.

`sourceReadingSessionId` is stable and unique across one source archive. It is
used for selection, diagnostics, deterministic packaging, and replay-safe
correlation. It is not a destination database primary key.

## Locations and progress

`location` is the format-neutral durable anchor. A location string is
self-describing, and its accepted syntax depends on the Book/container format:

- EPUB Books use the supported [`epubcfi(...)` profile](epub-location.md).
- A [`cbz:...` profile](cbz-location.md) is reserved for future CBZ support and
  is not accepted by the current runtime.

Marginalia payloads do not carry a separate `location_type`, `format`, or
`locator_kind`. The Book format and locator syntax provide that information.
One location represents one contiguous target.

Progress has a location, optional `locationLabel`, and update time. Annotation
locations have a location and optional `locationLabel`. The label is opaque
display text, not a navigation, identity, matching, or anchoring field.

### Saved location labels

The live Reader chrome and saved `locationLabel` serve different purposes.
Rendition-only fragments such as `p1/2` must not become durable identity.
Newly generated saved labels use `PPP% - Label`, where `PPP` is a zero-padded
whole-Book percentage from `000` through `100`. The suffix preference is:

1. a useful TOC or section label;
2. `Start` or `End` at the corresponding boundary;
3. a stable ordinal such as `Chapter 08`;
4. `Location`.

Historical labels remain valid opaque display text. Clients and servers must
not migrate, parse, or reinterpret them as identity.

## Annotation semantics

The portable annotation kinds are `highlight` and `bookmark`. Each belongs to
one Reading Session and inherits its Book context.

A highlight has required selected `text` and `color`. Optional `prefix` and
`suffix` retain immediate quote context for client-side recovery or repair;
optional `note` is user-authored prose. These values are annotation metadata,
not parts of the location string. A bookmark has no body.

`clientAnnotationId` is an opaque, nonblank Reader-generated identity unique
within one Reading Session. It supports correlation and retry-safe replay; it
is not a server database key. Soft deletion is server state, not an interchange
variant, so deleted annotations are absent from archives.

## Ordering and replay meaning

Archive arrays are deterministic. Author order is meaningful. Annotation
display order prefers nonblank location labels, then falls back to opaque
location, creation time, and identity. This ordering does not reconstruct a
format-specific reading order.

Portable identities make retries correlatable, but this profile does not
define a cross-server synchronization protocol.

## Compatibility

Consumers must validate the advertised profile and schema version. Unknown
properties are rejected. Changes to required fields, bounds, lifecycle
conditions, annotation variants, or identity meaning require coordinated
schema, runtime, fixture, and client updates.

The focused archive contract test validates retained examples and composes the
documentation schemas before comparing them with the runtime's offline bundle.
