# Marginalia domain

Marginalia is the domain root for user-owned Book reading history. Its core
records are:

- `ReadingSession`: one user's reading pass through one Book;
- `SessionProgress`: the single located progress record for a Reading Session;
- `Annotation`: a located bookmark or highlight belonging to a Reading Session;
  highlights may also carry a user note/comment.

The foundation models live in the `marginalia` Django app. No
`/api/v1/marginalia/` routes exist yet. The existing `reading` app and
`/api/v1/reading/` routes remain the old runtime implementation while the new
domain is built route by route; the new app does not depend on them.

## Session lifecycle

Session `status` is authoritative. It is `active`, `completed`, or `archived`;
there is no separate stored active flag. A database constraint permits at most
one active Session for a user and Book while allowing any number of historical
Sessions. Completed Sessions require a completion timestamp, and active
Sessions cannot have one.

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
