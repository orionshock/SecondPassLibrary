# API conventions

## Scope

The versioned JSON API lives under `/api/v1/`. The public discovery document at
`/.well-known/secondpass` is the one exception; external clients use it to find
the API root.

This page describes conventions shared across endpoints. It is not a complete
route or field reference. Check the active URL configuration and serializers
for exact methods, parameters, and wire fields. The first-party SDK defines the
shapes consumed by the Product UI, while the Marginalia schemas define the
portable archive formats.

DRF returns JSON by default. Product UI transport details may change with the
SDK before release and should not be treated as public API merely because the
current frontend uses them.

## Authentication

The API supports two forms of authentication:

- The browser Product UI uses Django sessions. Unsafe requests require a valid
  CSRF token. The SDK sends same-origin cookies and the CSRF header.
- External Reader clients use bearer tokens on the endpoints that explicitly
  support them. A bearer token has a narrower scope than the user's browser
  session, regardless of the user's account role.

Session authentication is the default. Endpoints that accept bearer tokens
must opt in and must still enforce role, ownership, and object-visibility
checks.

Anonymous access is limited to readiness and discovery responses and the
capability-based parts of Reader pairing. Public covers and the remaining
Django-rendered pages are separate HTTP surfaces. HTTP Basic authentication is
not supported.

