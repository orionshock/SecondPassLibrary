# Session management (design)

This document describes the direction for **authentication/login sessions** vs **reading sessions**.

Status:

- Phase 1 (web session tracking + revocation) is implemented.
- Phase 1 Client API sessions (PIN/code authorize + bearer token) are implemented (bearer token is enabled for `/api/v1/accounts/me/` only).

See `docs/client-api-auth.md` for the planned PIN/code authorization flow for reader clients.

## Terminology

- **Django web session**: the browser/product UI login session managed by Django’s session framework (cookie + server-side session).
- **UserWebSession**: planned companion model to track and revoke Django web sessions.
- **UserClientSession**: bearer-token session for reader/API clients (implemented; Phase 1 enables bearer auth for `GET /api/v1/accounts/me/` only).
- **ReadingSession**: a reading/progress session through a book (in `reading` app). Not related to authentication.

## Web session policy

Web session revocation follows these rules:

- **Self password change**:
  - keeps the **current** Django web session
  - revokes **all other** Django web sessions for that user
- **Managed/admin password reset**:
  - revokes **all** Django web sessions for the target user
- **Disabling a user**:
  - revokes **all** Django web sessions for the target user
- **Client API bearer sessions**:
  - revoke Client API sessions (see `revoke_all_api_sessions(user)`)

API endpoints remain authoritative; these are *policy goals* for the implementation.

## Models

### `accounts.UserWebSession` (implemented)

- `user`
- `session_key`
- `user_agent`
- `ip_address`
- `created_at`
- `updated_at` (used as `last_seen` for now)

### `accounts.UserClientSession` (implemented)

- `user`
- `name`
- `client_type`
- `token_hash`
- `created_at`
- `last_seen_at`
- `expires_at`
- `revoked_at`

Notes:

- Raw API tokens are **never** stored.
- Only token hashes are stored (e.g., `token_hash`).
- Planned reader-client auth flow is documented in `docs/client-api-auth.md`.

## Session control module

Module: `accounts/session_control.py`

Functions:

- `revoke_other_web_sessions(user, current_session_key)`
- `revoke_all_web_sessions(user)`
- `revoke_all_api_sessions(user)`
- `user_changed_own_password(user, current_session_key)`
- `admin_reset_user_password(user)`
- `disable_user(user)`

These functions should be called by views/services that implement password changes, managed resets, and disable flows.

## Product UI direction (planned)

The Product UI exposes basic web session controls inside the **Profile** page (not a separate `/profile/security/` route):

- Change password (existing `/profile/password/` remains the password form route today)
- “Log out other web sessions” (revoke other Django web sessions; keeps the current session)
- “Log out everywhere” (revoke all Django web sessions)
- Later: list/revoke API/client sessions (once API/client sessions exist)

Do not assume per-browser session listing in the first implementation; revocation-first is sufficient initially.

## Non-goals

- No MFA (yet)
- No email-based password reset (yet)
- No OIDC (yet)
- No bearer-token access to product UI/admin endpoints
- Do not conflate `reading.ReadingSession` with auth/login sessions


## Implementation phases

Phase 1 (implemented):

- `UserWebSession` model + middleware/hooks to track sessions
- `accounts/session_control.py`
- Password change/reset/disable flows revoke sessions correctly

Phase 2:

- Profile session management section (within `/profile/`) calling the revocation actions (implemented: logout other web sessions)

Phase 3:

- Profile UI listing/revocation for Client API sessions (UserClientSession)
