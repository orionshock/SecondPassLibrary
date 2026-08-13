# Marginalia-Linked Books: Visibility and Preservation

> **Immutable core policy for AI coding agents.** This file is authoritative and must not be edited, regenerated, consolidated, renamed, or deleted. If an implementation, test, API, SDK, Product UI behavior, or other document disagrees with this policy, stop and adjust the implementation and its dependent boundaries to comply. Do not resolve disagreement by weakening or changing this file.

## Authority and audience

This document owns the relationship between current Library visibility, user-owned historical Marginalia, Book openability, visibility-dependent mutation, staged import matching, export, and Book deletion. It applies to Marginalia backend/API, SDK/Product UI, import/export, interchange, and test work.

[Marginalia](marginalia.md) owns the general Reading Session, annotation, import, and export lifecycles. The [Marginalia export specification](specs/marginalia-export.md) and [Reading Session and Annotation profile](specs/reading-session-annotation-profile/README.md) own exact interchange structure. This document owns the visibility and preservation boundary across those workflows.

Do not use `MarginaliaBookVerse` as product vocabulary. The canonical term is **Marginalia-linked Book**.

## Three separate concepts

These concepts must not be collapsed:

1. A **Library-visible Book** is currently available through the canonical Library visibility policy.
2. A **Marginalia-linked Book** is an existing Book referenced by at least one Reading Session owned by the user.
3. An **Openable Book** is both Marginalia-linked and currently Library-visible. The API represents this with `can_open`, adapted by the SDK to `canOpen`.

**Owned Marginalia** means Reading Sessions and annotations owned by the user, independent of current Library visibility.

The Library-visible and Marginalia-linked sets overlap, but neither contains the other.

| Example | Library-visible | Marginalia-linked | Openable |
|---|---:|---:|---:|
| Visible Book with no owned Session | Yes | No | Not present in Marginalia Books, but a Session may be opened |
| Visible Book with an owned Session | Yes | Yes | Yes |
| Inaccessible Book with historical owned Session | No | Yes | No |
| Inaccessible Book with no owned Session | No | No | No |
| Deleted Book | No | No surviving link | No |

A Shelf, stage, or owned Session is not a grant of current Library authority. Conversely, current Library visibility does not imply that Marginalia already exists.

## Marginalia-linked Book definition

A Marginalia-linked Book is:

> An existing Book referenced by at least one Reading Session owned by the user.

Ownership comes from the Session's user relationship, not from current Group membership. The Book must still exist because the Reading Session relation is required and cascading; there is no detached or nullable Book state.

Another user's Session does not put the Book in the current user's Marginalia-linked set. Possession of a Session UUID, Book UUID, stage reference, or exported identifier does not transfer ownership.

## `can_open` truth table

`can_open` is calculated from current, uncached Library visibility. It is not copied from an old Session, persisted as historical truth, or inferred in React.

| Owned Session for Book | Currently Library-visible | Marginalia Book row | `can_open` | May create/open new linked activity |
|---:|---:|---:|---:|---|
| No | Yes | No | Not applicable | Yes, subject to normal Session lifecycle |
| Yes | Yes | Yes | `true` | Yes, subject to lifecycle rules |
| Yes | No | Yes | `false` | No, except the narrow ownership-only operations below |
| No | No | No | Not applicable | No |
| Foreign Session only | Either | No ownership-derived row | Not applicable | Only according to the user's own Library visibility, never the foreign Session |
| Book deleted | No | No | Not applicable | No |

The Product UI may suppress Book navigation when `canOpen` is false, but the backend calculation is authoritative. `can_open=false` does not make owned history unreadable.

## Historical projection

Loss of Library access does not delete or hide user-owned Reading Sessions and annotations from their owner.

Historical Marginalia projections currently use the live Book record rather than a frozen metadata snapshot. They may include the current:

