# Marginalia

## Scope and ownership

Marginalia is user-owned reading data: Reading Sessions, saved progress, and
located annotations. Every Reading Session belongs to one user and one Library
Book; every annotation belongs through its Session and does not duplicate user
or Book ownership.

Ownership of historical Marginalia and current authority over the linked Book
are separate:

- the owner may read their existing Sessions, progress, and annotations after
  losing Library visibility;
- current visibility determines whether the Book can be opened and whether new
  linked reading activity may be created;
- writes that establish a new location or annotation recheck current Book
  authority at the service boundary;
- historical ownership never grants EPUB download, Book mutation, Group,
  Shelf, or general Library access.

Marginalia reads expose a bounded Book identity needed to understand owned
history. `can_open` is computed independently from current uncached Library
visibility. Missing Books and Books without caller-owned history use the same
not-found treatment, and historical projections do not expose EPUB/file data,
checksums, download URLs, Groups, Shelves, or permission internals. Broader
Book and Group visibility is defined in [Permissions](permissions.md).

Loss of visibility is not deletion. Removing Group membership or a Book
assignment must not destroy user-owned Marginalia. Deleting the actual user,
Book, or Session is different: database relationships cascade through its
Sessions or annotations and is therefore an operator-level destructive action.

## Reading Session lifecycle

A Reading Session is either `active` or `closed`. Status is authoritative:
active Sessions have no close timestamp; closed Sessions have one. A database
constraint permits at most one active Session for a user and Book, while any
number of closed historical Sessions may coexist. There is no archived state
and no reopening transition.

Opening a visible Book returns the existing active Session unchanged or creates
one when none exists. It never replaces or implicitly closes an active Session.
Starting over requires current Book access and atomically closes the current
Session, optionally finalizes its metadata and progress, and creates a blank
active Session. The old Session keeps its progress and annotations. User-scoped
start-over idempotency keys are retained for 24 hours: an identical replay
returns the stored success, while reuse for changed input or an in-progress
operation is a conflict.

Only active Sessions accept metadata, progress, or annotation changes. Session
name and notes may be updated on the owned active Session. Progress is one
complete saved location stored on the Session: an opaque CFI, an optional
display label, and a server/source timestamp. Marginalia does not parse,
normalize, derive, or assign numeric meaning to CFIs or labels.

Progress replacement requires current Library access. Closing is explicit and
does not create a replacement Session. Final metadata, optional final progress,
and closure commit atomically under the Session mutation boundary. A close
without new progress may complete after Book access is lost; supplying final
progress still requires current access because it is a live location write.
An identical close retry is safe, while an attempt to alter an already-closed
Session is rejected.

History is ordered by latest meaningful activity: Session metadata, saved
progress, or a current non-deleted annotation, with stable start/id fallbacks.
Reads do not update activity timestamps.

## Annotation lifecycle

Annotations are owned through their Reading Session and have one of two kinds:

- a highlight has selected text and may include quote context, color, and a
  user note;
- a bookmark has a location but no highlight body or comment content.

Every annotation has an opaque CFI, an optional bounded location label, and a
portable `client_id` unique within its Session. Client identity is not global
and is distinct from the local database UUID.

Annotation synchronization is an atomic batch against an owned active Session.
The service locks/rechecks the Session and current uncached Book visibility
before mutation. Any invalid operation, closed Session, or lost authority
leaves the whole batch unapplied. Upsert by `client_id` creates, updates, or
restores the same row without duplication; deleting an unknown or already
deleted identity is a retry-safe no-op.

Deletion is soft deletion. Deleted annotations remain storage state but are
excluded from ordinary reads, activity, counts, import/export empty-Session
policy, and archive serialization. A later upsert of the same Session-scoped
client identity restores the row.

The authoritative collection uses stable reading order. Nonblank location
labels sort first and lexically; blank labels fall back to CFI, creation time,
and server identity. Marginalia does not attempt to interpret that ordering as
EPUB structure. Active and closed collections remain readable by their owner
after Book visibility changes, but closed Sessions cannot be synchronized.

## Visibility and preservation

Owned Marginalia is durable personal history. Current Library visibility is
required for opening a Book, creating a linked active Session, starting over,
writing progress, and synchronizing annotations. Each such mutation asks the
canonical uncached Library visibility query at its service boundary; React
state, an earlier query, or a cached preview is never authority.

Reading existing Sessions, progress, and current annotations depends on
ownership, not current Book visibility. Closing without a new progress value
also preserves this distinction. `can_open=false` communicates that the Book is
not currently available without hiding or deleting the owner's history.

This historical projection is deliberately bounded. It may retain the linked
Book's identity, title, authors, Series, and public cover needed to recognize
owned history, but it does not broaden Library permissions. Other users'
Sessions and annotations are filtered before search, counts, ordering, or
nested data are calculated. Missing, foreign, and otherwise unowned objects use
the established no-enumeration response.

Exports include owned historical Marginalia even when `can_open` is false.
Imports are stricter because they create new linked history: the Book must be
currently visible at the mutation boundary.

## Import workflow

