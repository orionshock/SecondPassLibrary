# Marginalia domain

Marginalia is the domain root for user-owned Book reading history. Its core
records are:

- `ReadingSession`: one user's reading pass through one Book;
- progress fields on `ReadingSession`: its current saved location;
- `Annotation`: a located bookmark or highlight belonging to a Reading Session;
  highlights may also carry a user note/comment.

The models and complete API live in the `marginalia` Django app under
`/api/v1/marginalia/`. Marginalia is the sole runtime domain for this data.

## Django admin repair surface

Django admin registers Marginalia Reading Sessions, Annotations, and Import
Stages as privileged operator repair surfaces. Operators can add, inspect,
change, individually delete, and bulk delete these records. Session lifecycle
and progress fields, complete Annotation location/body/deletion state, and all
persisted Import Stage metadata are exposed; only model-generated UUID and
automatic timestamps are read-only. The raw Import token cannot be displayed
because only its digest is stored, and admin does not read staged archive
contents automatically.

Admin repair is not constrained by Product UI active-only mutation policy.
Model and database integrity constraints still apply. Deleting a Session
cascades to its Annotations, and deleting a Library Book cascades through its
Marginalia Sessions and Annotations after Django's normal affected-object
confirmation. Deleting an Import Stage schedules removal of that stage's one
digest-named archive file; a file cleanup failure does not broaden deletion and
remains recoverable through `cleanup_marginalia_import_stages`.

## Canonical archive codec

`marginalia.archives` owns the strict executable contract shared by
Marginalia Import and Export. Its runtime schema lives beside that code; the
application and tests do not load documentation schemas from `docs/`.

Archive JSON uses camelCase and explicit portable identities:

- `fileHash` is the sole Book identity and has the form `sha256:<checksum>`;
- `sourceReadingSessionId` is deterministic within the source archive and is
  not a destination `ReadingSession` primary key;
- `clientAnnotationId` is the Reader-generated identity stored as
  `Annotation.client_id` and is not the local Annotation primary key.

The codec serializes an explicitly supplied, already-authorized Session set.
It groups Sessions by Book, includes inaccessible historical Books, reads
progress directly from the Session, excludes soft-deleted Annotations, and
uses the canonical highlight/bookmark union. It does not match Books, inspect
assets, parse CFIs, infer labels, authorize callers, or write database rows.

Sessions without non-deleted Annotations are excluded by default. Callers may
set `include_empty_sessions` explicitly for the Product UI's **Include empty
sessions** choice. Missing Book checksums and duplicate hashes across distinct
Books fail the complete serialization as integrity errors.

The session-authenticated Export API uses this codec for complete and selected
JSON attachments. Import preview validates the same contract before creating a
user-bound stage, and Apply imports selected staged Sessions.

## Owned-Marginalia Books

These authenticated read endpoints support Django sessions and Client API
bearer tokens:

- `GET /api/v1/marginalia/books/`
- `GET /api/v1/marginalia/books/<book_id>/`
- `GET /api/v1/marginalia/books/<book_id>/sessions/`
- `POST /api/v1/marginalia/books/<book_id>/open/`
- `GET /api/v1/marginalia/books/<book_id>/active-session/`
- `POST /api/v1/marginalia/books/<book_id>/start-over/`
- `GET /api/v1/marginalia/sessions/`
- `GET /api/v1/marginalia/sessions/recent/`
- `GET/PATCH /api/v1/marginalia/sessions/<session_id>/`
- `GET/PUT /api/v1/marginalia/sessions/<session_id>/progress/`
- `POST /api/v1/marginalia/sessions/<session_id>/close/`
- `GET /api/v1/marginalia/sessions/<session_id>/annotations/`
- `POST /api/v1/marginalia/sessions/<session_id>/annotations/batch/`
- `GET/POST /api/v1/marginalia/export/` (Django session authentication only)
- `POST /api/v1/marginalia/import/preview/` (Django session authentication only)

A Book is present only when the caller owns at least one Marginalia
`ReadingSession` for it. This historical ownership is independent of current
Library visibility. It authorizes only the bounded Marginalia Book projection;
it does not grant EPUB access, download or Reader access, Book mutation, Group
or Shelf access, or broader Library visibility. Missing Books and Books without
caller-owned Sessions both return the normal no-leakage `404` response.

