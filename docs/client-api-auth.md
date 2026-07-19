# Client API authorization

This document describes the **Client API** pairing flow (human code + browser approval) and bearer token semantics for reader clients.

## Current behavior

### Goals

- Keep human authentication as normal Django web login/session.
- Avoid redirect URI / custom URL scheme complexity for early reader clients.
- Support "server and client may be on different devices" (copy/paste a URL or type a short code).
- This is not an OAuth/OIDC provider.

### Terms

- **Client API**: a subset of the server API intended for non-browser clients. Authenticated via server-issued bearer tokens.
- **Reader client**: a separate app (mobile/desktop/etc.) that connects to a Second Pass Library server and uses the Client API.
- **ClientLoginRequest**: a short-lived server-side object representing a pending "pair this client" request, created by a reader client and authorized by a human in a browser session.
- **UserClientSession**: a server-side record representing a bearer token granted to a reader client for a specific user.
- **Django web session**: browser/product UI login session managed by Django sessions (cookie + server-side session rows).
- **ReadingSession**: a reading/progress session through a book in the `reading` domain model. Not related to authentication.

## Pairing flow (code + approve + poll)

High-level: the reader client creates a login request, a human authorizes it in the browser, then the reader client polls until it receives a bearer token **once**.

### Reader client

1. User enters the server base URL (e.g. `https://example-server/`).
2. Client calls `POST /api/v1/client-api/login-requests/` with basic client metadata.
3. Server returns:
   - `id` (request UUID)
   - `code` (short human code; not a bearer credential)
   - `authorize_url` (browser URL the user can open; may include the code as a query param)
   - `poll_url`
   - `expires_at`
   - `interval` (recommended poll interval in seconds)
4. Client displays the authorize URL and/or the code.

### Human / browser

1. User opens `authorize_url` in a browser.
2. If needed, user logs in through any supported flow that establishes a
   normal authenticated Django browser session. This is local password login
   today and may include optional external login in the future.
3. Server shows an approval screen: "Authorize this device/app?".
4. User approves or denies.

### Reader client

1. Client polls `poll_url` using the request id.
2. Server returns a status:
   - `pending`: not approved yet
   - `approved`: returns a bearer token **once** (then the request becomes `consumed`)
   - `denied` / `expired`: terminal
3. Client stores a connection profile and uses `Authorization: Bearer <token>` for future Client API requests.

Notes:

- The bearer token is a **client credential**, not a browser session token.
- The browser never receives the bearer token; only the reader client receives it from the poll endpoint.

## Models

### `ClientLoginRequest`

Key fields (conceptual):

- `id` (UUID)
- `code_hash` (code is never stored in plaintext)
- `client_name`, `client_type`
- `status` (`pending|approved|denied|consumed|expired`)
- `expires_at`, `approved_at`, `consumed_at`

### `UserClientSession`

Key fields:

- `id` (UUID)
- `user`
- `name`, `client_type`
- `token_hash` (raw tokens are never stored)
- `created_at`, `last_seen_at`, `expires_at`, `revoked_at`

## Endpoints

Client API (JSON):

- `GET /.well-known/secondpass` returns compact server identity and `api_base_url`.
- `{api_base_url}client-api/discovery/`
- `{api_base_url}client-api/login-requests/`
- `{api_base_url}client-api/login-requests/{id}/poll/`

`/.well-known/secondpass` is public server identity/discovery only. It includes
`server_description`, but not banner text, advanced library group state,
capabilities, or route manifests. Reader clients should use authenticated
`GET /api/v1/accounts/me/` as refreshable context after pairing; `/me` includes
`advanced_library_groups_enabled` for group browsing UI and `banner_text` for
the single server banner.

Product UI (Django templates):

- `GET /client-api/authorize/` (code entry / confirmation UI; may accept `?code=...`)
- `POST /client-api/authorize/` (approve or deny)

## Permissions / API surface

Client API bearer tokens are **reader/client tokens**, not admin/management tokens.

Allowed surface is an explicit allow-list.