- Book identity needed by the owned Marginalia projection;
- title;
- authors;
- Series summary where that projection includes it;
- public cover URL;
- `can_open` state.

Consequently, later title, author, Series, or cover changes may alter what the user sees alongside old Sessions. Do not describe this data as an immutable historical Book metadata snapshot.

The projection is bounded. Marginalia ownership does not reveal:

- EPUB/file bytes;
- storage paths;
- private Group names or assignments merely because access was lost;
- another user's Sessions or annotations;
- unrestricted Book mutation authority.

The Book link/action is suppressed when `can_open=false`. A public cover URL remains subject to the public-display-asset policy in [Library Book Visibility](book-visibility.md).

## Reading Session operation matrix

| Operation | Requires Session ownership | Requires active Session | Requires current Library visibility | Result after access loss |
|---|---:|---:|---:|---|
| List/detail/history read | Yes | No | No | Allowed |
| Open existing active or create new Session | User becomes owner | New/current active | Yes | Denied with anti-enumerating Book behavior |
| Start over | Yes if finalizing current active | Creates a new active Session | Yes | Denied |
| Edit Session title | Yes | Yes | No | Allowed while still active |
| Edit Session note | Yes | Yes | No | Allowed while still active |
| Update or clear progress | Yes | Yes | Yes | Denied |
| Close without new progress | Yes | Yes | No | Allowed |
| Close with new progress | Yes | Yes | Yes | Denied atomically |
| Reopen a closed Session | Not supported | Closed cannot become active | Not applicable | Not supported |
| Delete one Session | Yes | No; active and closed are eligible | No | Allowed |
| Export | Yes | No | No | Allowed |

### Durable Session rules

- There is at most one active Session for a user/Book pair.
- A user may have multiple closed historical Sessions for the same Book.
- Active and closed are lifecycle states, not visibility states.
- Session title and note may be edited only while the Session is active/open.
- Closed Sessions cannot edit title or note.
- Imported Sessions may receive title and note during import creation according to the archive contract, including when created as closed history.
- Progress changes require current uncached Book visibility.
- Closing without new progress remains available after access loss so the owner can finish the lifecycle without opening the Book.
- Closing with progress rechecks visibility before committing any supplied metadata or progress; denial rolls the whole close attempt back.
- A repeated identical close may return the already-closed result under the existing idempotent retry contract. It does not reopen or rewrite history.
- Start over finalizes an active Session and creates a new blank active Session. When only closed history exists, it may create a new Session; it never changes a closed Session back to active.
- An owner may permanently delete exactly one active or closed Session per
  request. This is an ownership-only lifecycle operation and does not require
  current Book visibility.

### Owner Session deletion

The normal server API supports permanent deletion of one owned Reading Session
as a single-resource operation, with the intended shape
`DELETE /api/v1/marginalia/sessions/{session_id}/`. There is no bulk Session
deletion API and no delete-all-Sessions or delete-all-history operation.

The server owns the complete destructive transaction. One request authorizes
the Session by ownership and atomically deletes that Session together with all
of its annotations through the relational cascade. The client must not delete
annotations separately, issue multiple destructive requests for one Session,
or infer whether cascade cleanup completed. Success means the complete
Session-owned collection was deleted; failure must not expose a partially
deleted Session collection.

Deletion may target an active or closed Session. It is permanent and cannot be
undone. It does not delete the associated Book, another Session, or annotations
owned by another Session. Deletion does not close, reopen, replace, or create a
Session.

Current Book visibility is not deletion authority. The owner may delete a
Session after losing visibility to its linked Book, while a foreign user may
not delete it regardless of their Book visibility or role. Missing and foreign
Session identities follow the normal bounded anti-enumeration contract.

## Annotation operation matrix

