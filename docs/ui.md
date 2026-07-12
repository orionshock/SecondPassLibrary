# UI Planning

This document sketches the first product web UI for Second Pass Library at a high level, before implementation.

## Status (first UI shell)

The first minimal product UI shell now exists:

- `/` redirects to `/dashboard/` after setup
- `/dashboard/` is the authenticated dashboard shell
- `/dashboard/` shows recent reading activity (from `GET /api/v1/reading/sessions/recent/`) and dashboard action cards
- `/server/` is an authenticated Owner-only Server Settings page (server identity + Django Admin / Service Hatch link)
- `/profile/` is the authenticated self account page (identity + groups + access summary + self-profile edit)
- `/profile/password/` is the authenticated self password change page
- `/library/` is an authenticated library browse page
- `/library/books/<book_id>/` is an API-driven book detail page (functional-first)
- `/library/books/<book_id>/edit/` is an API-driven book metadata edit page (Manager/Librarian/Owner only)
- `/imports/` is an API-driven imports page (upload + latest transient result)
- `/groups/` is an authenticated group list page
- `/groups/<group_id>/` is an authenticated group view page (Books/Members/Shelves tabs; read-oriented)
- `/groups/<group_id>/edit/` is an authenticated group management page (Details/Books/Members/Shelves tabs; management-oriented)
- `/groups/new/` is an authenticated group create page (Owner/Manager only)
- `/users/` provides functional user management for Manager/Owner only
- `/users/new/` provides functional local user creation for Manager/Owner (generated temporary password shown once)
- `/users/<profile_id>/edit/` provides a dedicated user edit screen for Manager/Owner
- `/reading/sessions/books/<book_id>/` shows the current user's reading sessions for a book
- `/reading/sessions/books/<book_id>/<session_id>/` shows session-specific Marginalia (progress + annotations) for the current user

Implementation note: the product UI lives in the dedicated Django app `web` (not `core`).

UI JavaScript is split into page-focused vanilla ES modules under `web/static/web/js/` and loaded via a single `<script type="module">` entrypoint (`web/static/web/js/main.js`). There is no frontend build step.

Product UI error handling:

- Missing Product UI pages return styled HTML error pages, not API JSON.
- Styled Product UI error pages currently exist for `404 Page not found`, `403 Not allowed`, and `500 Something went wrong`.
- Error pages should use the Product UI dark theme/shell where it is safe, avoid tracebacks and debug details in non-debug mode, and include a dashboard action.
- `/dashboard/` is the canonical dashboard route.
- `/app/` is not a supported route; it should remain a normal styled 404.
- Product UI object routes that expect UUID-backed IDs should reject malformed IDs with 404 before rendering a broken shell. Valid inaccessible objects may still intentionally return 404 to avoid leaking existence.

Fresh installs first use the server-rendered `/setup/` page to configure the
server name and optional description, the Public group's display name and
description, the advanced-groups setting, and the initial Owner account.
Defaults are `Second Pass Library`, a blank server description, `Common Room`,
`Main Public Library Room for everyone`, and advanced groups disabled. Common
Room remains the internally special Public group. Public is not universal access;
normal Public group membership still controls Public books and shelves.
Advanced groups present separate curator-managed rooms and enable normal
non-Public group mutation workflows. Setup is
available only while no active Django superuser exists. After setup,
authentication for Product UI pages continues to use the existing login at
`/api-auth/login/`.

Logout is POST-based (no GET logout links) and uses the existing `/api-auth/logout/`.

Planned auth/login session revocation behavior (and terminology vs `reading` sessions) is documented in `docs/session-management.md`.

The library browse screen is API-driven using vanilla JS fetch calls to `GET /api/v1/library/books/` (paginated), with basic loading/error/empty states.

The book detail page is API-driven using `GET /api/v1/library/books/<book_id>/` and is cover-forward:

- Top panel shows cover art (or placeholder), title/series/authors, and a primary Download action when a file is available.
- Tabs (default: Shelves) show Shelves, Groups, and Metadata. Secondary metadata includes identifiers and file details.

Dashboard note: recent reading items render a cover image when `book.cover_url` is present; otherwise they show a placeholder cover box. Recent reading cards link to the session Marginalia page and include an `[All Sessions]` link for the book.

Reading access-loss note: Product UI session history and export show owned marginalia even when the related book is no longer visible. Those rows use redacted book context and do not offer per-book/open navigation. Continue-reading/dashboard entrypoints omit inaccessible-book sessions.

