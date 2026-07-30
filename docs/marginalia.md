# Marginalia domain

Marginalia is the domain root for user-owned Book reading history. Its core
records are:

- `ReadingSession`: one user's reading pass through one Book;
- progress fields on `ReadingSession`: its current saved location;
- `Annotation`: a located bookmark or highlight belonging to a Reading Session;
  highlights may also carry a user note/comment.

The foundation models live in the `marginalia` Django app. The first read-only
API slice exposes owned-Marginalia Books under `/api/v1/marginalia/books/`.
The existing `reading` app and `/api/v1/reading/` routes remain the old runtime
implementation while the new domain is built route by route; the new app does
not depend on them.

## Owned-Marginalia Books

These authenticated read endpoints support Django sessions and Client API
bearer tokens:

- `GET /api/v1/marginalia/books/`
- `GET /api/v1/marginalia/books/<book_id>/`
- `GET /api/v1/marginalia/books/<book_id>/sessions/`
- `GET /api/v1/marginalia/sessions/`
- `GET/PATCH /api/v1/marginalia/sessions/<session_id>/`
- `GET/PUT /api/v1/marginalia/sessions/<session_id>/progress/`
- `POST /api/v1/marginalia/sessions/<session_id>/close/`
- `GET /api/v1/marginalia/sessions/<session_id>/annotations/`
- `POST /api/v1/marginalia/sessions/<session_id>/annotations/batch/`

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
    "series_index": "2.5"
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

A Book with Marginalia is protected from deletion. Deleting a user deletes that
user's Sessions. Deleting a Session deletes its annotations.

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
state. External client correlation and import/export profile mapping are
deferred until their routes are rebuilt.
