# Shelves

Shelves are ordered presentation/organization collections. They never grant
access to a Book. Role authority is defined in `docs/permissions.md`; exact API
routes and payload fields are defined in `docs/api.md`; detailed page layout is
defined in `docs/ui.md`.

## Concepts and owner types

Every shelf has exactly one owner:

- **User-owned**: owned by one user; may be `private` or `listed`.
- **Group-owned**: owned by one Library Group; visibility follows that group.

User-owned shelves preserve personal organization. Group-owned shelves organize
Books within the owning group's access context.

Shelf visibility and Book visibility are independent. A viewer must first be
allowed to see the shelf, and every returned item/preview must then pass current
Book visibility. Caller-owned and visible group-owned shelves can therefore
have zero visible items without revealing hidden titles or raw item counts.

Personal and group ownership use the same canonical `/api/v1/shelves/`
resources. Their policy code is separated internally, but ownership does not
create alternate mutation routes.

## Visibility and list scopes

The shelf list supports four scopes:

| Scope | Meaning | Empty shelf behavior |
| --- | --- | --- |
| omitted or `all` | All shelves visible to the caller | Combines the rules below |
| `personal` | Caller-owned user shelves | Includes empty shelves |
| `shared` | Listed shelves owned by other users | Requires viewer-visible `item_count > 0` |
| `group` | Visible group-owned shelves | Includes empty shelves |

Scope filtering never bypasses shelf or Book visibility. In particular:

- other users' private shelves are excluded from every scope, including for
  Manager and Owner;
- a listed other-user shelf containing only hidden Books is omitted exactly
  like an empty shared shelf;
- direct detail for an empty or hidden-only listed other-user shelf returns
  `404`, matching list discovery; Librarian+ status does not bypass this rule;
- the owner still sees an empty or hidden-only personal shelf with
  `item_count: 0`;
- a group member or broad role still sees a visible empty group shelf in both
  list and detail views;
- session and bearer reads apply the same visibility policy for their user.

Omitted scope and `scope=all` are equivalent and retain the normal paginated
list envelope. Scope composes with supported group, Book, ordering, preview,
and pagination parameters as documented in `docs/api.md`.

## Viewer-visible counts and previews

`item_count` is the number of shelf Books visible in the current request
context, not the raw number of stored `ShelfItem` rows.

`preview_books`, when requested, is derived from the same viewer-visible item
set. Preview rows never disclose hidden Books, file/download metadata, storage
paths, source names, checksums, reading data, or raw shelf-item state. Shelves
do not become Book-access scopes merely because they return previews.

Filtering shelves by Book also uses visible items only. Hidden items do not
cause a match and do not expose their item identifiers.

## Shelf items and ordering

A `ShelfItem` relates one Book to one shelf and stores a zero-based position.
A Book appears at most once per shelf.

Shelf item API rows keep item identity, shelf identity, position, and `added_by`
outside the nested Book. The nested Book uses the shared compact catalog shape,
including ordered Authors, Series/index, Catalog Tags, publisher, cover, and
file format, while excluding detail, file/download, checksum, and
storage/source/provenance fields.

Positions remain contiguous. Item mutations lock the Shelf and its stored item
rows before changing order. Add, remove, group-assignment cleanup, and explicit
unavailable-item cleanup compact the remaining order. Duplicate/colliding
requested positions are canonicalized deterministically. Product UI may display
one-based positions while the stored and API position remains zero-based.

Shelf lists accept name and viewer-visible item-count ordering in either
direction. Normal item reads accept stored position, title, and author ordering
in either direction. These read orderings do not mutate stored positions.
Editor inventory remains stored-position-only because its locked unavailable
placeholders describe the mutation order rather than an alternate presentation.

Deleting a shelf deletes its ShelfItems only. It never deletes Books, stored
EPUB files, reading sessions, or annotations.

Shelf writes are strict: unknown create/update/item fields return structured
validation errors. Shelf names are limited to 255 characters, Group-owned
creation requires `owner_group`, metadata updates use PATCH, and PUT is not
supported. User-owned creation rejects `owner_group` rather than silently
ignoring the contradictory owner. Create returns the complete Shelf summary,
including viewer-visible `item_count` (`0` for a new shelf). Adding an item uses
the `book` UUID field; missing or inaccessible Books collapse to the same
not-found response after Shelf edit authority is established. Adding a Book
that is already present returns a structured `book` field error. Malformed
Shelf item ids collapse to the same `404` as missing items.

