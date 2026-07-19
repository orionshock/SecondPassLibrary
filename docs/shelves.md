# Shelves

Shelves are **presentation/organization**, not access control.

## Summary

- LibraryGroups answer: "Can this user access this book?"
- Shelves answer: "How is this book organized or presented?"
- Metadata (subjects/tags/series/etc.) answer: "What kind of book is this?"

Shelves never grant access to books. Any book shown from a shelf must still pass normal book access checks.

## Core concepts

Second Pass Library distinguishes:

- **LibraryGroups**: access scopes for books (security boundary)
- **Shelves**: ordered collections of books (presentation)
- **Book metadata**: bibliographic fields and tags/subjects (descriptive)

Implications:

- A visible shelf does **not** imply all its books are visible.
- Shelf items may remain in the database even if a viewer cannot currently see a particular book; hidden books must not be leaked via shelf rendering.

## Ownership and visibility

Each shelf has exactly one owner:

- **User-owned shelf**: `owner_type="user"`, `owner_user` set, `owner_group` null
- **Group-owned shelf**: `owner_type="group"`, `owner_group` set, `owner_user` null

### User-owned shelves

User-owned shelves have a visibility setting:

- `private`: visible only to the owner
- `listed`: shelf metadata is visible to authenticated users

### Group-owned shelves

Group-owned shelves have no listed/public state. Visibility is derived from the owning LibraryGroup:

- visible to direct members of the owning group
- also visible to broad roles (Owner/Manager/Librarian)

## Models

### `Shelf`

- `id` (UUID)
- `name`, `description`
- `owner_type`: `user | group`
- `owner_user` (nullable FK), `owner_group` (nullable FK)
- `visibility` (user-owned shelves only): `private | listed`
- `created_by` (nullable FK)
- timestamps

List/detail payloads also include:

- `item_count`: number of shelf items
- `can_edit`: whether the current request context can edit the shelf
- `matched_item_id`: included on list results when filtering by `?book=<book_id>`

`owner_user` is included for user-owned shelves as a compact user object:

```json
{
  "profile_id": "8f8cc870-5f5a-41e7-8cf4-62bc56f0db15",
  "username": "manager"
}
```

`created_by` and shelf item `added_by` use the same username-only compact user
shape when known. These compact user payloads do not include Django auth user
database ids, email addresses, names, or profile/admin metadata.

### `ShelfItem`

- `id` (UUID)
- `shelf` (FK)
- `book` (FK)
- `position` (stored zero-based integer ordering)
- `added_by` (nullable FK)
- timestamps

Invariants:

- a given book appears at most once per shelf
- stored positions are contiguous zero-based integers; duplicate requested/current positions are canonicalized by position, book title, then stable IDs
- deleting a shelf deletes only the shelf and its items (never books or files)

## Permissions

High-level rules:

- **User-owned shelf**
  - view: owner always; other users only if `visibility="listed"`
  - edit: owner only
- **Group-owned shelf**
  - view: group members and broad roles
  - edit: Owner/Manager/Librarian; Curator of the owning non-Public group

Public group shelves:

- Public has no curators
- Public group shelves are editable only by Owner/Manager/Librarian
- Public group shelves follow normal Public group membership visibility; Public
  is not a universal shelf visibility bypass.
- These ownership and visibility rules apply in both simple and advanced group
  modes. Simple mode hides advanced group relationship/management UI; it does
  not disable user-owned shelves or Public group-owned shelves.

Shelf list responses apply one additional anti-leakage rule: a listed
user-owned shelf belonging to somebody else is omitted when its viewer-scoped
`item_count` is zero. Owners still see their own empty shelves, and visible
group-owned shelves remain listed when empty. Direct shelf item filtering and
private shelf visibility are unchanged.

Client API bearer-token requests are narrower than product UI/session-auth requests:

- bearer tokens may create/edit/delete shelves and manage shelf items only for the token user's own user-owned shelves
- group-owned shelves and other users' shelves are read-only to bearer clients and return `can_edit: false`
- the same user may still see `can_edit: true` for a group shelf when using product UI/session auth if normal group/product authorization allows it

## Book access constraints (important)

Shelf visibility and book visibility are separate:

1. First check whether the viewer can see the shelf.
2. Then filter shelf items/books through current book visibility from
   `library.queries`.

This applies to:

- user-owned shelves (including the owner)
- listed shelves
- group-owned shelves

If a user can see a shelf but cannot see any books on it, the shelf should render as empty (no hidden titles).

## Group-owned shelves

Group-owned shelves are owned by a LibraryGroup and intended to organize books within that group.

Important rule:

- when adding/removing shelf items, the API enforces that the editor is allowed to edit the shelf
- for group-owned shelves, adding is further constrained by group context (the API is authoritative)
- when a book is removed from a LibraryGroup, the explicit shelves hook removes
  that book from shelves owned by the same group and canonicalizes positions
- shelves owned by other groups and user-owned shelves are not modified by that
  group-removal hook

## User-owned shelves

User-owned shelves are personal organization with an optional listed mode.

Write constraint:

- when adding a book to a user-owned shelf, the server enforces that the editor can view the book at write time
- user-owned shelf items preserve durable user intent; group membership/book
  assignment changes do not delete user-owned shelf items
- normal visible APIs still hide unavailable user-owned shelf items from users
  who cannot currently see the book

## API endpoints

