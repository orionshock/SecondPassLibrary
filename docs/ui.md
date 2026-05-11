# UI Planning

This document sketches the first product web UI for Second Pass Library at a high level, before implementation.

## Status (first UI shell)

The first minimal product UI shell now exists:

- `/` redirects to `/app/`
- `/app/` is an authenticated dashboard shell
- `/app/` is a placeholder dashboard (future activity widgets are intentionally not implemented yet)
- `/profile/` is the authenticated self account page (identity + groups + capabilities + self-profile edit)
- `/profile/password/` is the authenticated self password change page
- `/library/` is an authenticated library browse page
- `/library/books/<book_id>/` is an API-driven book detail page (functional-first)
- `/library/books/<book_id>/edit/` is an API-driven book metadata edit page (Manager/Librarian/Owner only)
- `/imports/` is an API-driven imports page (upload + job list/results)
- `/groups/` is an authenticated group list page
- `/groups/<group_id>/` is an authenticated group view page (Books/Members/Shelves tabs; read-oriented)
- `/groups/<group_id>/edit/` is an authenticated group management page (Details/Books/Members/Shelves tabs; management-oriented)
- `/users/` provides functional user management for Manager/Owner only
- `/users/new/` provides functional local user creation for Manager/Owner (generated temporary password shown once)
- `/users/<user_id>/edit/` provides a dedicated user edit screen for Manager/Owner

Implementation note: the product UI lives in the dedicated Django app `web` (not `core`).

UI JavaScript is split into page-focused vanilla ES modules under `web/static/web/js/` and loaded via a single `<script type="module">` entrypoint (`web/static/web/js/main.js`). There is no frontend build step.

Authentication for product UI pages is currently delegated to DRF's built-in login at `/api-auth/login/` (custom login is intentionally deferred).

Logout is POST-based (no GET logout links) and uses the existing `/api-auth/logout/`.

The library browse screen is API-driven using vanilla JS fetch calls to `GET /api/v1/library/books/` (paginated), with basic loading/error/empty states.

The book detail page is API-driven using `GET /api/v1/library/books/<book_id>/` and renders metadata, identifiers, and file download links (from `download_url`).

The book detail page also shows the book's assigned LibraryGroups (filtered for Readers/Curators to only viewable groups) with links to the group pages.

The book metadata edit page is organized into client-side tabs (Metadata, Authors & Series, Library Groups, Shelves, Identifiers & File Info). It is API-driven using `PATCH /api/v1/library/books/<book_id>/` and supports basic metadata fields plus author/series editing. `series_index` supports integers or one decimal place. Author and series can be selected from existing records or created by name. Book identifiers can be added/edited/deleted here. LibraryGroup assignments can be added/removed here. The Shelves tab is a placeholder only. The Identifiers & File Info tab includes read-only BookFile info; the stored EPUB is not edited from this page.

The imports page is API-driven using:

- `GET /api/v1/library/imports/` (paginated job list)
- `POST /api/v1/library/imports/` (multipart upload field `file`)

It intentionally supports only `.epub` and simple `.zip` of EPUBs (no Calibre library imports, OPF sidecars, or PDF).

The groups UI is API-driven using:

- `GET /api/v1/library/groups/` (paginated list)
- `GET /api/v1/library/groups/<group_id>/` (detail)
- `PATCH /api/v1/library/groups/<group_id>/` (presentation fields only: description)
- `GET /api/v1/library/groups/<group_id>/books/` (paginated)
- `GET /api/v1/library/books/?q=<search>` (book search for the Groups UI picker)
- `POST /api/v1/library/groups/<group_id>/books/` (add book by id from picker)
- `DELETE /api/v1/library/groups/<group_id>/books/<book_id>/` (remove)
- Memberships:
  - `GET /api/v1/library/groups/<group_id>/memberships/` (paginated; visible to group members + managers/owners/librarians + Public viewers)
  - `POST/PATCH/DELETE /api/v1/library/groups/<group_id>/memberships/...` (Manager/Owner only)

Note: `LibraryGroup.slug` is currently shown in the product UI as diagnostic/internal-facing context only (group routes use UUIDs). Public is still identified internally by `slug="public"`.

The users UI is API-driven using:

- `GET /api/v1/accounts/users/` (paginated list; Manager/Owner only)
- `PATCH /api/v1/accounts/users/<id>/` (safe fields only; no passwords/invites)
- `POST /api/v1/accounts/users/` (creates local Django user and returns a temporary password once)
- `POST /api/v1/accounts/users/<id>/reset-password/` (managed reset; temporary password shown once)

Password management:

- The top-right username links to `/profile/`.
- If `me.must_change_password=true`, product UI pages redirect to `/profile/password/` until the user changes their password.

User deletion, invitations, email verification, password reset flows, and MFA are intentionally not implemented yet.

The users page shows each user's LibraryGroup memberships read-only; membership mutation is handled on the Group Edit page (`/groups/<group_id>/edit/`).

## 1. UI philosophy