Cover note: book lists/cards throughout the product UI render cover art when `cover_url` is present; placeholders remain when it is `null`.

Media note: `cover_url` points under `MEDIA_URL` (default: `/media/`). The only public media URL namespace is `/media/covers/`; book files and other protected user data are never served as raw media URLs.

The book detail page also shows the book's assigned LibraryGroups (filtered for Readers, including readers with group curator flags, to only viewable groups) with links to the group pages.

The book metadata edit page is organized into client-side tabs (Metadata, Authors & Series, Library Groups, Shelves, Identifiers & File Info). It is API-driven using `PATCH /api/v1/library/books/<book_id>/` and supports basic metadata fields plus author/series editing. `series_index` supports integers or one decimal place. Authors are selected from existing records; a series may be selected or created and assigned with the same atomic Book save. Identifier add/edit/remove controls update local page state and are saved as a complete replacement with the same Book PATCH. LibraryGroup assignments remain on their group relationship endpoints. The Shelves tab lists visible shelves containing the book and can remove the book from editable shelves. The Identifiers & File Info tab includes read-only Book-owned file metadata; the stored EPUB is not edited from this page.

The imports page is API-driven using:

- `POST /api/v1/library/imports/` (multipart upload field `file`)

Library imports are synchronous. The page shows the latest returned import
result for the current browser session; import history is not stored.

It intentionally supports only `.epub` and simple `.zip` of EPUBs (no Calibre sync/import of `metadata.db`, and no PDF).

ZIP OPF sidecars (current):

- When importing a `.zip`, the importer can optionally use an OPF sidecar to bootstrap metadata **for new books only** (not a sync/refresh mechanism).
- Sidecar lookup (per EPUB member), in order:
  - `metadata.opf` in the same directory as the EPUB (Calibre-style)
  - same-basename `.opf` in the same directory (`Foo.epub` -> `Foo.opf`)
  - if there is exactly one `.opf` in the same directory, use it
- A valid OPF sidecar is a full metadata replacement and takes precedence over EPUB embedded metadata.
- Duplicate EPUB checksum imports are rejected/skipped and do not refresh metadata or covers.
- Embedded EPUB cover extraction is best-effort; sidecar cover/assets are deferred.

The groups UI is API-driven using:

- `GET /api/v1/library/groups/` (paginated list)
- `POST /api/v1/library/groups/` (Owner/Manager only; create)
- `GET /api/v1/library/groups/<group_id>/` (detail)
- `PATCH /api/v1/library/groups/<group_id>/` (presentation fields only: description)
- `GET /api/v1/library/groups/<group_id>/books/` (paginated)
- `GET /api/v1/library/books/?q=<search>` (book search for the Groups UI picker)
- `POST /api/v1/library/groups/<group_id>/books/` (add book by id from picker)
- `DELETE /api/v1/library/groups/<group_id>/books/<book_id>/` (remove)
- Memberships:
  - `GET /api/v1/library/groups/<group_id>/memberships/` (paginated; visible to group members + managers/owners/librarians + Public viewers)
  - `POST/PATCH/DELETE /api/v1/library/groups/<group_id>/memberships/...` (Manager/Owner only)

Note: Group product routes use UUIDs and `LibraryGroup` no longer has a slug. The special Public group is identified internally by `ServerSetting(public_group_id)` (not by a slug string).

Dashboard note: the old "Sections" navigation card was removed from `/dashboard/` because the top navigation already provides the same links.

Shelves product UI pages exist (API-driven):

- `GET /shelves/` (list)
- `GET /shelves/new/` (create)
- `GET /shelves/<shelf_id>/` (view)
- `GET /shelves/<shelf_id>/edit/` (edit/manage items)

Book pages:

- Book detail (`/library/books/<book_id>/`) shows visible shelves containing the book.
- Book edit Shelves tab links to visible shelves containing the book (item management lives on Shelf Edit).
  - Book Edit Shelves tab (`/library/books/<book_id>/edit/`) lists shelves containing the book and can remove this book from editable shelves (it deletes only the ShelfItem).

Group shelves UX:

- Group View Shelves tab (`/groups/<group_id>/`) lists shelves owned by the group.
- Group Edit Shelves tab (`/groups/<group_id>/edit/`) lists shelves and links to View/Edit; creation deep-links to `GET /shelves/new/?owner_group=<group_id>`.
- Shelf Edit remains the canonical shelf management page (details + items + add/remove + ordering + delete).

