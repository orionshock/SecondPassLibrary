# Marginalia domain

Marginalia is the domain root for user-owned Book reading history. Its core
records are:

- `ReadingSession`: one user's reading pass through one Book;
- `SessionProgress`: the single located progress record for a Reading Session;
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
      "annotation_count": 12,
      "progression": 0.75
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
user's Sessions. Deleting a Session deletes its progress and annotations.

## Located records

`SessionProgress` and `Annotation` store a `cfi` machine anchor adjacent to an
optional `location_label` display companion. Both values are opaque to the
Marginalia models. They are stored unchanged; the models do not parse,
normalize, infer, reconstruct, or derive either value.

`location_label` is a bounded string of at most 255 characters. Its absent
storage value is the empty string rather than `null`. It is Reader-generated
location display data, not annotation text or user-authored prose.

Annotations derive their user and Book context solely from their Reading
Session. They do not duplicate a Book foreign key. Located annotations require
a nonempty CFI and use soft deletion. The only annotation kinds are `highlight`
and `bookmark`. A note is `comment_text` attached to a highlight, not a separate
annotation kind. Highlights require selected text; bookmarks carry neither
highlight nor comment content.

Request idempotency remains an API concern and is deliberately not domain model
state. External client correlation and import/export profile mapping are
deferred until their routes are rebuilt.