Shelves are under `/api/v1/shelves/`:

- `GET /api/v1/shelves/` (paginated)
  - filters:
    - omitted `scope` or `?scope=all` (combined visible shelves)
    - `?scope=personal` (current user's user-owned shelves, including empty)
    - `?scope=shared` (other users' listed shelves with a viewer-visible item)
    - `?scope=group` (visible group-owned shelves, including empty)
    - `?owner_group=<group_id>` (group-owned shelves for a group)
    - `?book=<book_id>` (shelves containing the book; includes `matched_item_id` when applicable)
  - validation/combinations:
    - `scope` accepts only `all`, `personal`, `shared`, or `group`
    - `owner_group` and `book` must be valid UUIDs
    - `scope=personal&owner_group=<group_id>` is invalid and returns `400`
    - `scope=group&owner_group=<group_id>` is valid
    - malformed or incompatible supplied filters return `400`
- `POST /api/v1/shelves/` (create)
- `GET /api/v1/shelves/<id>/`
- `PATCH /api/v1/shelves/<id>/` (partial update; name/description/visibility only)
- `PUT /api/v1/shelves/<id>/` (treated the same as `PATCH` for compatibility; partial update)
- `DELETE /api/v1/shelves/<id>/`
- items:
  - `GET /api/v1/shelves/<id>/items/` (paginated)
  - `POST /api/v1/shelves/<id>/items/`
  - `PATCH /api/v1/shelves/<id>/items/<item_id>/` (either `{"move": "up|down"}` or `{"position": 0}`)
  - `DELETE /api/v1/shelves/<id>/items/<item_id>/`

Notes:

- Omitting `scope` and `scope=all` return the same combined visible-shelves list.
- All scopes use the normal DRF paginated envelope; no grouped response is returned.
- Session and bearer reads use the same scope rules.
- Scope filters do not bypass visibility policy. Other users' private shelves are excluded from personal, shared, and unscoped lists, including for Manager and Owner users.
- Shelf item `book` summaries include `cover_url` when available.
- Shelf item positions are stored zero-based and canonicalized as contiguous integers.
- Patching an existing item with `position` uses list move-to semantics: remove the item from its current ordered position, insert it at the requested zero-based target position (clamped to list bounds), then renumber all items contiguously.
- Product/UI displays may show one-based labels such as `#1`, `#2`, etc.
- Shelves do not grant book access: `/items/` filters listed books through normal book access rules.
- `?book=<book_id>` never matches through an item whose book is not currently
  visible to the requester and does not expose `matched_item_id` for hidden
  items.
- Client API bearer tokens may read visible shelves, but may create/edit/delete shelves and manage shelf items only for the token user's own personal shelves. Group shelves and other users' shelves remain read-only via bearer tokens and report `can_edit: false`.

## Product UI

Product UI routes:

- `GET /shelves/` (URL-backed Personal, Shared by Others, and Group Shelves tabs)
- `GET /shelves/new/` (create)
- `GET /shelves/<shelf_id>/` (view)
- `GET /shelves/<shelf_id>/edit/` (edit/manage items)

Behavior:

- Shelf edit is the primary shelf management page. It uses tabs:
  - Books in shelf (default): remove/reorder with `Move up` / `Move down` and a `Move to` dropdown; changes apply immediately.
  - Add books: broad BookVerse search uses
    `GET /api/v1/library/search?q=<term>&ordering=title&exclude_shelf=<shelf_id>`;
    changes apply immediately and existing shelf books are excluded server-side.
  - Details: edit name/description/visibility (user shelves only) and delete.
- Shelf list/detail/edit views place shelf ownership in the first metadata segment:
  - user-owned shelves show the Material Symbols `person` icon followed by `First Last <@username>` when a first or last name exists, falling back to `<@username>` without an empty gap
  - group-owned shelves show the Material Symbols `groups` icon followed by the group name
  - visibility and item count follow with separators, such as `person Owen Benji <@owner> - Private - 17 items` or `groups Public - Private - 6 items`
  - `profile_id` is used for identity comparison only and is not displayed
- Book detail and book edit pages surface shelf context (shelves containing the book).
- Group pages include shelf tabs for group-owned shelves.

## Service Hatch / admin

Django admin is the service hatch and can inspect/edit shelf internals for
recovery/debugging when exposed with `SECOND_PASS_ENABLE_DJANGO_ADMIN=1`. It is
not the product UI.

### Optional unavailable-item cleanup

User-owned shelf items intentionally survive later access changes, while normal
APIs continue hiding books the viewer cannot access. Operators may optionally
report or remove those unavailable rows with `cleanup_shelves`:

```powershell
python manage.py cleanup_shelves
python manage.py cleanup_shelves --apply
```

The default is a dry run. It reports affected user-owned shelves and unavailable
item counts without changing data. `--apply` transactionally removes only items
the shelf owner can no longer access and canonicalizes the remaining positions.
Group-owned shelves are never included. This command is optional maintenance;
it does not add live cleanup or change group/membership propagation behavior.

## Non-goals

- Shelves are not access control.
- No public/anonymous shelf browsing.
- No drag/drop ordering UI.
- No per-row numeric position input UI in the current shelf edit page.
- No group-shelf or other-user shelf writes via Client API bearer tokens; those shelves are read-only to bearer clients.

## Future possibilities

- Bulk reordering APIs.