List responses use normal page-number pagination (`page`, `page_size`; default
20, maximum 200). `q` searches only Book title, author names, and Series name.
Results are distinct Books ordered by newest caller-owned Marginalia activity,
then title and id. Activity is the newest update among the caller's Sessions,
their progress, and their non-deleted annotations.

List and detail use the same projection:

```json
{
  "id": "<book-uuid>",
  "title": "Book title",
  "authors": [{"id": "<author-uuid>", "name": "Author name"}],
  "series": {
    "id": "<series-uuid>",
    "name": "Series name",
    "series_index": "2.50"
  },
  "cover_url": "http://example.test/media/covers/example.jpg",
  "can_open": false,
  "session_count": 2,
  "active_session_count": 0,
  "last_activity_at": "2026-07-29T12:00:00Z"
}
```

`series` and `cover_url` may be `null`. Counts include only the authenticated
user's Sessions. `can_open` is computed separately from current Library
visibility and is not implied by Marginalia ownership. Cover images remain
available when `can_open` is false because covers are public display assets in
the existing media security model; the projection never contains EPUB/file
metadata, download URLs, checksums, identifiers, Groups, Shelves, or permission
internals.

## Live-reading lifecycle bootstrap

The three Book lifecycle routes return one bounded bootstrap envelope. It
contains the canonical Marginalia Book summary, active Session detail and
progress, every current non-deleted Annotation for that active Session in
stable reading order, and the ordinary first page of the Book's closed
Sessions:

```json
{
  "created": false,
  "context": {"book": {"id": "<book-uuid>", "title": "Book title"}},
  "session": {"id": "<session-uuid>", "status": "active", "progress": null},
  "annotations": [],
  "closed_sessions": {
    "count": 3,
    "next": null,
    "previous": null,
    "results": []
  }
}
```

Annotations are complete and unpaginated. Closed history uses the normal
20-row page size and its pagination links target
`GET /api/v1/marginalia/books/<book_id>/sessions/?status=closed`. Bootstrap
does not repeat the profile URI from `/server/info` and contains no Book asset,
file, download, hash, or storage data. Library separately owns asset
acquisition and asset failures; Marginalia checks only current Library
authority.

`POST /api/v1/marginalia/books/<book_id>/open/` accepts optional `name` and
`notes` creation defaults. It creates an active Session only when none exists
(`201`, `created=true`), otherwise returns the existing Session unchanged
(`200`, `created=false`). Open never closes or replaces a Session.

`GET /api/v1/marginalia/books/<book_id>/active-session/` is strictly
read-only. When no active Session exists, it returns `session=null`, an empty
Annotation collection, and the closed history page. It never creates a
Session or changes activity timestamps.

`POST /api/v1/marginalia/books/<book_id>/start-over/` requires a valid
`Idempotency-Key`. In one transaction it optionally finalizes the active
Session's `name`, `notes`, and complete progress location, explicitly closes
that Session, and creates one blank active Session. The new Session has no
progress or Annotations; all previous progress and Annotations remain with the
closed Session. With no active Session, an empty request creates the blank
Session while finalization fields are rejected. The route always returns
`201` and `created=true` on success.

Start-over keys are user-scoped and retained for 24 hours using the existing
short-lived idempotency store. The normalized request and complete successful
response are recorded in the same transaction as the lifecycle change. An
identical replay returns that stored response without another Session; reuse
for a different request or a still-processing request returns a bounded
`409` conflict.

All three routes support session and Client API bearer authentication and
require current Library authority for the Book. Missing and inaccessible Books
use the same no-leakage `404`. They do not inspect whether the authorized Book
asset is healthy or present.

## Sessions for one Book

`GET /api/v1/marginalia/books/<book_id>/sessions/` returns only the caller's
Sessions for an owned-Marginalia Book. The selected canonical Book summary is
returned once as `context.book`; Session rows do not duplicate Book metadata:

