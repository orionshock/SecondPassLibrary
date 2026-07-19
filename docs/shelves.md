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
Book visibility. A visible shelf can therefore have zero visible items without
revealing hidden titles or raw item counts.

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
- the owner still sees an empty or hidden-only personal shelf with
  `item_count: 0`;
- a group member or broad role still sees a visible empty group shelf.

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

Positions remain contiguous. Add, remove, move-up, move-down, move-to-position,
group-assignment cleanup, and explicit unavailable-item cleanup compact the
remaining order. Duplicate/colliding requested positions are canonicalized
deterministically. Product UI may display one-based positions while the stored
and API position remains zero-based.

Deleting a shelf deletes its ShelfItems only. It never deletes Books, stored
EPUB files, reading sessions, or annotations.

## User-owned shelf item retention

A Book must be visible to the editor when it is added to a user-owned shelf.
Later access loss does not delete that stored item automatically. This preserves
the shelf owner's durable organization until an explicit cleanup decision.

Normal reads hide the unavailable Book and return visibility-scoped counts and
previews. PATCH/move operations on a retained unavailable item return the
normal not-found response and do not expose hidden Book data. The shelf owner
may still DELETE the retained item by its known shelf-item id; deletion reveals
no Book metadata.

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
Shelf Edit uses Details, Books, and Add Books tabs. Add Books uses broad library
Book search with `exclude_shelf` so already-contained Books are suppressed by
the server. Delete Shelf uses a collapsed disclosure and a final browser
confirmation.

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
