# API conventions

## Scope

`/api/v1/` is the active versioned JSON API namespace. Public discovery at
`/.well-known/secondpass` is the deliberate exception because it advertises the
API root to external clients.

This document owns shared HTTP conventions and stable external boundaries. It
is not a route or field catalog. Active URL configuration and serializers are
authoritative for exact endpoint methods, query parameters, and wire fields;
the first-party SDK types and adapters are authoritative for the Product UI's
application-facing shapes. Normative Marginalia schemas own their interchange
formats.

The default DRF renderer is JSON only. Product UI transport may evolve together
with the SDK before release and should not be copied into prose merely because
it exists today.

## Authentication modes

The API has two authenticated boundaries:

- Django session authentication is the browser Product UI authority. Unsafe
  methods require Django CSRF protection; the SDK sends same-origin credentials
  and the CSRF header.
- Client API bearer authentication is opt-in on explicitly supported external
  Reader endpoints. It is narrower than browser authority: an account role does
  not turn a bearer credential into an unrestricted management credential.

Session authentication is the default. A view must opt into bearer
authentication deliberately, then apply its normal role, ownership, and object
visibility rules. Within the API/discovery boundary, anonymous access is an
explicit exception used for bounded readiness/discovery and the
capability-based portions of Reader pairing. Public cover delivery and retained
browser pages are separate HTTP surfaces. HTTP Basic authentication is not part
of the product contract.