```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "context": {
    "book": {
      "id": "<book-uuid>",
      "title": "Book title",
      "authors": [{"id": "<author-uuid>", "name": "Author name"}],
      "series": null,
      "cover_url": null,
      "can_open": false,
      "session_count": 2,
      "active_session_count": 0,
      "last_activity_at": "2026-07-21T12:00:00Z"
    }
  },
  "results": [
    {
      "id": "<session-uuid>",
      "name": "Second pass",
      "notes": "Session note",
      "status": "closed",
      "started_at": "2026-07-01T12:00:00Z",
      "closed_at": "2026-07-20T12:00:00Z",
      "updated_at": "2026-07-20T12:00:00Z",
      "last_activity_at": "2026-07-21T12:00:00Z",
      "annotation_count": 12
    }
  ]
}
```

The list uses normal `page` and `page_size` pagination. Omitted `status` means
all Sessions; accepted values are `active` and `closed`. `q` searches only the
caller's Session name and notes because the parent Book is already fixed. Empty
filtered results remain `200` and retain `context.book`. Results are ordered by
the newest update across the Session, its progress, and its non-deleted
annotations, then by start time and id. Counts, filtering, search, and activity
exclude other users' Sessions.

Current Library visibility remains unnecessary. The caller must own a Session
for the parent Book, and missing or unowned parents use the same no-leakage
`404` response as Marginalia Book detail.

## All Sessions

`GET /api/v1/marginalia/sessions/` returns the caller's Sessions across all
Books. It uses the same bounded Session fields, activity calculation, status
filtering, and page-number pagination as the nested Book route. Omitted
`status` means all Sessions; accepted values are `active` and `closed`.

Global `q` search covers Session name and notes plus bounded Book identity:
Book title, author names, and Series name. The Session ownership filter is
applied before these joins, so another user's Sessions and Books cannot match.

`has_annotations=true` keeps Sessions with at least one non-deleted
Annotation; `has_annotations=false` keeps Sessions with none. Omission applies
no annotation-presence filter. Filtering occurs before pagination, and
soft-deleted Annotations do not count.

Each row adds only the Book reference needed by the Marginalia Session card:

```json
{
  "id": "<session-uuid>",
  "name": "Second pass",
  "notes": "Session note",
  "status": "closed",
  "started_at": "2026-07-01T12:00:00Z",
  "closed_at": "2026-07-20T12:00:00Z",
  "updated_at": "2026-07-20T12:00:00Z",
  "last_activity_at": "2026-07-21T12:00:00Z",
  "annotation_count": 12,
  "book": {
    "id": "<book-uuid>",
    "title": "Book title",
    "cover_url": "http://example.test/media/covers/example.jpg",
    "can_open": false
  }
}
```

The Book reference deliberately excludes authors, Series, Session aggregates,
EPUB/file fields, download URLs, identifiers, Groups, Shelves, and unrelated
catalog metadata. Owned Marginalia keeps title and public cover identity
available for an inaccessible historical Book, while `can_open=false` prevents
that history from implying current Book Detail, Reader, or download authority.

## Export

`GET /api/v1/marginalia/export/` exports all caller-owned Sessions.
`POST /api/v1/marginalia/export/` exports an explicit nonempty
`reading_session_ids` array. Both routes require Django session authentication;
Client API bearer tokens are rejected. Selected IDs must be unique and all
must belong to the caller. Missing and foreign IDs use the same no-leakage
`404`, and no partial archive is returned.

Both methods accept `include_empty_sessions`, defaulting to `false`. Empty
means no non-deleted Annotations. If the policy leaves no Sessions, the route
returns a bounded `409`. Current Library access is not required, so owned
historical Marginalia remains exportable.

The response is a canonical UTF-8 JSON attachment named
`YYYYMMDD-second-pass-marginalia.json`, using the server-local request date.
The codec supplies canonical ordering and the precise `generatedAt` timestamp.
Missing checksums and conflicting duplicate Book hashes fail the entire request
with a bounded integrity conflict before an attachment is emitted. The archive
contains no selection-scope field; its Books and Sessions are authoritative.

