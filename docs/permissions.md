# Permissions and Roles

This document describes the intended permission model for Second Pass Library.

Key principles:

- Reading metadata is user-owned and durable.
- LibraryGroups are **access scopes**, not shelves.
- Access to a book is determined by `LibraryGroupMembership` + `BookGroupAssignment`.
- Losing book access does not hide or remove a user's existing reading sessions
  and annotations from that user, but it does block live reading activity,
  annotation/progress writes, new sessions, and book-file download.
- Session summary/detail payloads may expose `can_open=false` for owned
  sessions whose book is no longer visible. That is a UI hint for open/continue
  capability, not a denial of marginalia ownership.
- Business rules should be centralized in policy helpers and service modules (avoid scattered per-view logic).

In plain language:

- Readers live in groups.
- Curator is an optional group-membership stewardship flag.
- Librarians manage the collection globally.
- Managers manage people globally.
- Owners manage the installation.

## Roles (global)

Global roles live on `UserProfile.role`:

- `manager`
- `librarian`
- `reader`

### Owner (Django `is_superuser`)

- Owner is Django `is_superuser`.
- Owner is a system/root authority, not a normal app role.
- Owner can do everything.
- Only Owner can promote users to Manager or demote existing Managers.
- Owner may use Django admin/service hatches for recovery.
- The first-run setup page creates the initial active superuser and an
  associated Manager `UserProfile`; it does not add an `owner` profile role.
- The setup page is unavailable once any active superuser exists.

### Manager

Manager is the app-level administrator.

Manager can:

- manage users
- assign users as Librarian or Reader
- manage LibraryGroup membership (add/remove users from groups)
- set or clear the `is_curator` stewardship flag on group memberships
- create LibraryGroups
- manage LibraryGroup identity, subject to Public restrictions
- perform all Librarian-level book/library operations

API note (current implementation):

- LibraryGroup create endpoints are available to Owner/Manager only.
- Group membership management is now exposed via Manager/Owner-only group membership endpoints (see `docs/api.md`).

Manager cannot (unless also Owner):

- promote users to Manager
- demote existing Managers
- change Public's fixed identity

## User management API (narrow)

User management is intentionally limited:

- `POST /api/v1/accounts/users/` (Manager/Owner only; creates local Django user and returns a temporary password once)
- `POST /api/v1/accounts/users/<profile_id>/reset-password/` (Manager/Owner only; resets a managed user's password and returns a temporary password once)
- `GET /api/v1/accounts/users/`
- `GET /api/v1/accounts/users/<profile_id>/`
- `PATCH /api/v1/accounts/users/<profile_id>/` (safe fields only; no password reset/invite/delete endpoints)

Invite-by-email is not a core account lifecycle requirement. Self-hosted
installations may use Owner/Manager-managed local users and the Django admin
service hatch without configuring SMTP. See `docs/architecture.md` for the
canonical account, email, and future external-auth posture.

Creation rules:

- Owner can create `manager`, `librarian`, or `reader` users.
- Manager can create `librarian` or `reader` users only (cannot create `manager`).
- Librarian/Reader cannot create users.

### `/api/v1/accounts/me/` account hints

`GET /api/v1/accounts/me/` includes the caller's identity, global `role`, `is_owner` flag, and `groups` memberships to help future UIs decide what to show.

These are **account hints**, not a replacement for policy enforcement. Broad Product UI affordances are derived from `role` and `is_owner`; object-specific affordances come from object payloads such as LibraryGroup `capabilities.can_curate`. Every endpoint still enforces authorization via the specific `core.policies` helpers.

Rules:

- Owner can manage all users, but cannot deactivate themselves via the API.
- Manager can manage non-Owner, non-Manager users only.
- Managers cannot promote/demote Managers.
- Managers cannot change their own role.
- No user can deactivate themselves via the API.
- Managed user password resets set `UserProfile.must_change_password=true` (force change on next login via product UI redirect).

### Librarian

Librarian is the global book/content manager.

Librarian can:

- import books
- edit book metadata
- manage book files
- assign/remove books from existing LibraryGroups (via safe curation services)
- edit group presentation fields where allowed
- edit description for non-Public LibraryGroups
- later: manage group-owned shelves for all groups where applicable

Librarian cannot:

- create LibraryGroups
- rename LibraryGroups
- change LibraryGroup identity fields
- manage LibraryGroup membership
- add/remove users from groups
- set curator flags
- manage global user roles

Public-specific librarian rule:

- Librarian may edit Public description only.
- Librarian may not change Public name.

### Reader

Reader can:

- browse/download books they have access to
- manage their own reading metadata
- manage their own future personal shelves (if implemented later)

Reader cannot:

- manage library inventory
- import books
- manage LibraryGroups
- manage users

## Curator (group-scoped flag)

Curator is **not** a global role. A `LibraryGroupMembership` means ordinary group membership; `is_curator=true` is an optional group-scoped curator/stewardship flag on that exact membership.

Reader users with `is_curator=true` can curate that exact **non-Public** LibraryGroup only:

- edit group description
- add books they can already view/read to the group
- remove books from the group
- create and manage group-owned shelves for that group

Curator cannot:

- curate Public
- import books
- delete books from the system
- create/rename LibraryGroups
- change LibraryGroup identity fields
- manage group membership
- add/remove users from groups
- assign or remove curator flags
- add books they cannot already view/read

Librarian, Manager, and Owner users can curate groups through their broad global authority. They may also have `is_curator=true` on a non-Public group as stewardship metadata, but their broad authority does not depend on that flag.

## LibraryGroups

LibraryGroups are access scopes. They are not shelves and they do not exist to provide presentation/organization.

### Identity vs presentation

Identity fields:

- `name`

Presentation/configuration fields:

- `description`

Rules:

- Name should be treated as immutable in normal product workflows after group creation.
- The Public display name is configured during first-run setup or by the Owner
  through server settings.
- Description is a presentation/configuration field and may be editable according to role policy.

## Public group

Public is special. `Common Room` is its default display name, not its internal
identity.

- Public is identified by `ServerSetting(public_group_id)`.
- Public is the only special built-in LibraryGroup.
- Public behavior is based on `is_public_group()` / `get_public_group()` (not boolean flags).
- Renaming the Public display name does not change its identity or protections.
- Public cannot be deleted.
- Public cannot have curator assignments (`is_curator=true` is invalid).

Default/fallback behavior:

- Public, displayed as `Common Room` by default, is the shared public library
  space managed by librarians and managers.
- First-run Owner setup creates/repairs Public, saves its configured name and
  description, and adds the Owner as an ordinary member.
- New users default to Public ordinary membership.
- New/imported books default to Public (book assignment).
- Users/books must belong to at least one LibraryGroup.
- Public is fallback only: if a user/book would otherwise have zero groups, it is restored to Public.

`advanced_library_groups_enabled` is currently a Product UI preference.
Disabled means the server is centered on Common Room. Enabled presents
additional curator-managed rooms, each with its own memberships and group-owned
shelves, as a first-class workflow. It does not alter permissions or block
group APIs.

Role constraints:

- Librarian may edit Public description only.
- Managers/Owner may manage Public only within the protected Public rules.

## Safe group mutation (services)

Safe changes to group assignments should go through:

- `library.group_services.add_book_to_group()`
- `library.group_services.remove_book_from_group()`

This prevents scattered direct `BookGroupAssignment` writes and centralizes invariants (including the Public fallback invariant).

## Shelves

Shelves are a presentation/organization feature and **do not** grant book access. See `docs/shelves.md`.

Shelves API is implemented under `/api/v1/shelves/`. Shelves have product UI support; they remain separate from access control.

## Group membership management (current)

- **Viewing group members (read-only):**
  - Owner/Manager/Librarian can list group members.
  - Direct members of a group can list that group's members (including Public).
  - Non-members cannot list memberships for non-Public groups they cannot view (anti-leakage behavior).
- **Owner/Manager** can manage LibraryGroup memberships via the API (add/remove users and set `is_curator`).
- **Librarian/Curator/Reader** cannot manage memberships via the API.
- **Public protections**:
  - Public is default/fallback (assigned on user creation, and restored if a user would otherwise have zero memberships).
  - Public memberships can be removed when another group remains; removing a user's final membership restores Public.
  - Public cannot have curator assignments.

## Group API and anti-existence-leakage rules

When exposing groups through the API:

- Prefer returning `404 Not Found` for groups the user cannot view (avoid leaking group existence).
- Group book listings must still filter each book through `can_view_book(user, book)` (a viewable group must not leak inaccessible books).
- Group curation endpoints should call the safe group curation services above.
- Group presentation updates should be limited to `description` via `PATCH /api/v1/library/groups/<group_id>/`.

Not implemented (non-goals):

- No public API for anonymous users to create LibraryGroups.
- Group delete/scary delete is not part of the current documented product/API contract.

## Shelves are separate (design principle)

LibraryGroups are access scopes. Shelves are presentation/organization objects.

- A shelf never grants access to a book.
- Shelf visibility controls whether the shelf/list itself can be seen.
- Each book on a shelf must still pass `can_view_book(user, book)`.
- User-owned shelves and group-owned shelves should be modeled separately later.
- Librarians may manage group-owned shelves across groups later.
- Curators may manage group-owned shelves only for groups where `is_curator=true`; broad roles may manage group-owned shelves through global authority.
- Readers may manage their own personal shelves later.

## Policy helper direction (recommended)

Centralize permission rules in explicit policy helpers. Recommended helpers include:

- `can_create_library_group(user)`
- `can_manage_group_identity(user, group)`
- `can_manage_group_membership(user, group)`
- `can_curate_group(user, group)`
- `can_assign_global_role(actor, target_user, new_role)`
- `can_view_book(user, book)`
- `can_download_book_file(user, book_file)`
- `can_add_book_to_group(user, book, group)`
- `can_remove_book_from_group(user, book, group)`

Notes:

- Group mutation should use `library.group_services.add_book_to_group()` / `remove_book_from_group()`.
- Future group presentation APIs should enforce the role rules above.
- Future user-management APIs should enforce Owner-only Manager promotion/demotion.