- Django `/admin` is the service hatch for operators and recovery. It is not the product UI.
- The product UI should expose normal workflows only. Advanced controls should be hidden unless relevant to the user's role/capabilities.
- The UI should not hardcode role logic in many places. It should treat `GET /api/v1/accounts/me/` as the bootstrap source of truth for:
  - identity (`username`, `email`)
  - global role (`role`) and `is_owner`
  - broad UI hints (`capabilities`)
  - direct group memberships (`groups`)
  - scoped curator power (`curated_group_ids`)
- Capabilities are UI hints, not authorization guarantees. The UI must still handle 403/404 responses from specific endpoints.

## 2. First UI surface

Likely top-level sections (navigation may be role-gated):

- Library (browse/search)
- Book detail (metadata, file, reading info)
- Imports (upload and import job history)
- Groups (LibraryGroups: view, curation, presentation)
- Reading (history, sessions, annotations, devices)
- Users (management)
- Settings / system (lightweight configuration and diagnostics)
- Optional future reader UI (separate scope; not required for the first product UI)

## 3. Role-based navigation

The UI should gate navigation based on `/api/v1/accounts/me/`:

### Reader

- Sees: Library, Book detail, Reading, Settings (limited)
- Does not see: Imports, Users, advanced group controls

### Curator (group-scoped)

Curator is a membership role, not a global role. A curator typically has global `role=reader` but will have:

- `curated_group_ids` non-empty and `capabilities.can_edit_group_presentation=true`

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
- If `file` is present on the book payload, show a "Download" action that links to the BookFile download endpoint.
- Optional: when the user is browsing in a specific group context, the UI should show that context and use the Groups APIs for the group book list rather than mixing access logic on the client.

## 5. Book detail screen

Primary endpoint:

- `GET /api/v1/library/books/<book_id>/`

Content:

- Metadata: title/subtitle/summary/publisher/language/published_date/subjects
- Authors and series
- Identifiers (scheme/value/source)
- File: show the stored EPUB `BookFile` (if present) with a download link:
  - `GET /api/v1/library/book-files/<book_file_id>/download/`

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

Visible only when `capabilities.can_access_imports=true` (currently Librarian/Manager/Owner).

Primary endpoints:

- Upload: `POST /api/v1/library/imports/` (multipart field name `file`)
- List jobs: `GET /api/v1/library/imports/` (paginated)
- Job detail: `GET /api/v1/library/imports/<job_id>/`

UI behaviors:

- Upload form supporting `.epub` or `.zip` of `.epub` files.
- Show the created job result immediately (status, counts, items).
- Job history view with paging and detail drill-in.

Non-goals:

- No Calibre imports yet.

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

- Readers should only see groups they can view (Public or direct membership).
- Group book listings must be treated as filtered by server policy; the UI must not assume group visibility implies book visibility.
- Presentation edits should be shown only when the user has broad capability (or scoped curator power for that group).
- Curation controls (add/remove books) should be gated similarly.

Constraints:

- No membership management UI yet (no public API for adding/removing users or assigning curator roles).
- No public UI for creating/deleting groups yet (admin/service hatch only).

## 8. User management screen

Visible only for Manager/Owner (`capabilities.can_manage_users=true`).

Primary endpoints:

- List: `GET /api/v1/accounts/users/` (paginated)
- Detail: `GET /api/v1/accounts/users/<user_id>/`
- Patch: `PATCH /api/v1/accounts/users/<user_id>/` (safe fields only; no password handling)
- Create: `POST /api/v1/accounts/users/` (Manager/Owner only; returns generated temporary password once)

UI behaviors:

- `/users/` is a compact list screen with simple client-side role tabs/filters (over the currently loaded page):
  - All, Readers, Curators, Librarians, Managers, Inactive
  - Curators are detected via group membership role (`membership_role == curator`) and show a "Curates: ..." summary
- Editing is on a dedicated page: `/users/<user_id>/edit/`.
- When allowed (`capabilities.can_manage_group_memberships`), the user edit page includes user-centric group membership management (add/update/remove).
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
- Devices: `GET /api/v1/reading/devices/` (paginated) and per-device CRUD (user-scoped)

UI behaviors:

- Sessions list (by default newest-first in UI; actual API ordering is server-defined).
- Annotations view with filters by book and session and a toggle for deleted items.
- Soft delete should be communicated clearly (deleted items can be shown when requested).

## 10. Future shelves (not implemented yet)

- Shelves are presentation/organization objects, not access control.
- Likely future direction:
  - user-owned shelves
  - group-owned shelves
- Shelf membership must not grant book access; each book must still pass `can_view_book`.

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

## 12. API gaps before UI

These gaps are likely to block or significantly complicate a first product UI:

- LibraryGroups:
  - no public API for creating/deleting groups
  - no public API for managing group memberships (adding/removing users, assigning curator roles)
- Reading:
  - sessions list has no server-side filter/query params documented for common UI needs (e.g., filter by `book_id`, active-only); the UI can work around this initially, but it will not scale well
- Users:
  - no user create/invite flow yet (acceptable for bootstrap/admin usage, but limits self-host onboarding UX)

Non-blocking but useful:

- A small "system info" endpoint for build/version and configured features (optional; can also be static in the UI for now).