| Operation | Requires ownership | Requires active Session | Requires current Library visibility | Access-loss behavior |
|---|---:|---:|---:|---|
| Read current annotations | Yes | No | No | Allowed |
| Create/upsert | Yes | Yes | Yes | Denied |
| Update through upsert | Yes | Yes | Yes | Denied |
| Soft delete | Yes | Yes | Yes | Denied |
| Restore through upsert/client identity | Yes | Yes | Yes | Denied |
| Batch mutation | Yes | Yes | Yes | Atomic denial |
| Export | Yes | No | No | Allowed |

Annotation deletion is a mutation even though it is represented as soft deletion. A user who lost Book visibility may read retained annotations but cannot delete, restore, or modify them until visibility returns and the owning Session is active.

Those individual annotation-mutation rules do not restrict owner deletion of
the entire Session. Session deletion is the separate server-owned lifecycle
operation above; its cascade permanently removes the Session's annotations
without client-orchestrated annotation requests.

Batch operations are atomic. A mixed batch must not partially commit around a lifecycle or visibility failure. Portable/client identifiers support replay and upsert semantics but are scoped to the owning Session; they are not global capabilities.

Reading-order sorting is distinct from creation-time ordering. Location-bearing annotations sort according to the canonical reading-location rules with stable fallbacks. Do not replace that order with incidental database insertion order.

## Access-loss lifecycle

Membership removal, Book assignment removal, Group deletion, or another Library policy transition may move a Book outside the user's current Library-visible set.

When that happens:

- owned Sessions remain stored and readable;
- owned annotations remain stored and readable;
- the Book remains in the Marginalia-linked set while it exists and an owned Session references it;
- `can_open` becomes false on current uncached projections;
- Product UI Book navigation is suppressed;
- new Session creation/open and start-over are denied;
- progress mutation is denied;
- annotation create/update/delete/restore is denied;
- title/note editing remains possible only for an active owned Session;
- close without new progress remains possible;
- close with new progress is denied without partial metadata persistence;
- owner deletion of one active or closed Session remains possible;
- export remains available;
- previously valid personal Shelf retention follows [Library Book Visibility](book-visibility.md), not Marginalia ownership.

Access loss is an expected product lifecycle, not data corruption and not an instruction to clean up historical Marginalia.

## Access restoration

If Group membership, Book assignment, or broad role authority later restores Library visibility:

- `can_open` becomes true on the next authoritative projection;
- the Book becomes navigable again;
- visibility-dependent mutations resume if their Session lifecycle conditions are also satisfied;
- a closed Session remains closed and cannot be reopened;
- a new or start-over Session may be created according to the normal one-active-Session rule;
- retained unavailable personal Shelf items may become available again;
- an Unmatched import artifact can be re-imported and matched normally.

Restoration does not undo an operator cleanup that already removed a retained
Shelf item, and it does not recreate data destroyed by owner Session deletion,
Book deletion, user deletion, or Admin repair.

## Import matching and privacy

A staged import belongs to one user, expires according to the stage policy, and is not a cross-user capability.

Matching uses staged identity, including the supplied exact file checksum, and current Library state. A candidate can be classified as:

- `not_found`: no matching Book identity is known;
- `ambiguous_match`: the match cannot be resolved uniquely under the current matching contract;
- `book_inaccessible`: the supplied identity resolves to a known Book outside the user's current Library-visible set.

A **known but inaccessible staged Book** is not an applyable match. It enters the existing Unmatched flow.

The `book_inaccessible` classification is a narrow, deliberate disclosure: the server may establish that the user-supplied identity is known, but the response presents only data already contained in the user's stage. It must not return fresh hidden:

- Book UUID;
- live title or authors;
- Group names, memberships, or assignments;
- storage identity or path;
- EPUB content;
- another user's Marginalia.

Staged title, authors, identifiers, checksum fields, Sessions, and annotations may be displayed or preserved because the importing user supplied them.

## Apply-time authority and partial apply

Preview is not mutation authority. Apply rechecks every selected matched Book against current uncached Library visibility inside the apply transaction immediately before creating Marginalia.

The candidate-level contract is:

- selected candidates that remain visible apply normally;
- a candidate that lost visibility after preview moves into the result's Unmatched set with reason `book_inaccessible`;
- no Session, annotation, import marker, or other candidate data is created for that inaccessible candidate;
- other selected accessible candidates continue to apply;
- candidate-level access loss is a successful partial-apply outcome, not a transaction-wide 403;
- historical Marginalia created while access was valid remains untouched.

True structural failures remain transaction-wide failures. These include malformed or corrupt staged data, a missing formerly matched Book, missing required staged payload, invalid ownership, invalid/expired stage state, and persistence failure. Do not turn structural corruption into a partial-success model.

After a successful full or partial apply:

- the stage is consumed/applied;
- the result records applied and unmatched outcomes in deterministic staged order;
- identical replay returns the stored result without duplicate Sessions or annotations;
- a changed selection or changed replay request is rejected;
- the staged file is deleted after commit when no unmatched download remains;
- it is retained when the stored result still offers an Unmatched download;
- retrying inaccessible candidates requires downloading that artifact and importing it again later.

The stage must not remain “ready” after partial mutation; that would allow replay to duplicate the accessible candidates.

## Unmatched artifact

The Unmatched download is the existing portable retry mechanism. It is built from staged/import-owned data, not from unrestricted fresh Book queries.

It preserves the portable Session and annotation content needed for a later import, together with the staged Book identity fields permitted by the archive format. It does not add hidden live Book UUIDs, Group state, current visibility detail, server paths, or newly fetched metadata.

The internal/result reason may remain `book_inaccessible` even when the portable interchange schema does not encode server-local matching reasons. Re-import performs matching again against then-current Library state rather than trusting the old outcome.

## Export behavior and limits

Marginalia export is based on owned Sessions, not current Library visibility.

- Complete export includes eligible Sessions owned by the requesting user.
- Selected export resolves only Sessions owned by the requesting user.
- Inaccessible historical Books remain exportable.
- Foreign and nonexistent selected IDs use the same bounded anti-enumerating behavior.
- Export does not grant Book download or Group access.
- Deleted/soft-deleted annotations follow the canonical archive inclusion rules.

The archive uses current live Book checksum, title, and authors once per represented Book. It is not a frozen historical metadata snapshot. Multiple Sessions for one Book follow the archive's distinct-Book metadata representation rather than multiplying Book metadata accidentally.

Synchronous export is intentionally bounded for the single-worker home-lab deployment:

| Limit | Value |
|---|---:|
| Selected Session IDs | 500 |
| Sessions in a complete export | 5,000 |
| Included annotations | 50,000 |
| Estimated archive size | 16 MiB |
| Final serialized archive size | 16 MiB |

Count and estimate checks reject known-oversized work before archive materialization where possible. The final serialized-byte guard remains authoritative for residual encoding or estimation differences. Oversized responses are bounded and actionable without returning identifiers, contents, or other users' counts.

Exact archive structure and version linkage belong to the [export envelope specification](specs/marginalia-export.md) and [profile schema](specs/reading-session-annotation-profile/README.md).

## Access loss, restoration, and deletion matrix

| State change | Sessions | Annotations | `can_open` | New mutations | Export |
|---|---|---|---:|---|---|
| Current visibility retained | Preserved | Preserved | `true` for linked Book | Allowed by lifecycle | Allowed |
| Library access lost | Preserved and readable | Preserved and readable | `false` | Only ownership-only exceptions | Allowed |
| Library access restored | Preserved | Preserved | `true` | Resume where Session lifecycle permits | Allowed |
| Session closed | Historical/readable | Historical/readable | Based on current Book visibility | Session/annotation mutations remain closed | Allowed |
| Session deleted by owner | Removed | Cascades | Book may remain linked through other Sessions | Other Sessions follow normal rules | Remaining owned data only |
| Book deleted | Cascades away | Cascades through Sessions | Not applicable | Impossible | No surviving linked data |
| User deleted | Cascades owned Sessions | Cascades through Sessions | Not applicable | Impossible | No owned data |
| Session deleted by Admin repair | Removed | Cascades | Book may remain linked through other Sessions | Other Sessions follow normal rules | Remaining owned data only |

