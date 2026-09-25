# Marginalia

## What Marginalia contains

Marginalia is user-owned reading data: Reading Sessions, saved progress, and
located annotations. Every Reading Session belongs to one user and one Library
Book; every annotation belongs through its Session and does not duplicate user
or Book ownership.

Historical Marginalia ownership is separate from current access to the linked
Book. The immutable [Marginalia-Linked Books](marginalia-book-visibility.md)
policy defines what users may read, open, change, import, and export after
access changes or a Book is deleted. [Library Book
Visibility](book-visibility.md) defines the current visible Book set. This guide
describes the general lifecycle without changing either policy.

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
start-over idempotency keys have a 24-hour replay window. The key namespace is
shared by all such requests from the same user rather than being scoped to one
Book. Method, full path, and validated body are part of the identity: an
identical replay returns the stored success, while reuse for another request
or a retry made while the first request is still processing returns a
conflict. Once the window expires, the key may be used again.

`POST /api/v1/marginalia/books/{book_id}/open/` always returns an active
Session. It returns the one already active for that user and Book or creates
one; the database prevents multiple active Sessions for the pair.
`GET /api/v1/marginalia/books/{book_id}/active-session/` is the read-only way
to ask whether one exists and may return `null`.
`POST /api/v1/marginalia/books/{book_id}/start-over/` is an intentional
new-reading-pass action, not a recovery mechanism for an ordinary
closed-session write. All three are supported Reader operations when the Book
is currently visible.

Only active Sessions accept title, note, progress, or annotation changes.
Progress is one saved location stored on the Session: a `location`, an optional
display label, and a server/source timestamp. For EPUB Books, the location is a
syntax-validated CFI stored unchanged as the durable anchor; the exact accepted
subset and behavior belong to the [EPUB Location Profile](specs/epub-location.md).
`locationLabel` is persisted display text, not a second position or identity
field.