| Domain | Bearer access | Notes |
| --- | --- | --- |
| `GET /api/v1/accounts/me/` | read-only | Refreshes current user, role, group membership summary, banner text, and advanced-groups state. Bearer `PATCH` is rejected. |
| `/api/v1/library/` Books, Authors, Series, Tags | read-only | List/detail endpoints are visibility-scoped. Book detail exposes `file.download_url` and visibility-scoped `groups` summaries; Book list rows do not include groups. |
| `/api/v1/library/books/<book_id>/download/` | read-only | Streams the complete visible canonical EPUB as an `application/epub+zip` attachment. Byte Range responses are not currently supported. |
| `/api/v1/library/groups/` and group-scoped Books/Auth/Series/Tags | read-only | Group reads require group visibility. Simple mode exposes Public/Common Room only. |
| `/api/v1/reading/` sessions/progress/annotations | read/write for owned reading state | Bearer mutations are limited to the token owner's sessions, progress, and annotations. Writes that open/read/write a book require current book visibility. |
| `/api/v1/shelves/` | read visible shelves; mutate own personal shelves only | Bearer may create/edit/delete the token user's personal shelves and add/move/remove items there. Group shelves and other users' shelves are read-only when visible. |

Library details:

- Bearer credentials are read-only under `/api/v1/library/` regardless of
  account role; mixed endpoint writes still require Django session auth.
- Books, Authors, Series, Catalog Tags, visible LibraryGroups, and visible
  group-scoped Books/Auth/Series/Tags are bearer-readable.
- Book, Author, and Series browse filters use `tag=<tag-slug>`; UUID tag
  filters are not part of the client contract.
- All results, counts, filters, and pagination are scoped to books visible to
  the token owner; inaccessible details and groups return `404`.
- Book detail `groups` contains the same visibility-scoped group summaries as
  session-authenticated detail (`id`, `name`, `description`, and
  `is_public_group`). It contains no membership or user data. In simple mode,
  only Public/Common Room can appear.
- Author, Series, Group, and Shelf list/detail payloads may opt into
  `preview_books` with `include_preview_books=true`; preview items contain only
  `id`, `title`, and `cover_url`, never file/download URLs. Group-scoped Author
  and Series lists also support the same opt-in. Tag endpoints do not currently
  attach preview books.
- `/media/books/` is not public. Reader clients must use Book detail
  `file.download_url` and the authenticated download endpoint for EPUB bytes.
  Storage names and paths are never returned. Cover URLs remain public display
  assets under `/media/covers/`.

Reading details:

- Bearer clients should use normal Reading API endpoints for sync:
  sessions, progress, annotations, `open`, `start-over`, `close`,
  `recent`, and activity summary.
- `POST /api/v1/reading/annotations/` supports optional `Idempotency-Key`
  (recommended) for safe retries.
- For "continue reading" UIs, use
  `GET /api/v1/reading/sessions/recent/?limit=10`.
- Marginalia import/export endpoints are **session-only** and reject Client API
  bearer tokens:
  - `GET/POST /api/v1/reading/export/`
  - `POST /api/v1/reading/import/preview/`
  - `POST /api/v1/reading/import/apply/`
  - `GET /api/v1/reading/import/unmatched/?import_token=<token>`

Shelves details:

- Bearer tokens may read any shelf the user can view.
- Visible shelf list/detail payloads may opt into `preview_books` with
  `include_preview_books=true`; shelves still do not grant book access.
- Bearer tokens may create/edit/delete **only** the user's own personal shelves.
- Bearer tokens may add/remove/reorder items only in the user's own personal
  shelves.
- Group-owned shelves are read-only via bearer tokens and report
  `can_edit: false`.
- Other users' shelves are read-only when visible/listed and report
  `can_edit: false`.
- Shelf item book lists still filter each book through normal book access;
  shelves do not grant book access.

Explicitly session-only or bearer-denied surfaces:

- Library mutations: Book metadata/tag PATCH, Author/Series PATCH, cover
  upload/clear, Library import upload, group create/update/delete, group book
  assignment mutation, and group membership list/mutation.
- Account/user management: managed users, user choices, password changes, web
  session management, and Product UI/admin endpoints.
- Reading marginalia import/export listed above.

Management endpoints reject Client API tokens unless explicitly allowed.

## Security rules

- The human code expires quickly.
- The code and bearer token are stored hashed server-side; raw values are never stored.
- Poll returns the bearer token only once (approval transitions to `consumed` after delivery).
- Approving requires an authenticated Django web session.
- Denied/expired/consumed requests cannot be reused.

## Product UI integration

- `/profile/` lists active Device/API sessions (Client API sessions) for the current user and allows revoking them.
- `/profile/` links to `/client-api/authorize/` to begin the human side of pairing.

## Non-goals

- No OAuth provider implementation.
- No OIDC.
- No redirect URI / custom scheme requirement.
- No client secrets.
- No bearer-token access to product UI/admin endpoints.
- No reader rendering in the server product UI.

## Future possibilities

- Token lifetime/rotation policy (expiring vs non-expiring tokens).
- Server-side throttling/rate limiting policy for polling.
- Optional client-session attribution fields on reading data (without changing reading data ownership rules).
