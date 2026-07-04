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

Product UI (Django templates):

- `GET /client-api/authorize/` (code entry / confirmation UI; may accept `?code=...`)
- `POST /client-api/authorize/` (approve or deny)

## Permissions / API surface

Client API bearer tokens are **reader/client tokens**, not admin/management tokens.

Allowed surface is an explicit allow-list. In current behavior, bearer tokens are enabled for:

- `GET /api/v1/accounts/me/` (read-only; bearer tokens do not allow `PATCH`)
- selected library read/download endpoints
  - supported browse endpoints may opt into `preview_books` with `include_preview_books=true`; preview items are visibility-scoped context hints with `id`, `title`, and `cover_url` only, never file/download URLs
- shelves endpoints:
  - bearer tokens may read any shelf the user can view
  - visible shelf list/detail payloads may opt into `preview_books` with `include_preview_books=true`; shelves still do not grant book access
  - bearer tokens may create/edit/delete **only** the user's own personal shelves
  - bearer tokens may add/remove/reorder items only in the user's own personal shelves
  - group-owned shelves are read-only via bearer tokens and report `can_edit: false`
  - other users' shelves are read-only when visible (listed) and report `can_edit: false`
  - `can_edit` is request-context-sensitive; product UI/session auth may allow group shelf edits according to normal group policy, but bearer auth never allows group shelf writes
  - shelf item book lists still filter each book through normal book access; shelves do not grant book access
- reading user-data endpoints (sessions/progress/annotations), strictly scoped to the token owner
  - `POST /api/v1/reading/annotations/` supports optional `Idempotency-Key` (recommended) for safe retries
  - for "continue reading" UIs: `GET /api/v1/reading/sessions/recent/?limit=10`

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