Inactive users are rejected at both authenticated boundaries. Server-side
`must_change_password` enforcement applies to session-authenticated browser
users; blocked API calls return JSON rather than redirecting to an HTML page.
Browser-session and forced-password policy is documented in
[Architecture](architecture.md#browser-sessions-and-forced-password-changes).
Pairing, bearer lifetime, revocation, and the external Reader allow-list belong
in [Client API authorization](client-api-auth.md).

Cross-origin requests are allowed for `/api/` and `/.well-known/` without
credentials so independent browser Reader clients can use bearer tokens. The
same-origin Product UI uses session cookies and is not a credentialed CORS
application. Enabling cross-origin cookies would require a separate security
design.

## Request conventions

JSON is the normal request format. Upload endpoints explicitly use multipart
forms, and attachment responses are binary or JSON documents with their own
media types. Callers must not infer a request format from a neighboring route.

Wire names use Django/DRF `snake_case`. UUID identities are treated as opaque
strings and validated before use. A malformed UUID in a query or body normally
produces a field-level `400`; a malformed path identity may fail URL matching
and receive the API's JSON `404`. Public profile UUIDs, rather than Django auth
database IDs, identify users in externally visible relationships.

Mutation serializers with a closed input shape reject unknown fields. This is
especially important for account, catalog, Group, Shelf, and Marginalia writes:
read-only or privileged-looking fields must not be silently accepted. The exact
allowed fields remain serializer-owned, because not every read serializer or
framework endpoint has the same shape.

Ordering, filtering, and search selectors are explicit allow-lists. Client
values must never be interpolated as arbitrary ORM field names or SQL
structure. Bulk and selected-ID operations impose operation-specific item
limits before expensive queries or serialization; those limits belong in the
relevant domain contract. Idempotency keys and replay fingerprints are likewise
operation-specific rather than a universal API mechanism.

Marginalia Session deletion is deliberately not a bulk or selected-ID
operation. Its intended shape is the single-resource request
`DELETE /api/v1/marginalia/sessions/{session_id}/`. One authenticated request
represents the complete permanent deletion of one Session and its Session-owned
annotations. There is no delete-all-Sessions or delete-all-history endpoint.
The server must enforce ownership and the complete destructive lifecycle;
current visibility of the linked Book is not required.

## Response and wire conventions

There is no universal success envelope. Detail objects, collection pages,
workflow results, empty `204` responses, and attachments legitimately differ.
The active serializer or normative schema owns each exact shape.

Server JSON generally retains `snake_case`. `@second-pass/spl-api` validates
and adapts wire values—including field-error paths—into stable frontend naming
before React sees them. Orchestrators interpret SDK results and errors;
presentational regions do not consume wire payloads or runtime SDK error
classes. See [Frontend](frontend.md#data-and-error-flow).

API failures stay API responses. Authentication, authorization, forced-password
enforcement, and missing API routes must not redirect to the login page or
Product UI shell. Browser navigation outside the API namespace retains its
separate redirect and HTML error behavior.

## Error conventions

Error responses are bounded JSON, but the project intentionally has more than
one established shape:

- DRF authentication and object failures commonly use `{"detail": "..."}`.
- Serializer validation commonly returns fields mapped to message lists.
- Project workflow errors use `{"error": {"code", "message", "detail",
  "hint"}}`, sometimes with a small operation-specific extension.
- Middleware may return a bounded top-level `detail` and `code`, such as
  `password_change_required`.

Do not claim or implement a universal envelope without a coordinated contract
change. Stable machine-readable codes should be added only for errors callers
must distinguish; SDK normalization handles the established variants.

Status semantics are conventional but authority-sensitive:

- `400` covers malformed or invalid request data.
- `403` covers authenticated requests that lack authority when acknowledging
  the object or operation is safe.
- `404` also covers inaccessible objects when confirming existence would leak
  another user's or Group's data.
- `409` covers valid requests blocked by lifecycle, replay, or integrity state.
- `413` is used for configured oversized-export responses; upload validators
  may instead report a field-level `400` according to their endpoint contract.
- `503` may represent a bounded storage or readiness failure.

Unknown, foreign, and hidden identities must not yield more revealing errors
than the owning domain permits. Responses must not contain exception text,
tracebacks, credentials, tokens, cookies, local paths, storage names, archive
payloads, or private object metadata. API route misses under `/api/` use the
bounded JSON not-found response rather than Django's HTML page.

Specialized contracts are documented with their owners: forced-password
enforcement in [Architecture](architecture.md), pairing in
[Client API authorization](client-api-auth.md), and Marginalia import/export
conflicts and size failures in [Marginalia](marginalia.md).

## Pagination and collections

Normal list endpoints use page-number pagination:

- `page` is one-based;
- `page_size` defaults to 20 and is capped at 200;
- an absent, blank, malformed, or nonpositive `page_size` falls back to 20;
- a value above 200 is clamped to 200.

The shared page shape is `count`, `next`, `previous`, and `results`.
Endpoint-specific collections may deliberately use a smaller fixed limit or a
complete bounded collection instead, but that must be explicit in their domain
contract. Clients must follow `next` rather than assuming one page is complete.

Filtering and visibility happen before counting and pagination. Ordering must
be deterministic, with stable fallback identities where display values can
tie. List, detail, nested collection, preview, and mutation paths must not use
different visibility universes merely because they serialize different shapes.

## Visibility and anti-enumeration

Authorization belongs to backend query and service boundaries. React route
guards, capability flags, `can_edit` hints, and objects fetched earlier in a
workflow are never mutation authority.

For owner-initiated Marginalia Session deletion, the backend authorizes the
target Session by ownership even when the owner no longer has current visibility
to the linked Book. A successful operation deletes only that Session and its
cascading annotations; it does not delete the Book or unrelated Marginalia.
Foreign and missing Session identities follow the domain's bounded
anti-enumeration behavior. The destructive operation is atomic from the API
contract's perspective: failure does not leave a partially deleted
Session-owned collection.

The same current visibility or ownership rule must be applied to lists,
details, mutations, attachments, downloads, counts, filters, and previews.
Selected operations must validate the requesting user's complete selection
without revealing whether rejected IDs belong to another user. Where existence
itself is sensitive, missing and inaccessible objects intentionally converge on
the same `404` treatment.

General role and Shelf authority belongs in [Permissions](permissions.md).
Detailed current Book authority is immutable policy in [Library Book
Visibility](book-visibility.md); Advanced/Simple Mode behavior is immutable
policy in [Advanced Library Groups Mode](advanced-library-groups.md). The
separate historical-reading boundary is immutable policy in
[Marginalia-Linked Books](marginalia-book-visibility.md).

## Attachments, imports, and downloads

Authenticated downloads recheck ownership or current visibility at download
time through the canonical uncached boundary. A URL or object returned by an
earlier response is not continuing authorization. Public cover images are a
separate display-only surface; stored EPUBs and private archives are never
exposed as raw public media.

Successful attachments set their real media type and a bounded,
content-disposition filename. User-derived filenames are normalized so control
characters, path separators, storage identities, and local paths cannot enter
headers. Buffered exports are fully validated and size-checked before a response
is constructed, so failures do not emit partial attachments. A failure after a
genuinely streamed file has sent headers can only terminate the stream and be
logged; it cannot retroactively replace the HTTP status.

An attachment endpoint may return structured JSON instead of a file when it
fails before streaming. The shared SDK attachment client recognizes
`application/json` and any media type ending in `+json`, case-insensitively and
with normal parameters. Malformed JSON gets a bounded generic error. HTML,
plain-text, and other proxy-generated failures remain generic and their bodies
are not exposed to the Product UI.

Library upload formats, metadata behavior, and archive safety limits are owned
by [Imports](imports.md). Marginalia upload, partial-apply, export bounds, and
downloadable Unmatched behavior are owned by [Marginalia](marginalia.md); exact
interchange structures are owned by the normative specifications linked below.

## Stable external boundaries

Only externally meaningful surfaces receive dedicated prose:

- [Client API authorization](client-api-auth.md) owns discovery, Reader
  pairing, bearer scope, polling/consumption, and client-session revocation.
- [Marginalia](marginalia.md) owns user-data lifecycle, staged import, partial
  apply, replay, and bounded export behavior.
- [Marginalia export archive](specs/marginalia-export.md) and the
  [Reading Session and Annotation profile](specs/reading-session-annotation-profile/README.md)
  own exact portable interchange schemas. Focused offline checks validate their
  examples and semantic parity with the runtime bundled schema.
- [Imports](imports.md) owns Library import metadata and untrusted archive
  handling.
- [Permissions](permissions.md) owns general roles, Group mutation authority,
  and Shelf access, with detailed visibility and mode policy delegated to the
  immutable documents above.

Exact internal Product UI routes and payloads are coordinated through backend
serializers, SDK adapters, and focused tests. They do not become stable external
contracts merely because the current React application calls them.

## Compatibility and change policy

Second Pass Library is pre-release. Do not add legacy routes, response aliases,
dual field names, or compatibility wrappers unless an explicit supported client
requires them. Backend, SDK, and Product UI may change together, with affected
callers and tests updated directly.

Externally documented Reader behavior and normative Marginalia schemas still
require coordinated documentation, implementation, SDK/client, and test changes.
Repository code, executable schemas, current tests, and observed runtime behavior
override stale prose.