The users UI is API-driven using:

- `GET /api/v1/accounts/users/` (paginated list; Manager/Owner only)
- `PATCH /api/v1/accounts/users/<profile_id>/` (safe fields only; no passwords/invites)
- `POST /api/v1/accounts/users/` (creates local Django user and returns a temporary password once)
- `POST /api/v1/accounts/users/<profile_id>/reset-password/` (managed reset; temporary password shown once)

Password management:

- The top-right username links to `/profile/`.
- If `me.must_change_password=true`, product UI pages redirect to `/profile/password/` until the user changes their password.
- Self password change keeps the current login session but logs out other web sessions for that user.
- `/profile/` includes a Session management section with a "Log out all other web sessions" action.
- `/profile/` also lists active Device/API sessions (Client API bearer sessions) and allows revoking them.
- `/profile/` includes a "Connect a device/app" link to `/client-api/authorize/` to begin the human side of pairing.

User deletion, invitations, email verification, password reset flows, and MFA are intentionally not implemented yet.

The users page shows each user's LibraryGroup memberships read-only; membership mutation is handled on the Group Edit page (`/groups/<group_id>/edit/`).

## 1. UI philosophy

- Django `/admin` is the service hatch for operators and recovery. It is not the product UI.
- The product UI should not expose the service hatch as a normal nav item; it is linked from the Owner-only Server Settings page (`/server/`).
- Operator recovery posture is documented in `docs/admin.md`.
- The product UI should expose normal workflows only. Advanced controls should be hidden unless relevant to the user's role, owner flag, or object-scoped capabilities.
- The UI should not hardcode role logic in many places. It should treat `GET /api/v1/accounts/me/` as the bootstrap source of truth for:
  - identity (`username`, `email`)
  - global role (`role`) and `is_owner`
  - direct group memberships (`groups`)
  - exact membership stewardship (`groups[].is_curator`)
- Object payload capabilities are UI hints, not authorization guarantees. The UI must still handle 403/404 responses from specific endpoints.
- Do not "fix" established anti-leak 404 responses to 403 without an explicit product/security decision.
- Decorative UI punctuation and separators should not be written as HTML character entities in live templates or JavaScript-generated markup. Use semantic inline elements with CSS-generated separators, or real text only when the character is meaningful content. ARIA labels should use plain readable punctuation or words.

## 2. First UI surface

Likely top-level sections (navigation may be role-gated):

- Library (browse/search)
- Book detail (metadata, file, reading info)
- Imports (upload and latest synchronous result)
- Groups (LibraryGroups: view, curation, presentation)
- Reading (history, sessions, annotations)
- Users (management)
- Settings / system (lightweight configuration and diagnostics)
- Optional future reader UI (separate scope; not required for the first product UI)

## 3. Role-based navigation

The UI should gate navigation based on `/api/v1/accounts/me/`:

### Reader

- Sees: Library, Book detail, Reading, Settings (limited)
- Does not see: Imports, Users, advanced group controls

### Curator (group-scoped)

Curator is not a global role and is not mutually exclusive with ordinary membership. A group membership is ordinary membership; `is_curator=true` is an optional curator/stewardship flag on that exact membership.

Reader users gain scoped curation authority only for non-Public groups where their membership has `is_curator=true`. Librarian, Manager, and Owner users have broad curation authority through their global role; they may also be marked `is_curator=true` on a non-Public group as stewardship metadata.

Sees:

- Library, Book detail, Reading
- Groups section, but focused on the groups they can curate

### Librarian

- Sees: Library (+ management controls), Book detail (+ management controls), Imports, Groups (presentation + curation), Reading
- Does not see: Users

### Manager

- Sees: Everything a Librarian sees, plus Users
- May see additional system-level tools (still keep them minimal in the product UI)

### Owner

Owner is Django `is_superuser`. In the product UI, treat Owner as "Manager+".

## 4. Library browse screen

Primary endpoint:

- `GET /api/v1/library/books/` (paginated)

Recommended query params (current implementation):

- Search: `q=<text>` (title/subtitle/author/series/isbn/identifier value)
- Filters: `author=<author_id>`, `series=<series_id>`, `language=<code>`, `has_files=true|false`
- Ordering: `ordering=title|created_at|updated_at|published_date` (prefix with `-` for descending)