## User-owned shelf item retention

A Book must be visible to the editor when it is added to a user-owned shelf.
Later access loss does not delete that stored item automatically. This preserves
the shelf owner's durable organization until an explicit cleanup decision.

Normal reads hide the unavailable Book and return visibility-scoped counts and
previews. Editors may explicitly request
`GET /api/v1/shelves/<id>/items/?view=edit` to receive every stored slot in
position order. Visible rows contain the compact Book; retained unavailable
rows contain `book: null`, `unavailable: true`, and only bounded ShelfItem
metadata. Pagination counts all stored slots and additionally reports visible
and unavailable counts. Non-editors cannot request this representation.

Unavailable placeholders are locked. PATCH/move operations on one still return
the normal not-found response. Moving a visible row up or down swaps it with the
nearest visible row while skipping placeholders and leaving placeholder
positions fixed. Direct positioning, and explicit-position adds, return a
structured `position` error while a Shelf contains unavailable rows. A
positionless add appends after every stored slot. The Shelf owner may still
DELETE a retained item by its known ShelfItem id; deletion reveals no Book
metadata.

## Group-owned shelf item behavior

Group-owned shelf writes require edit authority for the owning group, and added
Books must satisfy the group shelf's supported Book constraints.

When a Book is removed from a Library Group, the explicit group-shelf hook
removes that Book from shelves owned by the same group and compacts their
positions. It does not alter user-owned shelves or shelves owned by another
group.

Public group shelves remain meaningful in simple and advanced modes. Public has
no curator memberships, so Public shelves are managed by Librarian, Manager, or
Owner. Custom-group Reader curators may manage shelves only for their exact
custom group.

## Mutation authority and bearer boundary

Session-authenticated Product UI/API authority follows `docs/permissions.md`:

- owners manage their own user shelves;
- broad roles manage group shelves;
- an exact custom-group Reader curator manages that group's shelves.

Client bearer tokens have a narrower mutation boundary:

- they may read any shelf visible to the token user;
- they may create/edit/delete the token user's personal shelves;
- they may add/remove/reorder items only in those personal shelves;
- group-owned shelves and other users' shelves are read-only and report
  `can_edit: false`.

The same user may receive a different `can_edit` hint under session auth for a
group shelf. The API remains authoritative in both contexts.

## Product UI workflows

The Shelves page presents explicit Personal, Shared by Others, and Group
Shelves tabs. Empty Personal and Group Shelves rows remain; empty/hidden-only
Shared by Others rows do not appear.

Shelf View presents visible Books and safe shelf description/ownership context.
Shelf Edit uses Details, Books, and Add Books tabs. Personal Shelf candidates
use broad library Book search with `exclude_shelf`. Group Shelf candidates use
the owning Group's Book endpoint with `exclude_shelf`, so candidates remain
group-eligible while already-contained Books are suppressed by the server.
Delete Shelf uses a collapsed disclosure and a final browser confirmation.

User-owned shelves may retain unavailable items. Their stored positions remain
intact; mutation UI must not silently collapse those positions or expose hidden
Book metadata. Reorder UI for this locked-placeholder model remains deferred.

Book Detail/Edit may surface shelves containing the Book, and Group View/Edit
may surface group-owned shelves. Those relationships do not change shelf or
Book visibility. Pager, row, icon, and responsive details remain in
`docs/ui.md`.

## `cleanup_shelves` maintenance policy

Unavailable user-owned shelf items are removed only by an explicit operator
cleanup. The command is intended for host scheduling (cron, systemd timer, or
equivalent); the application does not run it implicitly.

```powershell
python manage.py cleanup_shelves
python manage.py cleanup_shelves --apply
```

The default invocation is a dry run. It reports affected user-owned shelves and
unavailable item counts without changing data.

`--apply` performs the cleanup transactionally:

- removes only user-owned shelf items whose Book is unavailable to that shelf
  owner;
- compacts remaining positions;
- does not include group-owned shelves;
- does not change group membership or assignment propagation;
- does not delete Books, files, or reading data.

Deployment scheduling guidance is in `docs/deployment.md`.

## Non-goals

- Shelves are not access control.
- There is no anonymous/public shelf browsing contract.
- Client bearer tokens do not mutate group or other-user shelves.
- Cleanup is not a live request-time side effect.
