# Client API authorization (PIN/code design)

This document describes the planned **Client API** authentication flow used by future reader clients.

Goals:

- Keep the server's human authentication as normal Django web login/session.
- Avoid redirect URI / custom URL scheme complexity for early reader clients.
- Support "server and client may be on different devices" (copy/paste a URL or type a code).
- Avoid OAuth/OIDC for v1 (this is not an OAuth provider).

Status:

- Phase 1 (credential lifecycle + browser authorization + bearer token) is implemented.
- Phase 2 (bearer token access to **library read/download** APIs) is implemented.
- Bearer token access to **reading** write endpoints remains future work.

## 1. Terms

- **Client API**: A subset of the server API intended for non-browser clients (reader apps). Authenticated via bearer tokens issued by the server.
- **Reader client**: A separate project/app (mobile/desktop/etc.) that connects to a Second Pass Library server and uses the Client API.
- **ClientLoginRequest**: A short-lived server-side object representing a pending "pair this client" request, created by a reader client and authorized by a human in a browser session.
- **UserClientSession**: A long-lived (or semi-long-lived) server-side record representing a bearer token granted to a reader client for a specific user.
- **Django web session**: Browser/product UI login session managed by Django sessions (cookie + server-side session rows).
- **ReadingSession**: A reading/progress session through a book in the `reading` domain model. Not related to authentication.

## 2. Core flow

High-level: the reader client creates a login request, a human authorizes it in the browser, then the reader client polls until it receives a bearer token **once**.

### Reader client

1. User enters the server URL (e.g. `https://example-server/`).
2. Client calls `POST /api/v1/client-api/login-requests/` with basic client metadata.
3. Server returns:
   - `id` (request UUID)
   - `code` (short human code; not a bearer credential, but should still be unpredictable enough)
   - `authorize_url` (a product-UI URL the user can open in a browser; preferably includes the code as a query param)
   - `poll_url`
   - `expires_at`
   - `poll_interval_seconds` (recommended)
4. Client displays the authorize URL and/or the code.

### Human / browser

1. User opens `authorize_url` in a browser.
2. If needed, user logs in via normal Django session auth.
3. Server shows: "Authorize this reader/client?"
4. User approves or denies.

### Reader client

1. Client polls `poll_url` using the request id.
2. Server returns a status:
   - `pending`: not approved yet
   - `approved`: returns a bearer token **once** (then the request becomes `consumed`). `approved` always includes the token.
   - `denied` / `expired`: terminal
3. Client stores a connection profile and uses `Authorization: Bearer <token>` for future Client API requests.

Notes:

- The bearer token is a **client token** (reader token), not a browser session token.
- The browser never sees the bearer token; only the client receives it from the poll endpoint.

## 3. Models (planned)

### `ClientLoginRequest` (planned)

- `id` (UUID)
- `code_hash`
- `client_name` (string; user-visible)
- `client_type` (string enum-ish; e.g. `ios|android|desktop|cli|other`)
- `status` (`pending|approved|denied|consumed|expired`)
- `approved_by` (nullable `User`)
- `expires_at`
- `approved_at` (nullable)
- `consumed_at` (nullable)
- `created_at`
- Diagnostics (optional):
  - `originating_ip` (nullable)
  - `originating_user_agent` (nullable)

### `UserClientSession` (planned)

- `id` (UUID)
- `user` (FK)
- `name` (string; user-visible, default from client_name)
- `client_type` (string)
- `token_hash`
- `created_at`
- `last_seen_at` (nullable)
- `expires_at` (nullable)
- `revoked_at` (nullable)

Raw tokens are never stored:

- Only a one-way hash (e.g. `token_hash`) is persisted.
- The raw bearer token is shown/returned to the client exactly once.

## 4. Endpoints (planned)

### Planned Client API (JSON)

- `GET /api/v1/client-api/discovery/`
  - Returns server capabilities relevant to clients (version, auth methods supported, suggested poll interval, etc.).
- `POST /api/v1/client-api/login-requests/`
  - Creates a `ClientLoginRequest` and returns code + URLs.