Export remains intentionally buffered but is bounded before materialization:
selected requests accept at most 500 unique Session IDs, complete exports at
most 5,000 owned Sessions, and either mode at most 50,000 non-deleted
Annotations. A conservative database-side estimate rejects likely archives over
16 MiB before serialization, and the one final UTF-8 JSON byte string is also
limited to 16 MiB before an attachment response is created. Oversized exports
return `413 EXPORT_TOO_LARGE` with the export mode, triggered limit kind and
maximum, plus guidance to use a smaller selected export. No partial or
persistent export file is created. Ownership filtering and the missing/foreign
selected-ID `404` boundary are unchanged.

## Import preview and staging

`POST /api/v1/marginalia/import/preview/` accepts multipart `file` and optional
`include_empty_sessions` fields. The upload is limited to 25 MiB and must be a
UTF-8 canonical Marginalia archive. Preview parses the runtime-owned archive
schema, creates no Sessions or Annotations, and returns an opaque import token
plus deterministic `book-000001` and `reading-session-000001` candidate
identities.

Book matching uses only exact canonical `fileHash` values. A trusted service
may resolve the identity across the Library to distinguish `not_found`,
`ambiguous_match`, and `book_inaccessible`, but the preview returns only the
staged metadata supplied by the user and never hidden live metadata or UUIDs.
All three reasons appear in the Unmatched review and are not selectable. There
is no title, author, ISBN, CFI, or EPUB fallback. A conservative
same-Book/name/start-time duplicate
check produces a warning only; it does not suppress a matched Session.

Empty Sessions have no non-deleted Annotations. They are omitted by default;
`include_empty_sessions=true` includes them. The choice is stored on the stage
and is the authority for Apply and unmatched download. Source `active`
and `closed` Sessions are reviewable, but both report `will_import_as_status`
as `closed`. Unmatched Sessions remain reviewable and counted for the unmatched
download, but cannot be selected for Apply. `can_apply` is true only when a
matched Session survives the staged policy.

Successful preview stores canonical archive bytes under
`userdata/imports/staged/marginalia/<token-digest>.json` and one database stage
record containing only the token digest, owner, exact two-hour expiry, staged
policy, state, storage key, bounded preview metadata, and—after Apply—a request
fingerprint and bounded replay result. Uploaded names are not retained in
storage paths. Runtime token lookup rejects missing, foreign, malformed, or
expired stages through the same no-leakage boundary; a ready stage also
requires its staged file. Applied replay uses the stored result and therefore
does not require that deleted file. Expired stages are unusable immediately
even if their abandoned files await operator cleanup.

## Import Apply

`POST /api/v1/marginalia/import/apply/` is session-authenticated and accepts an
opaque `import_token` plus a nonempty `reading_sessions` selection. Each row
uses its staged `candidate_id` and may override `name` and `notes`. Candidate
IDs must be unique. Only matched candidates persisted as importable by that
stage can be selected; unmatched candidates and empty Sessions excluded by the
staged policy cannot be introduced at Apply time.

Apply locks the stage and validates the complete selection and staged canonical
archive before creating data. Immediately before mutation it rechecks every
selected Book through the uncached Library visibility query. Still-visible
candidates are created in one database transaction with fresh local UUIDs;
candidates that lost access are marked `book_inaccessible` in the persisted
stage preview and moved into the same Unmatched result/artifact. Access loss is
a successful partial apply, not a `403`. A missing Book, malformed stage, or
persistence failure remains a transaction-wide bounded `409`. Marginalia
created by earlier valid activity is unaffected.
Archive `clientAnnotationId` values become Session-scoped `Annotation.client_id`
values. Location strings and Annotation content are preserved unchanged; the
server does not parse CFI or inspect EPUB content.

Every imported Session is closed. A source closed Session retains `closedAt`.
A source active Session uses its canonical `updatedAt` as the deterministic
imported `closed_at`. Source Session, progress, and Annotation timestamps are
otherwise preserved. Import never creates, replaces, reopens, closes, or
mutates the user's active Session. Preview duplicate warnings remain warnings;
an explicitly selected candidate is imported.

On success, the stage stores a SHA-256 fingerprint of the effective selection
and overrides, its applied timestamp, applied/unmatched counts, staged-only
Unmatched Book summaries, and the bounded candidate-to-new-Session result.
Candidate order does not affect the fingerprint. An identical retry returns
that stored result without creating duplicates. A changed selection or override
returns `409`. The stage is consumed even for a partial or zero-created result;
retrying inaccessible material requires downloading and re-importing the diff.