UI behaviors:

- Paginated list with "next/previous" and page size controls.
- Search box + filter panel.
- Each row/card should show enough metadata to disambiguate (title, authors, series if present, language, published date if present).
- If `file` is present on the book payload, show a "Download" action that links
  to the authenticated book download endpoint.
- Optional: when the user is browsing in a specific group context, the UI should show that context and use the Groups APIs for the group book list rather than mixing access logic on the client.

## 5. Book detail screen

Primary endpoint:

- `GET /api/v1/library/books/<book_id>/`

Content:

- Metadata: title/subtitle/summary/publisher/language/published_date/subjects
- Authors and series, including author biography and series summary where provided
- Librarian+ may edit an author name/biography or series name/summary from its Library browse context; readers see the same context read-only.
- Identifiers (scheme/value/source)
- File: show the stored EPUB metadata from the Book-owned file fields when present.

Reading summary (current API surface):

- "Continue reading" / "Open" uses:
  - `GET /api/v1/reading/books/<book_id>/active-session/`
- Sessions and annotations summaries can be built from:
  - `GET /api/v1/reading/sessions/` (paginated)
  - `GET /api/v1/reading/annotations/?book_id=<book_id>` (paginated)

Management controls (role-gated):

- Librarian/Manager/Owner: metadata edits (where supported by API), file management (where supported), group curation affordances.
- Curator: group-specific curation actions only where allowed.

## 6. Import screen

Visible for Librarian, Manager, or Owner.

Primary endpoints:

- Upload: `POST /api/v1/library/imports/` (multipart field name `file`)

UI behaviors:

- Upload form supporting `.epub` or `.zip` of `.epub` files.
- Disable upload controls while the synchronous import request is running.
- Show that large ZIP files may take a while.
- Show the returned result immediately (source label, counts, items).
- No stored import history, async/background job, OPF-only upload, or target
  group selection is implemented.

Non-goals:

- No Calibre `metadata.db` imports.
- No sidecar cover/assets.

## 7. LibraryGroup (Groups) screen

Primary endpoints:

- List: `GET /api/v1/library/groups/` (paginated)
- Detail: `GET /api/v1/library/groups/<group_id>/`
- Group books:
  - `GET /api/v1/library/groups/<group_id>/books/` (paginated)
  - `POST /api/v1/library/groups/<group_id>/books/` body `{"book": "<book_id>"}`
  - `DELETE /api/v1/library/groups/<group_id>/books/<book_id>/`
- Presentation-only updates:
  - `PATCH /api/v1/library/groups/<group_id>/` (only `description`)

UI behaviors:

- Readers should only see groups they can view. Public/Common Room follows
  normal group membership visibility.
- Group book listings must be treated as filtered by server policy; the UI must not assume group visibility implies book visibility.
- Presentation edits, grouped book management, and group-owned shelf controls should be shown when the loaded group payload has `capabilities.can_curate=true`.
- Curation controls (add/remove books) should be gated by `group.capabilities.can_curate`.

Current implemented UI:

- Group creation exists at `/groups/new/` for Owner/Manager.
- Group membership management exists on the Group Edit page for Manager/Owner.
- Group deletion is not exposed in the Product UI.

## 8. User management screen

Visible only for Manager/Owner.

Primary endpoints:

- List: `GET /api/v1/accounts/users/` (paginated)
- Detail: `GET /api/v1/accounts/users/<profile_id>/`
- Patch: `PATCH /api/v1/accounts/users/<profile_id>/` (safe fields only; no password handling)
- Create: `POST /api/v1/accounts/users/` (Manager/Owner only; returns generated temporary password once)

UI behaviors:

- `/users/` is a compact list screen with simple client-side role tabs/filters (over the currently loaded page):
  - All, Readers, Curators, Librarians, Managers, Inactive
  - Curators are detected via `groups[].is_curator` and may show a "Curates: ..." summary
- Editing is on a dedicated page: `/users/<profile_id>/edit/`.
- For Manager/Owner, the user edit page includes user-centric group membership management (add/update/remove).
- Membership editors use ordinary membership plus a Curator checkbox/toggle, not a Reader/Curator role selector. Displays may show Member and Curator indicators separately.
- Show safe editable fields (email, first_name, last_name, is_active, role) on the edit page.
- Make role editing rules explicit in the UI:
  - Owner-only Manager promotion/demotion
  - Managers cannot manage Owner accounts, other Managers, or their own role
