# Session management (design)

This document describes the planned direction for **authentication/login sessions** vs **reading sessions**. It is design documentation; current behavior may be simpler until the related models/modules are implemented.

## Terminology

- **Django web session**: the browser/product UI login session managed by Django’s session framework (cookie + server-side session).
- **UserWebSession**: planned companion model to track and revoke Django web sessions.
- **UserApiSession / ClientSession**: planned future token/session model for reader/API clients (not implemented yet).
- **ReadingSession**: a reading/progress session through a book (in `reading` app). Not related to authentication.
- **`reading.Device`**: reading attribution/context (device-like metadata), not an auth mechanism.

## Web session policy (desired)

When implemented, web session revocation should follow these rules:

- **Self password change**:
  - keeps the **current** Django web session
  - revokes **all other** Django web sessions for that user
- **Managed/admin password reset**:
  - revokes **all** Django web sessions for the target user
- **Disabling a user**:
  - revokes **all** Django web sessions for the target user
- **Future client/API sessions**:
  - once `UserApiSession` exists, the flows above should revoke client/API sessions as well

API endpoints remain authoritative; these are *policy goals* for the implementation.

## Future models (planned)

### `accounts.UserWebSession` (planned)

- `user`
- `session_key`
- `user_agent`
- `ip_address`
- `created_at`
- `last_seen_at`

### `accounts.UserApiSession` / `accounts.ClientSession` (planned)

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

## Session control module (planned)

Planned module: `accounts/session_control.py`

Functions:

- `revoke_other_web_sessions(user, current_session_key)`
- `revoke_all_web_sessions(user)`
- `revoke_all_api_sessions(user)`
- `user_changed_own_password(user, current_session_key)`
- `admin_reset_user_password(user)`
- `disable_user(user)`

These functions should be called by views/services that implement password changes, managed resets, and disable flows.

## Product UI direction (planned)

Future direction is a **Profile** page tab/section (not a separate `/profile/security/` route):

- Change password (existing `/profile/password/` remains the password form route today)
- “Log out other sessions” (revoke other Django web sessions)
- “Log out everywhere” (revoke all Django web sessions)
- Later: list/revoke API/client sessions (once API/client sessions exist)

Do not assume per-browser session listing in the first implementation; revocation-first is sufficient initially.

## Non-goals

- No MFA (yet)
- No email-based password reset (yet)
- No OIDC (yet)
- No API token/session implementation yet
- Do not conflate `reading.ReadingSession` with auth/login sessions
- `reading.Device` remains reading context until client auth/session work exists

## Implementation phases (planned)

Phase 1:

- `UserWebSession` model + middleware/hooks to track sessions
- `accounts/session_control.py`
- Password change/reset/disable flows revoke sessions correctly

Phase 2:

- Profile “Security” tab/section UI (within `/profile/`) calling the revocation actions

Phase 3:

- API/client token sessions for a reader client (`UserApiSession` / `ClientSession`)

