# Session management

This document describes **authentication/login sessions** vs **reading sessions** and the current revocation rules.

See `docs/client-api-auth.md` for Client API pairing and bearer token semantics.
See the account and security posture in `docs/architecture.md` for canonical
identity, email, recovery, and future OIDC policy.

## Terminology

- **Django web session**: the browser/product UI login session managed by Django's session framework (cookie + server-side session).
- **UserWebSession**: companion model to track and revoke Django web sessions.
- **UserClientSession**: bearer-token session for Reader/API clients (bearer tokens are enabled for `/api/v1/accounts/me/`, selected Library read/download endpoints, Shelves with conservative write rules, and selected Marginalia endpoints).
- **ReadingSession**: a reading/progress session through a Book in the `marginalia` app. Not related to authentication.

## Web session policy

Web session revocation follows these rules:

- **Self password change**:
  - keeps the **current** Django web session
  - revokes **all other** Django web sessions for that user
  - revokes all Reader Client bearer sessions
  - atomically clears `must_change_password`; revocation failure rolls back the change
- **Managed/admin password reset**:
  - revokes **all** Django web sessions for the target user
  - revokes all Reader Client bearer sessions
  - atomically sets the temporary password and `must_change_password=true`
- **Disabling a user**:
  - revokes **all** Django web sessions for the target user
- **Client API bearer sessions**:
  - revoke Client API sessions (see `revoke_all_api_sessions(user)`)

API endpoints remain authoritative; the rules below describe the intended behavior enforced by the session control module.

An authenticated Django session whose profile has `must_change_password=true`
is restricted by middleware after Django authentication. It can load the Product
UI shell, logout, read the current-user and server bootstrap endpoints, and
submit the password change. Unrelated APIs receive a bounded JSON `403` with
`code=password_change_required`. Bearer-only requests authenticate later at the
DRF boundary and are intentionally unchanged.

## Models

### `accounts.UserWebSession` (implemented)

- `user`
- `session_key`
- `user_agent`
- `ip_address`
- `created_at`
- `updated_at` (currently acts as `last_seen`)

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
- Implemented reader-client code authorization is documented in `docs/client-api-auth.md`.

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

## Product UI

The Product UI exposes basic session controls inside the **Profile** page:

- Change password (`/profile/password/`)
- "Log out other web sessions" (revoke other Django web sessions; keeps the current session)
- Client API sessions list + revoke (UserClientSession)

On a fresh install with no active Owner, Product UI entry points and the login
page direct to `/setup/`. Successful setup creates the local Owner account and
then returns the operator to the existing Django login flow. Setup does not
create a login session automatically and does not introduce email/SMTP
requirements.

## Non-goals

- No MFA
- No invite-by-email or SMTP-dependent account lifecycle requirement
- No email-based password reset
- No OIDC
- No bearer-token access to product UI/admin endpoints
- Do not conflate `marginalia.ReadingSession` with auth/login sessions

## Future possibilities

- Per-browser web session listing (revocation already exists; listing is optional).
- Additional client-session attribution on reading data (without changing reading data ownership rules).
