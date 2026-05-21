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
- `can_edit`: whether the current caller can edit the shelf
- `matched_item_id`: included on list results when filtering by `?book=<book_id>`

### `ShelfItem`

- `id` (UUID)
- `shelf` (FK)
- `book` (FK)
- `position` (integer ordering)
- `added_by` (nullable FK)
- timestamps

Invariants:

- a given book appears at most once per shelf
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

## Book access constraints (important)

Shelf visibility and book visibility are separate:

1. First check `can_view_shelf(viewer, shelf)`.
2. Then filter shelf items/books through `can_view_book(viewer, book)`.

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

Group deletion:

- Deleting a non-Public LibraryGroup deletes shelves owned by that group (and their shelf items).

## User-owned shelves

User-owned shelves are personal organization with an optional listed mode.

Write constraint:

- when adding a book to a user-owned shelf, the server enforces that the editor can view the book at write time

## API endpoints

Shelves are under `/api/v1/shelves/`:

- `GET /api/v1/shelves/` (paginated)
  - filters:
    - `?owner_group=<group_id>` (group-owned shelves for a group)
    - `?book=<book_id>` (shelves containing the book; includes `matched_item_id` when applicable)
- `POST /api/v1/shelves/` (create)
- `GET /api/v1/shelves/<id>/`
- `PATCH /api/v1/shelves/<id>/`
- `DELETE /api/v1/shelves/<id>/`
- items:
  - `GET /api/v1/shelves/<id>/items/` (paginated)
  - `POST /api/v1/shelves/<id>/items/`
  - `PATCH /api/v1/shelves/<id>/items/<item_id>/`
  - `DELETE /api/v1/shelves/<id>/items/<item_id>/`

Notes:

- Shelf item `book` summaries include `cover_url` when available.

## Product UI

Product UI routes:

- `GET /shelves/` (list)
- `GET /shelves/new/` (create)
- `GET /shelves/<shelf_id>/` (view)
- `GET /shelves/<shelf_id>/edit/` (edit/manage items)

Behavior:

- Shelf edit is the primary shelf management page (add/remove items, ordering, delete).
- Book detail and book edit pages surface shelf context (shelves containing the book).
- Group pages include shelf tabs for group-owned shelves.

## Service Hatch / admin

Django admin at `/admin/` is the service hatch and can inspect/edit shelf internals for recovery/debugging. It is not the product UI.

## Non-goals

- Shelves are not access control.
- No public/anonymous shelf browsing.
- No drag/drop ordering UI (ordering is numeric inputs).
- No group-shelf management via Client API bearer tokens (group shelves remain product UI/session-auth only).

## Future possibilities

- Reader-client shelves support (explicit allow-list; keep write rules conservative).
- Server-side cleanup hooks when removing a book from a LibraryGroup (e.g. removing from shelves owned by that group).
- Bulk reordering APIs.