The Reader may show a richer live label while a Book is open, such as
`Dedication • p1/2 • 1%`. Page fragments describe the current rendition and are
not saved. New saved labels use the stable `PPP% - Label` form described in the
[interchange contract](specs/marginalia.md#saved-location-labels).
Historical labels remain valid display text and are never migrated or
reinterpreted by the server.

Replacing progress requires current Library access. Closing is explicit and
does not create a replacement Session. Final metadata, optional final progress,
and closure commit in one transaction. A close
without new progress may complete after Book access is lost; supplying final
progress still requires current access because it is a live location write.
An identical close retry is safe, while an attempt to alter an already-closed
Session is rejected.

Closing and live writes are serialized as one-or-the-other outcomes. If a
progress or annotation write commits first, it succeeds and closure follows.
If closure commits first, the write makes no changes and returns
`SESSION_CLOSED`. Progress replacement, annotation synchronization, and close
all recheck the active state inside their transaction; an annotation batch is
never partially applied.

Session names are at most 255 characters. Notes have no separate field-level
character limit. On open, close, start-over, and metadata edits, the API trims
leading and trailing whitespace from supplied names and notes. Omitting a
field preserves its current value where the operation updates an existing
Session; explicitly sending an allowed blank value stores an empty string.

An owner may permanently delete exactly one of their active or closed Sessions
through one normal server request, with the intended single-resource shape
`DELETE /api/v1/marginalia/sessions/{session_id}/`. Deletion depends on Session
ownership, not current visibility of the linked Book, so owned history remains
deletable after Book access is lost. Foreign Sessions are never deletable by
the requester. There is no bulk Session deletion API and no delete-all-history
operation.

The server performs the entire destructive operation. It atomically deletes the
Session and all annotations owned through that Session's existing relational
cascade. A client must not delete annotations separately or coordinate a
multi-request deletion. The associated Book, unrelated Sessions, and their
annotations remain untouched. Session deletion is permanent, cannot be undone,
and does not introduce a closed-to-active transition.

History is ordered by latest meaningful activity: Session metadata, saved
progress, or a current non-deleted annotation, with stable start/id fallbacks.
Reads do not update activity timestamps.

## Annotation lifecycle

Annotations are owned through their Reading Session and have one of two kinds:

- a highlight has selected text and may include quote context, color, and a
  user note;
- a bookmark has a location but no highlight body or comment content.

Every annotation has a syntax-validated `location`, an optional bounded location
label, and a portable `client_id` unique within its Session. For EPUB Books, the
self-describing CFI value anchors
the annotation; the label only describes that saved location for display.
Client identity is
not global and is distinct from the local database UUID. The API accepts any
non-whitespace string up to 255 characters and does not require UUID syntax.
Readers should normally generate a UUID v4 because it provides a simple,
collision-resistant identity. The same `client_id` may legally appear in two
different Sessions.

Annotation synchronization is an atomic batch against an owned active Session.
The service locks/rechecks the Session and current uncached Book visibility
before mutation. Any invalid operation, closed Session, or lost authority
leaves the whole batch unapplied. Upsert by `client_id` creates, updates, or
restores the same row without duplication; deleting an unknown or already
deleted identity is a retry-safe no-op.

When a whole batch is rejected with `SESSION_CLOSED`, a Reader should preserve
locally authored, unacknowledged upserts rather than discard them. It may open
the same Book, then replay those upserts as one batch into the active Session
returned by `open`, retaining their `client_id` values. It must not use
start-over for this recovery and must not replay deletes from the historical
Session into the new one. If the Book can no longer be opened, the Reader
should keep the authored annotations locally as unsynced. The server never
moves annotations between Sessions automatically.

Deletion is soft deletion. Deleted annotations remain storage state but are
excluded from ordinary reads, activity, counts, import/export empty-Session
policy, and archive serialization. A later upsert of the same Session-scoped
client identity restores the row.

The first soft deletion records an explicit deletion timestamp; retrying the
same deletion does not renew that clock, and restoration clears it. Registered
maintenance permanently removes expired tombstones. Closed-Session tombstones
use a 7-day default retention, while active-Session tombstones use a more
conservative 28-day default. Both values are configurable Server Settings, and
the task defaults to a Monthly schedule. Operational execution and configuration
are documented in [Operations](operations.md#deleted-marginalia-annotations).

For a highlight body, `text` is the actual selected quotation and is the only
quote text clients should normally display. `prefix` and `suffix` are immediate
surrounding selector context retained for anchoring, matching, repair, and
interchange; clients must not prepend or append them to the visible quotation.
`note` remains separate user-authored annotation text. The server preserves
these fields as supplied and does not normalize their whitespace for display.
Any display-only whitespace treatment belongs to the client and must apply to
`text` alone. The Product UI follows this boundary for both active and closed
Session detail.

Annotation collections use a stable display order. Nonblank location labels
sort first and lexically; blank labels fall back to location, creation time, and
server identity. The server compares the complete label as opaque text. It does
not parse the percentage or suffix, and this ordering is not a substitute for
EPUB navigation or annotation anchoring. Active and closed collections remain
readable by their owner after Book visibility changes, but closed Sessions
cannot be synchronized.

## Visibility and preservation

Owned Marginalia is durable personal history, retained until the owner
explicitly deletes an individual Session or another documented lifecycle event
removes it. Current Book authority is a separate property.
[Marginalia-Linked Books](marginalia-book-visibility.md) is
the sole detailed policy for `can_open`, access loss and restoration, mutation
exceptions, historical metadata projection, anti-enumeration, exports, and
deletion. In particular, do not reduce that contract to “every mutation
requires current visibility”: owned active-Session title/note edits, closing
without new progress, and owner deletion of one Session are documented
exceptions.

## Import workflow

Marginalia import is a staged, preview-before-apply workflow for the canonical
archive format. An uploaded archive is bounded to 25 MiB, strictly validated,
and stored under an opaque, user-bound stage for two hours. Preview creates no
Sessions or annotations. Stage ownership, expiry, token format, stored archive,
and preview consistency are checked without disclosing whether another user's
stage exists. Cleanup scheduling and command usage belong in
[Operations](operations.md#marginalia-import-stages).

Book matching uses the canonical `fileHash` identity only. `fileHash` is
`sha256:<lowercase hex>`, where the digest is calculated from the exact uploaded
EPUB byte stream before parsing and is the same checksum stored on the Library
Book. Export serializes that stored checksum; import compares it directly with
currently stored Book checksums. Title, Author, ISBN, EPUB UID, Calibre ID,
other identifiers, and location values are never matching fallbacks. The same
bibliographic work in a repacked or otherwise byte-different EPUB therefore
remains Unmatched because its annotation locations may not be compatible.
Preview distinguishes:

- `not_found`: no Book has the supplied identity;
- `ambiguous_match`: more than one currently visible Book has it;
- `book_inaccessible`: a Book identity exists but is not currently visible.

For `not_found`, import the exact EPUB represented by the archive before
previewing again. Similar title, Author, or identifier metadata cannot repair a
checksum mismatch.

Second Pass Library exports always include `fileHash`. An imported entry that
omits it remains Unmatched and can be downloaded again; the importer does not
substitute bibliographic metadata for the missing identity.

`book_inaccessible` confirms that the exact archive-supplied hash is known, but
reveals no current metadata, database identity, or access-scope details.

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
covers the selected candidates and overrides regardless of request ordering.
An identical replay returns the stored result without duplicating
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

The single-worker home-server deployment uses these synchronous buffering
limits:

- at most 500 selected Session IDs;
- at most 5,000 Sessions in a complete export;
- at most 50,000 non-deleted annotations;
- at most 16 MiB by conservative database-side estimate and by final serialized
  UTF-8 bytes.

The estimate includes serialized Session and annotation text plus each
represented Book's checksum, title, and Author names using conservative JSON
escaping allowances. Count limits run before archive materialization; the final
16 MiB byte check makes the final decision. Oversized work returns a bounded,
actionable error directing the user to export a smaller selection without
revealing another user's data or archive contents.

## Replay, idempotency, and integrity

Replay protection is applied to each operation without changing the portable
data model:

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

The archive specifications define the exact interchange structures:

- [Marginalia export archive](specs/marginalia-export.md) defines the portable
  archive envelope and Book grouping.
- [Marginalia Interchange Contract](specs/marginalia.md)
  defines exact Session, progress, location, highlight, bookmark, and portable
  identity shapes.

The documentation schemas are the normative external machine-readable
contract. Runtime keeps an offline bundled schema beside the archive codec; a
focused contract test validates the retained examples and checks semantic
parity between the split documentation schemas and that runtime bundle.