The stage is the consumption authority. Its file is deleted after commit only
when no downloadable Unmatched Sessions remain. Partial results retain the file
until the normal two-hour stage expiry so their diff stays downloadable. A
cleanup failure does not undo the import; it
is logged without user data and the periodic cleanup command can remove the
digest-named orphan later. Validation or transaction failure leaves the stage
ready and retains its file for a corrected retry.

## Unmatched Import download

`GET /api/v1/marginalia/import/unmatched/?import_token=<token>` is a
session-authenticated, read-only download of the unmatched Sessions recorded by
one staged preview. The persisted preview controls which Books are unmatched,
which candidates survived the staged empty-Session policy, and the expected
download count. Download never reruns Library matching, so a later access
change does not alter the reviewed result. It does not parse CFI or inspect an
EPUB.

The response is `application/zip` with stable filename
`secondpass-marginalia-sessions.zip`. It contains only unmatched Books and
candidate-level apply-time access losses that still have staged downloadable
candidates, using this splitter-compatible
layout:

```text
01-book-key/01-01-book-key-reading-session-key.json
```

Numbering is one-based with a two-digit minimum width. Keys are deterministic,
ASCII-oriented, traversal-safe, reserved-name-safe, collision-safe, and
bounded. Book keys use the staged archive title with an ordinal fallback.
Session keys prefer canonical `sourceReadingSessionId`, then `startedAt`, then
an ordinal fallback; local database identities are never used.

Each JSON member is a canonical mini-export with exactly one Book and one
Reading Session. It preserves the original archive `generatedAt`, source
active/closed status, progress, Annotations, explicit portable identities, and
opaque location values. ZIP member order, timestamps, permissions, compression,
and JSON rendering are fixed, so repeated downloads from the same stage are
byte-identical. A stage with no downloadable unmatched Sessions returns `409`.

Download does not consume, extend, update, or invalidate the stage. Apply may
still use a ready stage afterward. A consumed partial stage remains downloadable
until expiry; its diff is assembled from the original staged archive and the
persisted classification. Restoring access does not rematch that stage: import
the downloaded canonical diff to preview and apply it again.

`python backend/manage.py cleanup_marginalia_import_stages` removes expired stages and
safe digest-named orphan files; `--dry-run` reports bounded counts without
deleting. The command is repeat-safe and suitable for periodic host scheduling.
Django does not schedule it. A weekly run is acceptable because runtime access
enforces the two-hour expiry independently.

## Recent Sessions

`GET /api/v1/marginalia/sessions/recent/` returns a bounded, unpaginated
Dashboard collection. Omitted `include_closed`, or `include_closed=false`,
returns active Sessions only; `include_closed=true` also includes closed
Sessions. `limit` defaults to 10 and accepts values from 1 through 50.

The ownership filter and limit are applied in the database. Results are not
deduplicated by Book and retain the server-authoritative activity order used by
the other Session collections: newest Session metadata, saved progress, or
non-deleted Annotation update first. Each result contains `id`, `name`,
`status`, `last_activity_at`, saved `progress` (or `null`), and the bounded
`id`, `title`, `cover_url`, and `can_open` Book reference. Inaccessible Books
remain identifiable while `can_open=false` prevents a Library action.

## Session detail and metadata

`GET /api/v1/marginalia/sessions/<session_id>/` returns one caller-owned
Session independently of current Library visibility. Missing and foreign
Sessions use the same no-leakage `404`. The canonical Marginalia Book summary
is returned once in `context.book`; the bounded Session detail is returned in
`session`:

```json
{
  "context": {"book": {"id": "<book-uuid>", "title": "Book title"}},
  "session": {
    "id": "<session-uuid>",
    "name": "Second pass",
    "notes": "Session note",
    "status": "active",
    "started_at": "2026-07-30T12:00:00Z",
    "closed_at": null,
    "updated_at": "2026-07-30T12:00:00Z",
    "last_activity_at": "2026-07-30T12:00:00Z",
    "annotation_count": 0,
    "progress": {
      "cfi": "epubcfi(/6/8!/4/2)",
      "location_label": "Chapter 08 · 42%",
      "updated_at": "2026-07-30T12:00:00Z"
    }
  }
}
```