Marginalia import is a staged, preview-before-apply workflow for the canonical
archive format. An uploaded archive is bounded to 25 MiB, strictly validated,
and stored under an opaque, user-bound stage for two hours. Preview creates no
Sessions or annotations. Stage ownership, expiry, token format, stored archive,
and preview consistency are checked without disclosing whether another user's
stage exists. Cleanup scheduling and command usage belong in
[Operations](operations.md#marginalia-import-stages).

Book matching uses the canonical `fileHash` identity only; title, author,
identifier, and CFI values are not matching fallbacks. Preview distinguishes:

- `not_found`: no Book has the supplied identity;
- `ambiguous_match`: more than one currently visible Book has it;
- `book_inaccessible`: a Book identity exists but is not currently visible.

`book_inaccessible` deliberately confirms that the exact archive-supplied hash
is known. The privacy boundary is that it reveals no fresh live metadata,
database identity, or access-scope details.

Matched and visible candidates may be selected. Unmatched candidates cannot be
applied. For an inaccessible Book, the workflow retains only the title, Authors,
file hash, Sessions, and annotations supplied in the user-owned staged archive.
Preview/results expose bounded staged summaries rather than annotation contents
and never fetch or return the hidden live Book UUID, metadata, Groups,
assignments, or storage details. Possible duplicate Sessions are warnings, not
automatic merges or suppression.

Apply locks the stage, validates the complete selection and canonical archive,
and rechecks each selected Book through the uncached visibility query inside
the apply transaction immediately before creation. Accessible candidates are
created as new closed Sessions; canonical source timestamps, progress, portable
annotation identities, and annotation content are preserved. A source-active
Session is deterministically closed at its source `updatedAt`. Import does not
replace, reopen, close, or otherwise mutate an existing active Session.

If a selected Book becomes inaccessible after preview, that candidate creates
no Session or annotation. It is reclassified as `book_inaccessible` in the
existing Unmatched result while other accessible candidates apply. This is a
successful partial apply, not a transaction-wide permission failure. A missing
Book, corrupt or inconsistent stage/archive, invalid selection, or persistence
failure remains structural: the transaction rolls back and the ready stage can
be corrected or retried as allowed by its original lifetime.

A successful full or partial apply consumes the stage. Its request fingerprint
covers the effective selected candidates and overrides independent of request
ordering. An identical replay returns the stored result without duplicating
Sessions or annotations; changed replay input is rejected. This protection is
stage-specific: importing the same archive through a new preview remains an
explicit user choice and may produce duplicate advisories.

The staged file is deleted after commit only when no downloadable Unmatched
content remains. Otherwise it is retained until normal stage expiry so the
Unmatched artifact can be downloaded. Unselected matched candidates are not
silently imported or converted into Unmatched content. After access is
restored, retrying inaccessible candidates requires downloading their artifact
and importing that canonical content through a new preview.

The Unmatched artifact is deterministic and importable through the normal
workflow. It contains only staged/import-owned Book metadata, Sessions,
progress, annotations, and portable identities. It never rematches at download
time or adds hidden live Book data, local Book UUIDs, Group state, filenames,
paths, or tokens.

## Export workflow

Complete and selected exports contain only the requesting user's Sessions and
non-deleted annotations. Selected identities must be unique and all owned by
the requester; missing and foreign identities share the same not-found
boundary, and no partial archive is returned. Current Book visibility does not
exclude owned historical data.

Exports use the canonical deterministic JSON archive. Sessions without current
annotations are excluded by default; callers may explicitly include them.
Missing Book checksums or conflicting duplicate hashes are integrity failures,
not an invitation to merge Books. Export is read-only, creates no persistent
file, and emits no partial attachment after failure.

Synchronous buffering is deliberately bounded for the supported single-worker
home-lab deployment:

- at most 500 selected Session IDs;
- at most 5,000 Sessions in a complete export;
- at most 50,000 non-deleted annotations;
- at most 16 MiB by conservative database-side estimate and by final serialized
  UTF-8 bytes.

The estimate includes serialized Session and annotation text plus each
represented Book's checksum, title, and Author names using conservative JSON
escaping allowances. Count limits run before archive materialization; the final
16 MiB byte check remains authoritative. Oversized work returns a bounded,
actionable error directing the user to export a smaller selection without
revealing another user's data or archive contents.

## Replay, idempotency, and integrity

Replay protection belongs at the operation boundary rather than changing the
portable domain model:

- opening converges on the single active Session constraint;
- start-over uses a short-lived user-scoped idempotency record;
- annotation upsert/delete converges on a Session-scoped client identity;
- staged Apply stores a request fingerprint and result for identical replay.

Changed replays are conflicts, structural failures roll back their transaction,
and candidate-level access loss produces only the explicit Unmatched outcome.
No cross-user stage, Session, annotation, or export access is permitted. A
fresh import is not globally deduplicated: its possible-duplicate signal remains
advisory so the user controls whether another historical Session is created.

## Logging and privacy

Marginalia logs may record bounded lifecycle summaries, counts, expected
conflicts, cleanup failures, and unexpected integrity/storage failures at
appropriate levels. Expected unmatched or inaccessible import outcomes are
normal product events, not exception-level failures.

Never log annotation or note contents, progress locations, archive payloads,
stage tokens, upload/download bodies, hidden Book metadata, filenames, storage
paths, credentials, or full request data. General repository logging rules are
in [AGENTS.md](../AGENTS.md#logging-and-maintenance).

## External specifications

Exact archive and interchange structures are normative outside this domain
overview:

- [Marginalia export archive](specs/marginalia-export.md) owns the portable
  archive envelope and Book grouping.
- [Reading Session and Annotation profile](specs/reading-session-annotation-profile/README.md)
  owns exact Session, progress, location, highlight, bookmark, and portable
  identity shapes.

The executable schema lives beside the backend archive codec. Documentation
schemas and reference types describe the external contract but are not loaded
by runtime code or tests.
