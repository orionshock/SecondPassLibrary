# Permissions and visibility

This document defines current role authority, Book visibility, and Shelf
ownership/visibility rules. Exact HTTP routes and payloads belong in
`docs/api.md`; Product UI architecture belongs in `docs/frontend.md`.

## Identity concepts

Second Pass Library has one system Owner and three application roles:

- **Owner**: represented by Django `is_superuser`; not a normal profile role.
- **Manager**: manages users, Library Groups, and library operations within the
  restrictions below.
- **Librarian**: manages Books, imports, group Book assignments, and supported
  group/shelf presentation.
- **Reader**: reads visible Books and owns personal reading and shelf data.

`LibraryGroupMembership` grants access to one Library Group. Its optional
`is_curator=true` flag grants group-scoped stewardship for that exact custom
group; Curator is not a global role.

Role/capability values returned to a client are UI hints. Every operation still
enforces authority at the API/service boundary.

## Global role authority

### Owner

Owner may:

- manage all non-Owner users and assign global roles;
- perform all Manager and Librarian operations;
- manage designated Public group identity through Server Settings;
- enable advanced library groups;
- use the separately gated Django Admin Service Hatch for recovery.

Owner cannot deactivate or reset their own account through managed-user APIs.
Owner is still subject to protected Public-group and user-data invariants.

### Manager

Manager may:

- create Librarian and Reader accounts and manage non-Manager, non-Owner users;
- create, rename, update, and delete custom Library Groups;
- manage group memberships and curator flags;
- perform Librarian library and shelf operations.

Manager cannot promote/demote Managers, manage Owner, change their own role, or
change designated Public group name/description.

### Librarian

Librarian may:

- import Books and edit Book metadata, files, Catalog Tags, and covers;
- create, edit, and safely delete unattached catalog Authors and Series through
  session-authenticated management surfaces; attached entities require future
  reassignment or merge work and cannot be deleted;
- assign/remove Books from visible Library Groups through the supported group
  services;
- update custom-group descriptions;
- create and manage group-owned shelves, including Public group shelves.

Librarian cannot create/rename/delete groups, manage group memberships or
curator flags, manage global roles, or edit designated Public identity.

### Reader

Reader may:

- browse and download Books visible through their group memberships;
- manage their own reading sessions, progress, and annotations;
- create and manage their own private/listed shelves;
- read other visible shelf/group surfaces.

Reader has no global library, group, or user-management authority.

## Book visibility

Library Groups are Book access scopes. A Reader sees a Book when it is assigned
to at least one group the Reader can see. Librarian, Manager, and Owner retain
their existing broad library visibility.

Visibility is applied before counts, filters, pagination, previews, search, and
nested summaries. A visible group or shelf never permits hidden Book metadata
to leak through its rows, counts, previews, or empty-state behavior.

Reading metadata remains owned by its user. Existing sessions and annotations
are not deleted when Book access changes, although opening the Book and new
writes require current visibility.

## Designated Public group

Public/Common Room is a real designated `LibraryGroup`, identified by the
stored Public group id rather than its display name. `Common Room` is only its
default name.

- Public exists in both simple and advanced modes.
- Public is the default/fallback membership and Book assignment when an object
  would otherwise have no group.
- Public cannot be deleted.
- Public cannot have `is_curator=true` memberships.
- Public is not universal access; normal Public membership controls Reader
  access to its Books and shelves.
- Designated Public name and description are editable only by Owner through
  Server Settings. Normal Group PATCH rejects both fields for every role,
  including Owner.
- Librarian, Manager, and Owner retain their supported Public Book-assignment,
  membership-management, and shelf operations, subject to Public protections.

Group Edit therefore presents Public Details as read-only and points Owner to
Server Settings. Product UI architecture details remain in `docs/frontend.md`.

## Simple and advanced group modes

Simple mode is the supported one-Public-group Product UI mode. It hides custom
group navigation, relationship controls, selectors, and management surfaces.
It does not remove Public from the backend, disable Public group-scoped reads,
or disable shelves.

Custom groups are an advanced-mode concept. Owner can enable advanced groups
with explicit confirmation. The normal Product UI does not disable the feature
after use. Disable/collapse is an operator recovery workflow through the
Django Admin Service Hatch that consolidates supported custom-group state into
Public before disabling the feature.

## Custom group authority

For a visible custom group:

- Manager and Owner may create, rename, update, and delete it.
- Librarian, Manager, and Owner may update its description.
- A Reader curator may update the description and manage Books/shelves only for
  the exact custom group carrying their curator membership.
- A Reader curator may add only Books they can already see.
- Manager and Owner alone manage group memberships and curator flags.
- Direct members and broad roles may read the membership list; inaccessible
  groups return 404 to avoid existence leakage.