- `GET /api/v1/client-api/login-requests/<id>/poll/`
  - Returns `pending` or a token once after approval.

### Planned Product UI (Django templates)

- `GET /client-api/authorize/`
  - Code entry / confirmation UI (can accept `?code=...` for convenience).
- `POST /client-api/authorize/`
  - Approve or deny the login request.

## 5. Security rules

- The code expires quickly (target: ~10 minutes).
- The code is random enough to be safe to type/read and not easily guessable.
- The code is stored hashed (`code_hash`) and never stored as plaintext.
- Request id is an unguessable UUID.
- Polling responses should include a recommended interval and the server should enforce rate limiting (or server-side throttling) for polling.
- Token is returned only once; after it is issued, the login request transitions to `consumed`.
- Token is stored hashed server-side (`token_hash`), never raw.
- Approving requires an authenticated Django web session.
- Denied/expired/consumed requests cannot be reused.

## 6. Permissions / API surface

Initial Client API tokens are **reader/client tokens**, not admin/management tokens.

Allowed future surface (explicit allow-list; subject to change as endpoints are implemented):

- `/api/v1/accounts/me/`
- Library read/download endpoints
- Reading endpoints: sessions/progress/annotations (user-owned data)
- Possibly read-only shelves

Management endpoints should reject Client API tokens by default unless explicitly allowed later.

There is no full OAuth-style scope system in v1. If implementation needs a minimal mechanism, prefer a simple internal capability/allow-list check rather than a user-configurable scope framework.

## 7. Session control integration

When `UserClientSession` exists, session control should treat these as API/client sessions:

- `revoke_all_api_sessions(user)` revokes active client sessions.
- Self password change revokes client sessions.
- Managed password reset revokes client sessions.
- Disabling a user revokes client sessions.
- Profile UI can later list/revoke client sessions.

## 8. UI direction

### Server authorize page

- Code lookup/confirmation (and/or `?code=` deep-link).
- Show client name/type to the user.
- Approve / deny buttons.

### Profile page (future)

- List Client API sessions (minimal metadata: name/type/created/last-seen).
- Revoke button(s).

## 9. Non-goals

- No OAuth provider implementation.
- No OIDC.
- No redirect URI / custom scheme requirement.
- No client secrets.
- No MFA in this flow.
- No reader rendering in the server product UI.

## 10. Implementation phases

Phase 1:

- Models (`ClientLoginRequest`, `UserClientSession`)
- Discovery endpoint (`/.well-known/secondpass` and `GET /api/v1/client-api/discovery/`)
- Create login request endpoint (`POST /api/v1/client-api/login-requests/`)
- Authorize page (GET/POST `/client-api/authorize/`)
- Poll endpoint (`GET /api/v1/client-api/login-requests/<id>/poll/`)
- Bearer token authentication (enabled on `/api/v1/accounts/me/` only)
- Phase 1 guardrail: bearer tokens can `GET /api/v1/accounts/me/` but cannot `PATCH /api/v1/accounts/me/`.

Phase 2:

- Allow tokens on library read + download endpoints (explicit allow-list)
- Explicitly reject library/import/group-management endpoints for Client API tokens
- Allow tokens on reading user-data endpoints (explicit allow-list; user-owned and strictly scoped to the token owner)

Phase 3:

- Profile UI list/revoke Client API sessions

## Key decisions

- Use a PIN/code authorization flow to avoid redirect URI/custom scheme complexity.
- Keep human authentication as Django web login/session.
- Treat reader tokens as a separate authentication mechanism (bearer tokens), stored hashed and issued once.
- Prefer explicit allow-listing of Client API token permissions rather than a general-purpose scope system in v1.

## Open questions

- Code format: digits only vs alphanumeric, length, and error tolerance (e.g. grouping `ABCD-EFGH`).
- Polling semantics: long-poll vs short-poll, server throttling strategy, and recommended interval defaults.
- Token lifetime: expiring vs non-expiring tokens, rotation strategy, and how "last_seen_at" is updated.
- Whether to add optional client-session attribution fields to reading data (not implemented in v1).