`progress` is `null` when the Session has no saved location. It is read
directly from the Session's opaque progress fields; there is no numeric
progression or row-level profile version.

`PATCH` accepts only `name` and `notes`, supports partial updates, and returns
the same detail envelope. Only active Sessions are mutable. Closed Sessions
remain readable but reject metadata changes without altering stored data.
Reading detail never changes activity; a successful metadata update changes
the Session timestamp and therefore participates in normal activity ordering.

## Progress read and write

`GET /api/v1/marginalia/sessions/<session_id>/progress/` returns
`{"progress": null}` or the stored `{cfi, location_label, updated_at}` object.
The owner may read progress for active or closed Sessions even after losing
current Library access. Reading progress never creates state or changes a
timestamp.

`PUT` completely replaces the active Session's saved location. It requires a
nonblank `cfi`, accepts an optional `location_label`, rejects unknown fields,
and assigns `updated_at` on the server. The opaque CFI and label are stored
unchanged. A write requires ownership, an active Session, and current Library
authority for the Book. Marginalia delegates that authority decision to the
Library policy; it does not inspect, serve, or diagnose the Book asset. There
is no progress `PATCH` or `DELETE` operation.

## Explicit close

`POST /api/v1/marginalia/sessions/<session_id>/close/` explicitly closes one
owned active Session. The optional body may contain `name`, `notes`, and a
complete final `progress` location:

```json
{
  "name": "Finished first read",
  "notes": "Final thoughts",
  "progress": {
    "cfi": "epubcfi(/6/42)",
    "location_label": "Chapter 42 · 100%"
  }
}
```

Final metadata, final progress, and closure commit together under a Session row
lock. Live progress and close timestamps are server-assigned; a future
canonical import may preserve a separately validated source timestamp. Close
without final progress does not require current Library access. Final progress
does, because it is a live location write. The response is the normal Session
detail envelope and close never creates another Session.

An empty retry against an already closed Session returns its unchanged detail.
A retry whose supplied values equal the stored final values also succeeds.
Attempts to change closed metadata or progress return a bounded
`SESSION_CLOSED` conflict. Failed validation or authorization changes nothing.

## Session annotations

`GET /api/v1/marginalia/sessions/<session_id>/annotations/` returns the
complete current non-deleted Annotation collection for one owned Session. It
is deliberately not paginated so a Reading Client can replace its local
Session state from one response. Active and closed Sessions remain readable
without current Library access. Missing and foreign Sessions use the normal
no-leakage `404`.

Highlights and bookmarks use distinct canonical shapes. A highlight has one
body; a bookmark has none:

```json
{
  "id": "<server-uuid>",
  "client_id": "reader-highlight-1",
  "kind": "highlight",
  "location": {
    "cfi": "epubcfi(/6/8!/4/2)",
    "location_label": "Chapter 08 · 42%"
  },
  "body": {
    "text": "Selected passage",
    "prefix": "Before ",
    "suffix": " after.",
    "color": "yellow",
    "note": "Optional user note."
  },
  "created_at": "2026-07-30T12:00:00Z",
  "updated_at": "2026-07-30T12:00:00Z"
}
```

```json
{
  "id": "<server-uuid>",
  "client_id": "reader-bookmark-1",
  "kind": "bookmark",
  "location": {
    "cfi": "epubcfi(/6/10!/4/2)",
    "location_label": "Chapter 09 · 47%"
  },
  "created_at": "2026-07-30T12:05:00Z",
  "updated_at": "2026-07-30T12:05:00Z"
}
```

Results use stable reading order: nonblank `location_label` values sort first
and lexically ascending, followed by blank labels using CFI, creation time, and
server id as deterministic fallbacks. Marginalia does not parse either the
label or CFI.

## Annotation batch synchronization

`POST /api/v1/marginalia/sessions/<session_id>/annotations/batch/` accepts one
to 100 operations. Every `client_id` must be nonblank, at most 255 characters,
and unique within the request:

