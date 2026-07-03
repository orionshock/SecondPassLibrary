# Architecture

## Apps

Current apps:

- `core`: shared base models, policy helpers, utilities
- `accounts`: user profile, roles, current-user API
- `library`: books/authors/series, stored EPUB files, imports, LibraryGroups
- `reading`: reading sessions, progress, annotations
- `shelves`: shelves and shelf items (presentation/organization; not access control)

## Server-wide settings

Server-wide configuration lives in the database as `core.ServerSetting` and is accessed through the cached service helpers in `core.server_settings` to avoid a DB hit on every request.

Notes:

- Settings are cached as a single dict under one Django cache key and invalidated on update.
- `ServerSetting` is **not** intended for secrets.
- Server identity is stored as `ServerSetting(server_name)` and `ServerSetting(server_description)` and is editable via an Owner-only UI page (`/server/`) and API endpoint (`/api/v1/server/settings/`).
- `ServerSetting(advanced_library_groups_enabled)` is a Product UI preference. It does not change group permissions or disable backend group capabilities.
- The special Public LibraryGroup is identified by `ServerSetting(public_group_id)` (not by a `LibraryGroup.slug` field).

## Shelves

Shelves live in the `shelves` app and are strictly for presentation/organization, not access control. See `docs/shelves.md`.

## Service-layer rule

Keep business logic out of framework glue:

```text
views.py / commands.py / admin.py
  -> call services.py
  -> services.py performs domain operation
  -> models.py stores state
```

Avoid putting workflows in serializers, viewsets, `Model.save()`, admin classes, or signals (signals are reserved for small framework-adjacent behavior).

## Authentication (current)

Second Pass Library currently uses Django/DRF built-in authentication for local development and early API testing:

- Django **session authentication** (supports browser-based development and the DRF browsable API)
- Explicit **Client API bearer token authentication** on selected reader-client endpoints
- DRF browsable API login/logout at `/api-auth/`
- Django admin at `/admin/` (service hatch; not the product UI)

Position:

- Django `User` is the canonical local user record.
- `accounts.UserProfile` stores the app-level global role (`manager|librarian|reader`).
- `accounts.UserWebSession` tracks active Django web sessions to support revocation (companion tracking only; does not replace Django sessions).
- Client API bearer sessions are represented by `accounts.UserClientSession` (bearer tokens are enabled for `/api/v1/accounts/me/`, selected library read/download endpoints, shelves with conservative write rules, and reading user-data endpoints).
- Product UI uses session auth + CSRF and the REST API under `/api/v1/`.
- CORS is open for API/discovery endpoints only, with credentials disabled, so
  independent browser reader clients can use bearer tokens from another origin.
  Product UI session-auth routes are intentionally not CORS-open.
- Email verification, password reset flows, MFA, and invite systems are not implemented yet.

### First-run bootstrap

The normal fresh-install bootstrap path is the server-rendered Product UI at
`/setup/`. It is available only while no active Django superuser exists. Owner
authority remains represented by Django `is_superuser`; the associated
`UserProfile` uses the existing Manager app role rather than introducing a
separate Owner role.

Owner creation is performed by `accounts.bootstrap.create_first_owner()` inside
a transaction. The service checks the active-owner condition again immediately
before creation and sets a usable local password. The same setup submission
saves the server name and optional description, configures the protected Public
group's display name and description, saves the advanced-library-groups UI
preference, creates the Manager `UserProfile`, and adds the Owner as a reader
member of the Public group. The default Public display name is `Common Room`;
its internal identity and protections still come from
`ServerSetting(public_group_id)`. Email is optional metadata and no email,
invite, or SMTP flow is involved.

After an active Owner exists, `/setup/` redirects to normal login and cannot be
used to create additional Owners. `seed_dev_users` remains a local
development/demo convenience and is not an installation bootstrap mechanism.
Development and production startup wrappers apply migrations before starting
the web server; the setup view itself never creates or migrates schema.

