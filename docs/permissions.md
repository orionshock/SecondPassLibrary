# Permissions Model (Future Design)

This document describes the intended **future** permission model for Second Pass Library.

It is **documentation/design only**. It does not reflect current behavior in full, and it does not require implementation work by itself.

## Goals

- Keep the current implementation simple (shared library for authenticated users).
- Preserve a clear path to more advanced access control without a rewrite.
- Keep reading metadata user-owned and durable even if future book access rules change.
- Centralize permission policy in explicit helper functions (avoid scattered per-view logic).

## System Owner (is_superuser)

- **Owner** is represented by Djangoâ€™s built-in `is_superuser`.
- Owner is a **system-level** role, not a normal in-app role.
- Owner can do everything.
- Owner should be rare (ideally only the initial bootstrap/admin account).
- Only Owner can **promote or demote Managers**.
- Owner may eventually enable **Advanced Management** (a future mode/switch).

## Global App Roles (Normal In-App Roles)

These are the app's normal global roles (not Django admin permissions).

### Manager

- App-admin role.
- Can manage users, books, imports, and library configuration.
- Can assign users as **Librarian** or **Reader**.
- Cannot promote users to Manager.
- Cannot demote Managers.
- Manager promotion/demotion is Owner-only.

### Librarian

- Handles book mechanics.
- Can import books.
- Can edit book metadata.
- Can manage book files.
- Can assign books to groups (when Advanced Management exists).
- Cannot manage users.

### Reader

- Default user.
- Can browse/download books they have access to.
- Can manage **their own** reading metadata:
  - sessions
  - progress
  - annotations / highlights / notes / bookmarks
  - devices

## Advanced Management (Future Mode/Switch)

Advanced Management is a future mode controlled by Owner.

### When disabled (simple mode)

- The app behaves like a simple shared library.
- All users and books are effectively in **Public**.
- Group/Curator concepts are hidden from normal UI.

### When enabled (advanced mode)

- `LibraryGroup`, membership, and group-scoped curation become visible/manageable.
- Users may belong to multiple LibraryGroups.
- Books may belong to multiple LibraryGroups.
- Access can be scoped by LibraryGroup.

## LibraryGroup Concept (Future Product Model)

This is a product concept and is **not** the same as Django auth `Group`.

- Django `Group` may be used later for auth permission bundles, but `LibraryGroup` is the **product** access/curation concept.

### Intended future models (conceptual, not implemented)

#### LibraryGroup

- Product/library access scope.
- Top-level visibility and curation boundary.

#### LibraryGroupMembership

- Links a user to a LibraryGroup.
- Has a group-scoped role:
  - `reader`
  - `curator`

#### BookGroupAssignment

- Links a book to a LibraryGroup.
- Safe changes to group assignments should go through `library.group_services.add_book_to_group()` / `remove_book_from_group()` (avoid scattered direct `BookGroupAssignment` writes).

## Public Group Rules

### Current/simple rule (today)

- **Public** is the default shared library group.
- Public is identified by canonical slug `public` (not by a broad boolean flag).
- Public is the only special built-in `LibraryGroup` right now.
- Public special behavior should be expressed via `PUBLIC_GROUP_SLUG` / `is_public_group()` / `get_public_group()`, not via a boolean model flag.
- Every user belongs to Public.
- Every book belongs to Public by default.
  - In simple mode, a book should never remain without any group assignments; the safe fallback is Public.

### Future advanced rule (when Advanced Management is enabled)

- Users and books must belong to **at least one** LibraryGroup.
- Public remains the default fallback group.
- Public cannot have Curators.
- Managing Public is a Manager/Librarian responsibility.
- If a book would otherwise have no group assignments, it should be safely assigned back to Public (avoid “orphaned” inaccessible books).
  - Removing the final group assignment should fall back to Public.

## LibraryGroup Discoverability

LibraryGroups have a `discoverability` setting:

- `listed`: may appear in future UI lists/directories
- `unlisted`: hidden from future UI lists/directories (but still usable by direct link/admin)

Discoverability controls UI discoverability only:

- It does **not** grant access to books.
- Access is still controlled by `LibraryGroupMembership` and `BookGroupAssignment`.

## Curator Rules (Group-Scoped Role)

Curator is not a global role.

Curator:

- Exists only as a `LibraryGroupMembership` role.
- Applies only to the specific group where the user is curator.
- Cannot curate Public.
- Cannot import books.
- Cannot delete books from the system.
- Can remove any book from their own group.
- Can add a book to their group only if the curator personally already has read access to that book.
  - This prevents a curator from pulling hidden/restricted books into their group.

Example:

- Alice global role: Reader
- Public: reader
- Fantasy Club: curator
- Kids Books: reader

Alice can curate Fantasy Club only. Alice cannot curate Kids Books or Public.

## Permission Policy Direction (Implementation Guidance)

Implementation should use centralized, explicit policy helpers (e.g. `permissions.py` or `policy.py`) rather than scattered permission logic.

Possible future helpers:

- `can_manage_users(user)`
- `can_assign_global_role(actor, target_user, new_role)`
- `can_manage_library(user)`
- `can_import_books(user)`
- `can_view_book(user, book)`
- `can_download_book_file(user, book_file)`
- `can_curate_group(user, group)`
- `can_add_book_to_group(user, book, group)`
- `can_remove_book_from_group(user, book, group)`
- `can_view_reading_metadata(user, obj)`
- `can_edit_reading_metadata(user, obj)`

Policy rules that should remain true:

- Only Owner can assign or remove Manager role.
- Manager can assign Librarian/Reader but not Manager.
- Librarian manages books, not users.
- Reader manages only their own reading metadata.
- Reading metadata remains user-owned even if book access changes later.

Note: Until a formal user-management UI/API exists, Owner-only Manager promotion/demotion is enforced in Django admin.

## Shelves Are Separate

LibraryGroups are not shelves.

LibraryGroups:

- access scopes
- top-level visibility/curation boundaries

Shelves (if added later):

- presentation/organization feature
- should be modeled separately from LibraryGroups

### Shelves vs LibraryGroups (design note)

- LibraryGroups are access scopes.
- Shelves are future presentation/organization objects.
- Shelves should have owners: user-owned or LibraryGroup-owned.
- Shelf visibility/discoverability controls whether the shelf/list itself can be seen.
- A shelf must never grant access to books.
- When rendering a shelf, first check whether the viewer can see the shelf, then filter each shelf book through `can_view_book(user, book)`.
- A listed shelf does not make its books public.
- A group-owned shelf does not grant group membership.
- A user-owned shelf does not grant book access.
- Genres/tags are descriptive metadata and are separate from both LibraryGroups and shelves.