Group View is the presentation/read surface. Group Edit is the authorized
management surface, including broad library Book search with `exclude_group`.
Authorized custom-group deletion is a supported API/Product UI workflow.

## Membership and fallback rules

- New users start as ordinary Public members.
- New/imported Books start assigned to Public.
- Removing a user's final membership restores ordinary Public membership.
- Removing a Book's final assignment restores its Public assignment.
- A Public membership may be removed only when another membership remains.
- Public curator assignment is always invalid.
- Membership APIs identify users by public profile id rather than Django auth
  user id; membership record ids are not public identifiers.

User Edit and Group Edit are both valid Product UI membership-management
surfaces for authorized Manager/Owner users.

## Shelf ownership and visibility authority

Shelves organize Books; they never grant Book access. Every Shelf has exactly
one immutable owner: either one user or one Library Group. Its UUID, not its
display name, is identity; different owners may use the same name.

### Read visibility

- A user-owned private Shelf is visible and editable only to its owner. Broad
  application roles do not bypass that privacy boundary.
- A user-owned listed Shelf remains editable only by its owner. Another
  authenticated user can discover or open it only when it contains at least
  one Book currently visible to that viewer.
- A Group Shelf is visible to the owning Group's members and broad roles,
  including when empty. Its stored `visibility` is always `private`; visibility
  comes from Group membership, not a public Shelf setting.
- A Public Group Shelf follows the ordinary Group rule. "Public" does not mean
  anonymous: Public membership still controls Reader access.
- A user's own Shelves and visible Group Shelves remain visible when empty.
  Other users' listed Shelves with zero viewer-visible items are omitted and
  direct detail returns the same not-found treatment. List, detail, counts,
  previews, and item reads use the same viewer visibility boundary.

Normal Shelf reads include only currently visible Books. Counts and previews
must not disclose hidden Books or their metadata.

### Mutation authority

The user owner alone may create, rename, change visibility, populate, reorder,
remove from, or delete a personal Shelf. Owner, Manager, and Librarian may do
the corresponding operations for Group Shelves. A Reader curator may do so
only for a Shelf owned by their exact custom Group. Public Group Shelves have
no curator authority and are managed by Librarian, Manager, or Owner.

Advanced Library Groups gates only its documented Product UI navigation and
management controls. It does not invalidate Group Shelves, Public Group
behavior, or ordinary Group-scoped reads; Public Group Shelves work in simple
and advanced modes.

### Item eligibility, order, and later access loss

- An item on a user Shelf must reference a Book currently in that user's
  visible Book universe when added.
- An item on a Group Shelf must reference a Book assigned to that exact owning
  Group. Visibility through another Group is insufficient.
- A Book can occur at most once on a Shelf. Stored positions are zero-based,
  contiguous, and updated under the Shelf mutation boundary. Product UI may
  present positions as one-based; response sorting by title/author does not
  rewrite stored order.
- Later loss of Book visibility does not delete a user-owned Shelf item. Normal
  reads hide it; the owner can see only a safe unavailable placeholder in the
  editor and can remove it without receiving hidden Book metadata. Direct
  positioning is disabled while unavailable slots exist; relative moves skip
  those slots.
- Removing a Book from a Library Group removes it from Shelves owned by that
  exact Group and compacts their positions. It does not remove the Book from
  other Group Shelves or personal Shelves. Deleting a Book removes its Shelf
  items through the database relationship; deleting a Shelf removes only its
  items, never Books.

Operator review and optional removal of retained unavailable personal items is
documented in [Operations](operations.md#unavailable-personal-shelf-items).

## Client bearer restrictions

Client bearer tokens are reader-client credentials, not management tokens.

- Library and visible group reads are read-only through bearer authentication.
- Library/group mutation, imports, covers, and membership management require a
  Django session and their normal role authority.
- Bearer clients may read shelves visible to the token user.
- Bearer clients may create/edit/delete and manage items only in the token
  user's personal shelves.
- Group-owned and other users' shelves are read-only to bearer clients, even if
  the same user could manage a group shelf through Product UI session auth.
- Bearer Marginalia mutations are restricted to the token user's owned state.

Pairing and the full bearer route surface are documented in
`docs/client-api-auth.md`.

## Implementation guardrails

- Group assignment changes go through
  `library.groups.services.add_book_to_group()` and
  `library.groups.services.remove_book_from_group()`.
- Group removal/fallback behavior remains centralized in group services.
- Book and group list/detail queries use the visibility helpers in
  `library.queries`; do not reproduce visibility policy in serializers or UI
  JavaScript.
- Prefer 404 for inaccessible group/object detail where existence itself is
  protected.
- Do not treat capability fields, role names, or `can_edit` response hints as a
  substitute for server authorization.
- Do not use shelves as an access-control mechanism.