API endpoints under `/api/v1/` require authentication unless an endpoint explicitly documents otherwise.

### Account and security posture

Second Pass Library is a self-hosted library and reading server. Its security
target is standard account and session hygiene appropriate for protecting
private library, shelf, group, and reading data. SPL should prevent obvious
privilege escalation, cross-user access, sensitive metadata leaks, and unsafe
session or bearer-token handling. It is not intended to become a general
enterprise IAM platform without a concrete product need.

The primary account lifecycle paths are Owner/Manager-managed local users,
local username/password login, and a future optional SSO/OIDC login or
just-in-time provisioning flow. Django `User` remains the canonical local
account, `UserProfile.id` remains the stable server-local public `profile_id`,
and SPL roles and LibraryGroup memberships remain local authorization data.
Django admin remains an acceptable service hatch for account recovery in
self-hosted deployments.

Email is optional contact and management metadata:

- SMTP and email are not required for core SPL operation or local login.
- Email is not an identity key and is not required for future OIDC linking.
- Email may appear in existing management/admin contexts, but compact/public
  user payloads must not expose it.
- Accounts must not be linked solely by email, especially unverified email.

Invite-by-email, email verification, and SMTP-dependent password-reset or
account-recovery workflows are not current core requirements. Future versions
may add them under an explicit policy, but self-hosted deployments must not be
assumed to have working SMTP.

### Future direction (intentionally deferred)

The production/self-hosted client authentication story is intentionally not settled yet. Near-term priorities are:

- Keep a stable REST/JSON API surface while the domain model hardens.
- Avoid committing to an auth protocol that would force early client/UI decisions.

Expected future options include external authentication (OIDC), reverse-proxy/auth-header setups, or other self-host-friendly approaches, but none are implemented by default today.

If/when external auth is added, it is expected to map into the same canonical Django `User` record (not replace it).

`accounts.ExternalIdentity` is reserved infrastructure for future external
authentication. It is not used by any active login flow. Future identity
resolution must use the normalized OIDC issuer plus opaque subject (`iss` +
`sub`), never email or username alone. A local user may have multiple external
identities, including identities from multiple providers.

Username remains the local display handle. Email is contact/display data and
may participate only in a future explicit linking policy; accounts must never
be auto-linked solely by an unverified email claim. First and last name may be
populated from claims under a future documented synchronization policy.
`UserProfile.id` remains the server-local public user identifier exposed as
`profile_id`.

External providers authenticate identity only. SPL global roles and
LibraryGroup memberships remain local authorization data. Provider groups or
claims do not grant SPL roles by default. Local password authentication remains
supported alongside any future external login.

Notes for future browser UI:

- Session/CSRF behavior matters; any future web UI should account for CSRF when using session auth.
- HTTP Basic authentication is not part of the product auth model.

Session revocation rules and terminology are documented in `docs/session-management.md`.

Client API pairing (human code + approval + bearer token) is documented in `docs/client-api-auth.md`.

## Runtime/user data layout

All runtime and user-generated data lives under `userdata/` (ignored by Git):

```text
userdata/
  db/
  media/
  static/
  logs/
  imports/
```

## File storage

EPUB files are stored content-addressed by checksum (SHA-256). Imported filenames are diagnostic context only; human-readable filenames are derived from metadata when downloading/exporting.

Product policy: Books are import-only and file-backed. While the schema allows a `Book` row to exist without a `BookFile`, normal import flows create them together and the product does not support metadata-only/fileless Books.

## Library import services (current)

The library import pipeline follows a facade + focused-module structure:

- `library/services.py`: public facade (stable import paths and test patch points)
- `library/import_services.py`: `ImportJob` staging and ZIP orchestration
- `library/epub_services.py`: EPUB parsing and normalized metadata extraction/merge
- `library/opf_services.py`: OPF sidecar parsing and merge helpers
- `library/book_import_services.py`: persistence/orchestration for new `Book` records (create-only)
- `library/cover_services.py`: cover validation/storage and embedded cover discovery