- Include a Create User flow at `/users/new/`:
  - Manager may create Librarian/Reader users only
  - Owner may create Manager/Librarian/Reader users
  - A server-generated temporary password is shown once and must be copied immediately

## 9. Reading metadata screens

Reading data belongs to the authenticated user and should remain durable/exportable.

Primary endpoints:

- Sessions: `GET /api/v1/reading/sessions/` (paginated), `GET /api/v1/reading/sessions/<id>/`, `PATCH /api/v1/reading/sessions/<id>/` (only `name`, `notes`)
- Active session entrypoint: `GET /api/v1/reading/books/<book_id>/active-session/`
- Start over: `POST /api/v1/reading/books/<book_id>/start-over/`
- Progress: `GET/PUT/PATCH /api/v1/reading/sessions/<session_id>/progress/`
- Annotations: `GET /api/v1/reading/annotations/` (paginated), supports `?book_id=...`, `?session_id=...`, `?include_deleted=true`

UI behaviors:

- Sessions list (by default newest-first in UI; actual API ordering is server-defined).
- Annotations view with filters by book and session and a toggle for deleted items.
- Soft delete should be communicated clearly (deleted items can be shown when requested).

## 10. Shelves UI

- The top-level shelves page (`/shelves/`) has two independently paginated sections:
  - Personal Shelves uses `GET /api/v1/shelves/?scope=personal`.
  - Shared Shelves uses `GET /api/v1/shelves/?scope=shared`.
  - Shared includes visible group shelves and other users' listed shelves; normal visibility rules continue to exclude other users' private shelves.
- Shelf edit (`/shelves/<shelf_id>/edit/`) is the full in-context shelf management page:
  - Uses tabs to reduce scroll:
    - Books in shelf (default): remove and reorder items with `Move up` / `Move down` and a `Move to` dropdown; changes apply immediately.
    - Add books: search and add; changes apply immediately; books already in shelf are hidden from results.
    - Details: edit name/description (and visibility for user-owned shelves only) and delete shelf.
  - Delete shelf removes the shelf and its shelf items only; it never deletes books or files.
- Shelf metadata displays put the owner identity segment first:
  - User-owned shelves use the Material Symbols `person` icon followed by `First Last <@username>` when a name exists, or `<@username>` without an empty gap when it does not.
  - Group-owned shelves use the Material Symbols `groups` icon followed by the group name.
  - Visibility and item count follow the owner identity segment with separators, for example `person Owen Benji <@owner> - Private - 17 items` or `groups Public - Private - 6 items`.
  - `profile_id` is used only for identity comparison and is never displayed.
- Shelf item positions are stored zero-based and contiguous; UI labels may show one-based positions like `#1`.
- First/last shelf items disable invalid edge moves; the `Move to` dropdown uses one-based labels and applies immediately.
- Drag/drop and per-row numeric position inputs are not implemented in the current shelf edit UI.
- Shelves are presentation/organization objects, not access control.

## 11. Implementation options (non-binding)

### Option A: Django templates

- Pros: simplest stack, minimal build tooling, integrates easily with session auth.
- Cons: richer interactivity requires more server-rendered patterns or incremental JS.

### Option B: Django templates + vanilla JS (progressive enhancement)

- Pros: still minimal dependencies, can use API directly for dynamic screens, easy to start small.
- Cons: you must design consistent client-side state and error handling without a framework.

### Option C: React SPA

- Pros: strong patterns for complex UI state and routing.
- Cons: more dependencies/tooling and a larger surface area than needed for the first iteration.

Recommendation (first pass): start with Django templates + vanilla JS progressive enhancement. Keep navigation and shell server-rendered; use the API for the dynamic parts (lists, uploads, inline edits) and rely on `/api/v1/accounts/me/` to build the initial UI state.

## 12. Known limitations

Current limitations and intentional non-goals that affect the product UI:

- LibraryGroups:
  - no public API for creating/deleting groups (groups are currently bootstrap/admin-oriented)
- Reading:
  - reading history/export exists, but there is no in-server EPUB reader UI
- Users:
  - no email-based invites or password reset flows (managed user creation/reset exists for self-host administration)

Nice to have:

- A small "system info" endpoint for build/version and configured features (optional; UI can also display a static build label).