```json
{
  "operations": [
    {
      "action": "upsert",
      "annotation": {
        "client_id": "reader-highlight-1",
        "kind": "highlight",
        "location": {
          "cfi": "epubcfi(/6/8!/4/2)",
          "location_label": "Chapter 08 · 42%"
        },
        "body": {
          "text": "Selected passage",
          "prefix": "Before ",
          "suffix": " after.",
          "color": "yellow",
          "note": ""
        }
      }
    },
    {"action": "delete", "client_id": "reader-bookmark-1"}
  ]
}
```

`client_id` is unique within a Reading Session, not globally. Upsert creates or
updates that row and explicitly restores it when soft-deleted. Delete by an
unknown or already-deleted id is a retry-safe no-op. An identical upsert does
not create a duplicate or change its authoritative timestamps. Live creates
and actual changes receive server timestamps.

The entire request is strictly validated before mutation and commits in one
transaction. A duplicate `client_id` within one batch is rejected rather than
making operation order significant. The Session is locked and its active state
and current Library Book authority are rechecked inside the transaction.
Marginalia uses that Library policy without inspecting or serving the asset.
Closed Sessions return `SESSION_CLOSED`; access loss returns the normal bounded
permission error. Any failure leaves the complete batch unapplied.

Success returns the same complete authoritative non-deleted `annotations`
collection and reading order as GET. The reusable collection assembler is also
the source intended for the later open, active-session, and start-over
bootstrap envelopes.

## Session lifecycle

Session `status` is authoritative. It is either `active` or `closed`; there is
no archived state and no separate stored active flag. A database constraint
permits at most one active Session for a user and Book while allowing any
number of closed Sessions. Closed Sessions require `closed_at`, and active
Sessions cannot have it. Closing is idempotent: an already-closed Session keeps
its original state and timestamp. A Book may have only closed Sessions and no
active Session.

Opening is get-or-create behavior. If a Session is already active for the user
and Book, opening returns that Session unchanged. Opening never closes or
replaces an active Session. A new Session can be created only after the prior
active Session has been closed through the explicit close workflow. Future
metadata mutation services and API routes must reject changes to closed
Sessions.

Deleting a Book or user deletes the associated Sessions, and deleting a Session
deletes its Annotations. Django admin presents its normal cascade confirmation
before an operator deletion.

## Saved progress and located records

Progress is the Reading Session's current saved location, stored directly as
`progress_cfi`, `progress_location_label`, and `progress_updated_at`. There is
no separate progress row and no numeric progression field. No saved progress
is represented by blank CFI and label fields plus a null timestamp. A saved
location requires a nonempty CFI and timestamp; its label remains optional.
The three fields are assigned or cleared atomically.

Session detail and progress APIs project saved progress as `null` or:

```json
{
  "progress": {
    "cfi": "epubcfi(/6/8!/4/2)",
    "location_label": "Chapter 08 · 42%",
    "updated_at": "2026-07-30T12:00:00Z"
  }
}
```

Progress and `Annotation` store a `cfi` machine anchor adjacent to an optional
location-label display companion. Both values are opaque to the Marginalia
models. They are stored unchanged; the models do not parse, normalize, infer,
reconstruct, or derive either value.

`location_label` is a bounded string of at most 255 characters. Its absent
storage value is the empty string rather than `null`. It is Reader-generated
location display data, not annotation text or user-authored prose.

Annotations derive their user and Book context solely from their Reading
Session. They do not duplicate a Book foreign key. Located annotations require
a nonempty CFI and use soft deletion. Their durable client correlation id is
unique within the Session. The only annotation kinds are `highlight` and
`bookmark`. A note is `comment_text` attached to a highlight, not a separate
annotation kind. Highlights require selected text; bookmarks carry neither
highlight text, quote context, color, nor comment content.

The progress-write boundary requires that the caller own an active Session and
have current Library authority for its Book. Closed Sessions and inaccessible
Books remain readable under their normal ownership rules, but their progress
cannot be updated.

The supported interchange contract is identified once at application level by
`https://secondpasslibrary.local/specs/marginalia/0.1.0`; it is not persisted
on Sessions or Annotations. Authenticated `/api/v1/server/info/` exposes it as
`marginalia_profile_uri`.

Request idempotency remains an API concern and is deliberately not domain model
state. The archive codec maps `Annotation.client_id` to
`clientAnnotationId`; database Import and HTTP attachment routes use this
contract.
