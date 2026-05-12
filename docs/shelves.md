# Shelves (Design / Planned)

Shelves are a planned feature. This document records the intended model, routes, and policy rules **before implementation**.

## 1. Core principle

Second Pass Library has three distinct concepts:

- **LibraryGroups** answer: “Can this user access this book?”
- **Shelves** answer: “How is this book organized or presented?”
- **Genres/tags/metadata** answer: “What kind of book is this?”

Shelves are **presentation/organization**, not access control.

Important implications:

- A visible shelf does **not** imply all of its books are visible.
- Every book rendered from a shelf must still pass the normal access policy (e.g. `can_view_book(viewer, book)`).
- The server should not treat shelves as a backdoor for access.

## 2. Model direction

Implementation should use **one** `Shelf` model (not separate `UserShelf` and `GroupShelf` tables).

Reason:

- The core object is the same: a named/ordered collection of books.
- Ownership and policy differ, but the shelf object does not.
- One model keeps the API/UI consistent and reduces duplication.

### Planned models

`Shelf`:

- `id` (UUID)
- `name`
- `description`
- `owner_type`: `user | group`
- `owner_user` (nullable FK)
- `owner_group` (nullable FK to `LibraryGroup`)
- `visibility` (user-owned shelves only): `private | listed`
- `created_by` (nullable FK to user; “who created it”)
- timestamps (`created_at`, `updated_at`)

`ShelfItem`:

- `id` (UUID)
- `shelf` (FK)
- `book` (FK)
- `position` (integer ordering)
- `added_by` (nullable FK to user)
- timestamps

### Ownership invariant (hard rule)

Each shelf has **exactly one** owner:

- user shelf: `owner_user` is set; `owner_group` is null
- group shelf: `owner_group` is set; `owner_user` is null
- never both
- never neither

### ShelfItem invariants (hard rules)

- Each book appears **at most once** per shelf.
- Ordering starts simple with an integer `position`.
- No drag/drop reordering complexity initially; UI can submit final ordering later.

## 3. Routes (planned)

Planned UI routes are shelf-centric (not user-centric):

- `GET /shelves/`
- `GET /shelves/new/`
- `GET /shelves/<shelf_id>/`
- `GET /shelves/<shelf_id>/edit/`

Do not put user IDs in shelf URLs.

Reason:

- Shelf ID is sufficient.
- User IDs should not be dragged into URLs unless necessary.
- Django `User` currently uses sequential IDs, and we do not want to get sidetracked changing that.

## 4. User-owned shelves

User-owned shelves have visibility:

- `private`: visible only to the owning user
- `listed`: shelf metadata visible to authenticated users

Listed user shelves should show attribution, for example:

- “Alice’s Favorites”
- show owner username / display name in the shelf header/details

Editing rules:

- Only the owning user can edit a user-owned shelf in the product UI.
- Managers/Librarians do not edit personal shelves through normal product UI.
- Service hatch/admin can still exist.

Add/remove rules:

- A user can add only books they can currently view (enforced by `can_view_book(owner, book)` at write time).

Rendering rules (important):

- First check `can_view_shelf(viewer, shelf)`.
- Then filter shelf books through `can_view_book(viewer, book)`.
- This applies even to the shelf owner.
- If the owner later loses access to a book, the `ShelfItem` may remain in the DB but the book is hidden until access returns.

Listed shelf behavior:

- Listed shelves do not grant access to books.
- Listed shelves may show different visible books to different viewers.
- If a viewer can see the shelf but none of its books, render it as empty (do not leak hidden titles).

## 5. Group-owned shelves

Group-owned shelves have no discoverability/visibility state; access is derived from the owning group.

They are visible only to:

- direct members of the owning `LibraryGroup`
- Owner/Manager/Librarian broad roles

They are editable by:

- Owner
- Manager
- Librarian
- Curator of the owning **non-Public** group

Public group shelves:

- are just group-owned shelves for the Public `LibraryGroup`
- Public has no curators
- editable only by Owner/Manager/Librarian

Readers cannot edit group-owned shelves.

## 6. Group shelf item invariant (hard rule)

A group-owned shelf may contain **only** books assigned to that same `LibraryGroup`.

Examples:

- “Fantasy Club” shelf may contain only books assigned to “Fantasy Club”.
- Public shelf may contain only books assigned to Public.

This rule is intentionally stricter than “the editor can currently view the book”.

Reason:

- every group member should see every book on that group shelf
- group shelves should not contain books that disappear for some group members
- shelves organize presentation; `LibraryGroup`s still define access

When a book is removed from a `LibraryGroup`:

- the server should remove that book from shelves owned by that `LibraryGroup`
- do this cleanup in the group assignment service later (not by relying on UI reminders)

## 7. Public semantics

Public is:

- a default/fallback `LibraryGroup`
- not mandatory membership
- identified by `ServerSetting(public_group_id)`

Public shelves:

- are group-owned shelves for the Public group
- visible to Public members and broad roles
- editable only by Owner/Manager/Librarian
- do not grant access to Public books

## 8. Policy helpers to implement later

Planned policy helpers:

- `can_view_shelf(user, shelf)`
- `can_edit_shelf(user, shelf)`
- `can_add_book_to_shelf(user, book, shelf)`
- `can_remove_book_from_shelf(user, book, shelf)`

Rules:

`can_view_shelf`:

- user shelf `private`: owner only
- user shelf `listed`: authenticated users
- group shelf: group members + Owner/Manager/Librarian

`can_edit_shelf`:

- user shelf: owner only
- group shelf: Owner/Manager/Librarian, or curator of owning non-Public group

`can_add_book_to_shelf`:

- user shelf: `can_edit_shelf` and `can_view_book(user, book)`
- group shelf: `can_edit_shelf` and book is assigned to `shelf.owner_group`

Rendering direction:

- first check `can_view_shelf`
- then filter shelf items/books according to shelf type and book access policy

## 9. Planned API (direction only)

This is a likely REST shape; it is not implemented-current unless documented elsewhere.

- `GET /api/v1/shelves/`
- `POST /api/v1/shelves/`
- `GET /api/v1/shelves/<id>/`
- `PATCH /api/v1/shelves/<id>/`
- `DELETE /api/v1/shelves/<id>/`
- `GET /api/v1/shelves/<id>/items/`
- `POST /api/v1/shelves/<id>/items/`
- `PATCH /api/v1/shelves/<id>/items/<item_id>/`
- `DELETE /api/v1/shelves/<id>/items/<item_id>/`

## 10. Planned UI (direction only)

Global shelves section:

- `/shelves/` lists:
  - my shelves
  - listed user shelves visible to me
  - group shelves visible to me
- `/shelves/new/` creates a shelf
- `/shelves/<id>/` views a shelf
- `/shelves/<id>/edit/` edits shelf details/items where allowed

Group pages:

- group view “Shelves” tab lists group-owned shelves
- group edit “Shelves” tab manages group-owned shelves where allowed

Book edit page:

- a future “Shelves” tab may show shelves containing this book

## 11. Non-goals

- Do not use shelves for access control.
- Do not make group shelves publicly discoverable outside the group.
- Do not add social/follow/federation features.
- Do not implement reader-client shelf UX yet.
- Do not implement drag/drop ordering initially.
- Do not implement global shelf discovery beyond listed user shelves.
- Do not implement separate UserShelf/GroupShelf tables unless future needs prove one model is insufficient.