Inactive users cannot authenticate with either sessions or bearer tokens. A
session user marked `must_change_password` receives a JSON error from blocked
API calls rather than an HTML redirect. See
[Architecture](architecture.md#browser-sessions-and-forced-password-changes)
for browser-session behavior and
[Client API authorization](client-api-auth.md) for pairing, bearer tokens, and
revocation.

Cross-origin requests to `/api/` and `/.well-known/` do not include
credentials. This allows an independent browser-based Reader to authenticate
with a bearer token. The Product UI remains same-origin and uses session
cookies. Cross-origin cookie authentication is not supported.

## Requests

JSON is the standard request format. Upload endpoints use multipart forms, and
downloads return either binary attachments or JSON documents with their stated
media types. Do not assume that neighboring endpoints accept the same format.

Wire fields use `snake_case`. UUIDs are opaque strings and are validated before
use. A malformed UUID in a query parameter or request body normally produces a
field-level `400`. A malformed path UUID may fail URL matching and return the
API's JSON `404`. Public profile UUIDs, not Django authentication-table IDs,
identify users in API relationships.

Mutation serializers reject unknown fields when they define a closed input
shape. This prevents read-only and privileged-looking fields from being
silently ignored on account, catalog, Group, Shelf, and Marginalia writes. Each
serializer defines its own accepted fields; read and write shapes are not
assumed to be interchangeable.

Filtering, ordering, and search fields come from explicit allowlists. Client
input is never used as an arbitrary ORM field name or SQL fragment. Bulk
operations validate their item limits before expensive queries or
serialization. Limits, idempotency keys, and replay fingerprints are defined by
the workflow that uses them rather than by one universal API mechanism.

Marginalia Session deletion is intentionally a single-resource operation:

```text
DELETE /api/v1/marginalia/sessions/{session_id}/
```

One request permanently deletes one owned Session and its annotations. There
is no API for deleting all Sessions or all reading history. The server checks
ownership and performs the cascade. Current access to the linked Book is not
required.

## Limited HTML fields

The following fields store server-sanitized HTML:

- Book description
- Author biography
- Series summary
- Library Group description
- Shelf description
- Server Description
- Server Banner Message

The supported tags are `p`, `br`, `b`, `strong`, `i`, `em`, `ul`, `ol`, and
`li`. Attributes are not allowed. The sanitizer removes unsupported markup and
discards `script` and `style` elements with their contents. Links, images,
headings, tables, layout elements, classes, inline styles, event handlers, and
other HTML are unsupported.

The backend sanitizes these values with `nh3` before saving them and returns the
stored fragment unchanged. Clients should render them as limited HTML, not as
arbitrary trusted HTML. Plain text is valid. Raw newlines remain raw newlines;
the server does not invent paragraphs or line breaks. HTML entities retain
their normal meaning.

The Product UI uses a restricted WYSIWYG editor and one shared rendering
boundary. It does not add a second sanitizer, and these fields do not support
Markdown.

Book, Author, Series, Group, and Shelf prose fields may contain at most 25,000
characters of serialized sanitized HTML. Sanitization happens before the
length check, and markup counts toward the limit. Over-limit values are
rejected rather than truncated. Server Description and Server Banner Message
use their own shorter limits.

## Responses

Success responses do not share one envelope. Depending on the endpoint, a
successful response may be a detail object, a paginated collection, a workflow
result, an empty `204`, or an attachment. The endpoint serializer or portable
schema defines the exact shape.

Server JSON normally uses `snake_case`. `@second-pass/spl-api` validates and
adapts wire values, including validation paths, before React receives them.
Orchestrators interpret SDK responses and errors. Presentational components do
not read wire payloads or SDK error classes directly. See
[Frontend](frontend.md#data-and-error-flow).

API failures stay in the API. Authentication, authorization, forced-password
checks, and missing `/api/` routes return JSON and must not redirect to the
login page or Product UI shell. Browser routes outside the API retain their
normal HTML and redirect behavior.

Marginalia highlights keep selected `text` separate from the anchoring
`prefix` and `suffix`. Only `text` is displayed as the quotation. See
[Marginalia](marginalia.md#annotation-lifecycle).

## Saved Marginalia locations

Every saved progress value and annotation location has a CFI and may include a
`locationLabel` (`location_label` in the REST API). The CFI is the durable
reading-position anchor. The label is persisted display text: clients may show
it in Session history, progress summaries, bookmarks, highlights, and notes,
but must not parse it for navigation, identity, matching, or anchoring.

The Reader's live chrome may show temporary rendition details such as
`Dedication • p1/2 • 1%`. That live label is not the saved label. New saved
labels use `PPP% - Label`, with a zero-padded whole-Book percentage from `000`
through `100`, for example `001% - Dedication` or `014% - Chapter 08`.

Older labels such as `Chapter 08 - 01%` remain valid. The server stores and
returns them as supplied and does not migrate or reinterpret them. See the
[Reading Session and Annotation profile](specs/reading-session-annotation-profile/profile.md#saved-location-labels)
for label construction and fallback rules.

## Errors

Several error shapes are already in use:

- DRF authentication and object errors commonly return `{"detail": "..."}`.
- Serializer validation commonly maps field names to lists of messages.
- Workflow errors use `{"error": {"code", "message", "detail", "hint"}}`,
  sometimes with a small workflow-specific extension.
- Middleware may return a top-level `detail` and `code`, such as
  `password_change_required`.

Do not assume a universal error envelope. Stable machine-readable codes are
added when callers need to distinguish specific conditions; the SDK normalizes
the established response variants.

Status codes follow these general rules:

- `400` — malformed or invalid input
- `403` — an authenticated caller lacks permission, when acknowledging the
  object or operation is safe
- `404` — missing objects and inaccessible objects whose existence must not be
  disclosed
- `409` — lifecycle, replay, or integrity conflicts
- `413` — configured oversized-export failures; some upload validators instead
  use a field-level `400`
- `503` — bounded storage or readiness failures

Errors for missing, hidden, and foreign objects must not reveal more than the
domain permits. Responses must not include exception text, tracebacks,
credentials, tokens, cookies, local paths, storage names, archive payloads, or
private object metadata. Unknown `/api/` routes return the bounded JSON `404`,
not Django's HTML error page.

Special cases are documented alongside their workflows: forced-password
handling in [Architecture](architecture.md), pairing in
[Client API authorization](client-api-auth.md), and Marginalia import/export
errors in [Marginalia](marginalia.md).

## Pagination and collections

Most list endpoints use page-number pagination:

- `page` starts at 1.
- `page_size` defaults to 20 and cannot exceed 200.
- Missing, blank, malformed, or nonpositive `page_size` values fall back to 20.
- Values above 200 are clamped to 200.

The common page shape contains `count`, `next`, `previous`, and `results`.
Some endpoints return a smaller fixed collection or another explicitly bounded
shape. Clients should follow `next` rather than assuming that the first page is
complete.

Visibility and filtering are applied before the count and page are calculated.
Ordering is deterministic and uses stable identity fallbacks when display
values tie. Lists, details, previews, nested collections, and mutations must
use the same visibility rules even when their response shapes differ.

## Library reads

Authenticated Library reads provide both global and Group-scoped collections:

- `books/`, `authors/`, `series/`, and `tags/` below `/library/` or
  `/library/groups/{group_id}/`
- broad search at `/library/search` or
  `/library/groups/{group_id}/search`

The global scope includes every Book visible to the caller. A Group-scoped
request first resolves a visible Group and then limits results to visible Books
assigned to it. An inaccessible Group returns `404` before query processing.
Both scopes use the same filters, ordering, compact Book representation, axis
representations, previews, counts, and pagination.

Book browse search (`q`) checks title and sort title. Broad search also checks
subtitle, Author and Series names, identifier values, Catalog Tag names,
publisher, and description. Broad search supports `title`, `-title`, `author`,
`-author`, `series`, and `-series` ordering. Missing or blank search text
returns an empty normal page.

Paginated Book, broad-search, Author, and Series responses include a top-level
`catalog_tags` array next to `results`. Each entry contains the Catalog Tag's
`id`, `name`, and `slug`, plus `book_count`. Counts come from the complete
distinct-Book population for the current scope, search, and filters before
pagination. Tags with no matches are omitted, and an empty population returns
`catalog_tags: []`.

The active `tag` filter participates in those counts. It is a single-filter
model, not a self-excluding or multi-Tag facet system. The standalone `/tags/`
routes retain their scope-total counts and normal response envelope.

Book `description`, Author `biography`, and Series `summary` use the shared
[limited HTML contract](#limited-html-fields). Clients should render the
supported paragraphs, line breaks, emphasis, and lists. A client that cannot
do so safely should show plain text rather than raw HTML source. Clients should
not reproduce Calibre sanitization rules or define a competing HTML policy.

Book identifiers are repeatable string metadata, not Book identity. Several
Books may carry the same normalized ISBN, EPUB UID, Calibre ID, or other
scheme/value. Only duplicate identical identifier rows within one Book are
rejected. An exact EPUB checksum, not identifier metadata, determines whether
a Library import is a duplicate file.

During Library import, normalized Author and Series names are used for lookup,
not as proof of identity. With no match, the importer may create a record. With
one match, it may reuse that record. Multiple matches produce a `conflict`; the
server will not choose or merge records arbitrarily. The response tells the
operator whether Author or Series resolution was ambiguous and asks them to
resolve the catalog ambiguity or correct the source metadata before retrying.
Import items use `author_ambiguous` and `series_ambiguous` as their stable
`error_category` values.

Marginalia import follows a stricter Book identity rule because annotations are
tied to an exact EPUB structure. It matches only the archive's `fileHash`
against the stored EPUB checksum. Title, Author, ISBN, EPUB UID, Calibre ID, and
other metadata are never fallbacks. A missing or different hash leaves the
archive Book unmatched.

Author and Series collections share normalized-name matching, `exclude_id`,
Catalog Tag filtering, previews, and axis ordering. Counts and previews use the
same scoped Book population. Catalog Tag counts also use the full scoped
population rather than the current Book page.

A Group-scoped `exclude_shelf` value must identify a readable Shelf owned by
that Group. A mismatched or inaccessible Shelf returns the same non-enumerating
`404`. Global contextual exclusions retain their existing permission rules.

Book details and Book mutations, downloads, and imports remain global routes.
Group routes add only Group assignment, membership, and Group-owned Shelf
operations; they do not duplicate Book, Author, Series, or Tag detail routes.

## Visibility and anti-enumeration

Backend queries and services enforce authorization. React route guards,
capability flags, `can_edit` hints, and previously fetched objects are not
permission checks.

The same visibility or ownership rule applies to lists, details, mutations,
attachments, downloads, counts, filters, and previews. Operations that accept
several IDs validate the caller's complete selection without revealing whether
a rejected ID belongs to another user. When object existence is sensitive,
missing and inaccessible objects both return `404`.

A user may delete one of their own Marginalia Sessions after losing access to
the linked Book. Deletion removes that Session and its annotations, but not the
Book or anyone else's Marginalia. Missing and foreign Session IDs use the same
bounded anti-enumeration response. The deletion is atomic: a failure cannot
leave half of the Session-owned collection behind.

See [Permissions](permissions.md) for roles and Shelf authority. The detailed
rules for current Book access are in [Library Book Visibility](book-visibility.md),
Advanced and Simple Mode are defined in
[Advanced Library Groups Mode](advanced-library-groups.md), and historical
reading access is defined in
[Marginalia-Linked Books](marginalia-book-visibility.md).

## Attachments, imports, and downloads

Authenticated downloads recheck ownership or current visibility through the
uncached authorization path. A URL or object returned by an earlier request
does not grant continuing access. Public cover images are a separate,
display-only surface. EPUB files and private archives are never served as raw
public media.

Successful attachments use their actual media type and a bounded
`Content-Disposition` filename. Filenames derived from user data are cleaned so
control characters, path separators, storage identities, and local paths
cannot enter response headers.

Buffered exports are validated and size-checked before the response is built,
so an error does not produce a partial attachment. Once a truly streamed
response has sent its headers, a later failure can only stop the stream and be
logged; it cannot change the HTTP status.

An attachment endpoint may return structured JSON when it fails before
streaming. The SDK recognizes `application/json` and media types ending in
`+json`, ignoring case and normal parameters. Malformed JSON becomes a bounded
generic error. Bodies from HTML, plain-text, and other proxy-generated failures
are not exposed to the Product UI.

[Imports](imports.md) documents Library upload formats, metadata handling, and
archive limits. [Marginalia](marginalia.md) documents Marginalia staging,
partial apply, export limits, and downloadable Unmatched Sessions. The linked
schemas below define the exact interchange structures.

## External contracts

- [Client API authorization](client-api-auth.md) covers discovery, Reader
  pairing, bearer scope, polling, token consumption, and client-session
  revocation.
- [Marginalia](marginalia.md) covers the reading-data lifecycle, staged import,
  partial apply, replay, and export limits.
- [Marginalia export archive](specs/marginalia-export.md) and the
  [Reading Session and Annotation profile](specs/reading-session-annotation-profile/README.md)
  define the portable interchange schemas. Offline contract tests validate the
  examples and compare the documented schemas with the runtime copy.
- [Imports](imports.md) covers Library metadata import and untrusted archives.
- [Permissions](permissions.md) covers roles, Group mutations, and Shelf access.
  The visibility and mode documents linked above provide the detailed rules.

Internal Product UI routes and payloads are coordinated through backend
serializers, SDK adapters, and tests. Their use by the current React application
does not make them stable external contracts.

## Compatibility

Second Pass Library is pre-release. Avoid legacy routes, response aliases,
duplicate field names, and compatibility wrappers unless a supported client
actually needs them. Backend, SDK, Product UI, and affected tests can change
together.

Changes to documented Reader behavior or the Marginalia schemas require
coordinated updates to documentation, implementation, clients, and tests. When
prose has fallen behind, the executable schemas, current code, and tests define
the behavior.
