# UI Planning

This document sketches the first product web UI for Second Pass Library at a high level, before implementation.

## Status (first UI shell)

The first minimal product UI shell now exists:

- `/` redirects to `/app/`
- `/app/` is an authenticated dashboard shell
- `/library/` is an authenticated library browse page

Implementation note: the product UI lives in the dedicated Django app `web` (not `core`).

Authentication for product UI pages is currently delegated to DRF's built-in login at `/api-auth/login/` (custom login is intentionally deferred).

Logout is POST-based (no GET logout links) and uses the existing `/api-auth/logout/`.

The library browse screen is API-driven using vanilla JS fetch calls to `GET /api/v1/library/books/` (paginated), with basic loading/error/empty states.

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
- Book detail (metadata, files, reading info)
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
- If `files` are present on the book payload, show a "Download" action that links to the BookFile download endpoint(s).
- Optional: when the user is browsing in a specific group context, the UI should show that context and use the Groups APIs for the group book list rather than mixing access logic on the client.

## 5. Book detail screen

Primary endpoint:

- `GET /api/v1/library/books/<book_id>/`

Content:

- Metadata: title/subtitle/summary/publisher/language/published_date/subjects
- Authors and series
- Identifiers (scheme/value/source)
- Files: list available `BookFile`s with per-file download links:
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
  - `PATCH /api/v1/library/groups/<group_id>/` (only `description`, `discoverability`)

UI behaviors:

- Readers should only see groups they can view (Public, listed, or direct membership).
- Group book listings must be treated as filtered by server policy; the UI must not assume "listed means all books are visible".
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

UI behaviors:

- Show safe editable fields (email, first_name, last_name, is_active, role).
- Make role editing rules explicit in the UI:
  - Owner-only Manager promotion/demotion
  - Managers cannot manage Owner accounts, other Managers, or their own role
- No user create/delete/invite/password UI yet.

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