## Deletion boundary

**Preservation applies to Library access loss, not Book deletion.**

Current model behavior is deliberately relational:

- the Reading Session-to-Book relationship is required;
- Book deletion cascades to linked Reading Sessions;
- Session deletion cascades to annotations;
- user deletion cascades owned Reading Sessions and their annotations;
- no detached, orphaned, or null-Book Marginalia state exists;
- the normal server API may delete exactly one owned Session per request,
  including after current Book visibility is lost;
- no bulk or delete-all Session/history operation exists;
- Django Admin deletion remains an independent destructive repair action, not
  an owner-facing history-management workflow.

Durable owned history remains preserved across access loss until the owner
explicitly deletes an individual Session or another documented lifecycle event
removes it. Do not change the required relationship or invent detached-history
behavior without an explicit product decision outside normal implementation
work. Do not claim that the access-loss preservation invariant protects against
deliberate Session, Book, or user deletion.

## Privacy, anti-enumeration, and logging

Ownership governs historical reads. Current Library visibility governs openability and most new mutations. Both must be checked at backend query/service boundaries.

Durable privacy rules:

- foreign users cannot read or mutate another user's Sessions, annotations, stages, results, or exports;
- foreign and missing identifiers should converge where acknowledging existence would leak data;
- staged matching never returns fresh hidden Book metadata;
- `can_open` exposes only the current yes/no openability of a Book already linked through the user's own history;
- Marginalia ownership does not expose EPUB bytes, storage paths, Group assignments, or another user's history;
- Session deletion authorizes against ownership on the server and never trusts
  Product UI filtering or current Book visibility;
- apply and export must not trust Product UI selection as authority.

Domain logs may contain bounded lifecycle summaries, user identifiers, short stage references, counts, and expected conflict reasons where operationally useful. They must not contain titles, annotations, archive payloads, staged filenames or paths, full stage tokens, hidden Book identifiers, Group details, credentials, or response bodies. Expected inaccessible/unmatched outcomes are normal product events, not exception-level failures.

## Import/export authority matrix

| Workflow | Ownership boundary | Current visibility boundary | Privacy outcome |
|---|---|---|---|
| Preview stage | Stage owner | Used for current match classification | Only staged metadata returned for inaccessible Books |
| Apply accessible candidate | Stage owner | Uncached check inside transaction | Session/annotations created once |
| Apply newly inaccessible candidate | Stage owner | Uncached check fails | Candidate becomes Unmatched; no Marginalia created |
| Download Unmatched artifact | Stage/result owner | No fresh hidden Book lookup | Staged portable data only |
| Re-import after restoration | New stage owner | Matching uses restored current visibility | Candidate can become normally matched |
| Complete export | Session owner | Not required | Owned history included within limits |
| Selected export | Session owner | Not required | Foreign/missing IDs do not leak |

## Related authorities

- [Library Book Visibility](book-visibility.md) owns the current visible Book set, cache, Shelf eligibility, and download boundary.
- [Advanced Library Groups Mode](advanced-library-groups.md) owns Advanced/Simple presentation and custom Group mutation policy.
- [Marginalia](marginalia.md) owns the general domain lifecycle.
- [Permissions](permissions.md) owns broader role and Group authority.
- [Library Imports](imports.md) owns Library EPUB/archive import safety, not Marginalia interchange matching.
- [Operations](operations.md) owns cleanup and destructive repair procedures.
- [Marginalia export specification](specs/marginalia-export.md) owns the export envelope.
- [Reading Session and Annotation profile](specs/reading-session-annotation-profile/README.md) owns reusable interchange semantics and schema links.
