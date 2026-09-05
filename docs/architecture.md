# Architecture

## Apps

Current apps:

- `core`: shared base models, server settings, utilities
- `accounts`: user profile, roles, current-user API
- `library`: books/authors/series, stored EPUB files, imports, LibraryGroups
- `marginalia`: Reading Sessions, Session progress, located annotations,
  archive Import/Export, and owned-Marginalia Book projections
- `shelves`: shelves and shelf items (presentation/organization; not access control)

React/TypeScript layering and Product UI contributor boundaries are documented
in [Frontend](frontend.md).

Operator recovery workflows in the Django admin are documented in
[Operations](operations.md#admin-and-repair-workflows).

## Server-wide settings

Server-wide configuration lives in the database as `core.ServerSetting` and is accessed through the cached service helpers in `core.server_settings` to avoid a DB hit on every request.

Notes:

- Settings are cached as a single dict under one Django cache key and invalidated on update.
- `ServerSetting` is **not** intended for secrets.
- Server identity is stored as `ServerSetting(server_name)`,
  `ServerSetting(server_description)`, and
  `ServerSetting(server_banner_message)`. It is edited as one Owner-only
  Product UI surface at `/server/` through `/api/v1/server/settings/`.
  Description and banner values follow the shared
  [sanitized limited HTML](api.md#sanitized-limited-html) contract; the name is
  plain text.
- `ServerSetting(advanced_library_groups_enabled)` selects Advanced or Simple
  Mode. It never defines Book visibility. The immutable [Advanced Library
  Groups Mode](advanced-library-groups.md) policy owns its UI, API, retained
  state, and transition contract.
- The special Public LibraryGroup is identified by `ServerSetting(public_group_id)` (not by a `LibraryGroup.slug` field).
- The optional Second Pass Reader web client origin uses
  `ServerSetting(second_pass_reader_web_client_url)`. A nonblank
  `SECOND_PASS_READER_WEB_CLIENT_URL` deployment value is normalized and
  synchronized into that row at container startup; runtime consumers read the
  stored value. The effective non-secret value is authenticated server context;
  it is not current-user identity or anonymous discovery data.

## Shelves

Shelves live in the `shelves` app and are strictly for presentation/organization, not access control. See `docs/permissions.md`.

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

- Django **session authentication** for the React Product UI
- Explicit **Client API bearer token authentication** on selected reader-client endpoints
- Session login at `GET/POST /login/` and CSRF-protected logout at `POST /logout/`
- Optional Django admin at `/admin/` when `SECOND_PASS_ENABLE_DJANGO_ADMIN=1`
  (service hatch; not the product UI)

Position:

- Django `User` is the canonical local user record.
- `accounts.UserProfile` stores the app-level global role (`manager|librarian|reader`).
- `accounts.UserWebSession` tracks active Django web sessions to support revocation (companion tracking only; does not replace Django sessions).
- Client API bearer sessions are represented by `accounts.UserClientSession` (bearer tokens are enabled for `/api/v1/accounts/me/`, `/api/v1/server/info/`, selected library read/download endpoints, shelves with conservative write rules, and selected Marginalia endpoints).
- Product UI uses session auth + CSRF and the REST API under `/api/v1/`.
- Authenticated server-wide display context belongs to `/api/v1/server/info/`;
  current-user identity, memberships, and user-specific capabilities belong to
  `/api/v1/accounts/me/`. Public `/.well-known/secondpass` remains a smaller
  anonymous discovery contract.
- CORS is open for API/discovery endpoints only, with credentials disabled, so
  independent browser reader clients can use bearer tokens from another origin.
  Product UI session-auth routes are intentionally not CORS-open.
- Email verification, self-service/email-based password recovery, MFA, and
  invite systems are not implemented.

Interactive password login reserves database-backed failure slots before each
credential check: 10 attempts per normalized source over 10 minutes and 5 per
NFKC-normalized, case-folded username over 15 minutes. Successful authentication
clears both relevant buckets. Bucket keys are keyed hashes rather than stored IP
addresses or usernames; expired slots are removed in bounded batches during
normal login traffic, so no scheduled cleanup service is required.

### Browser sessions and forced password changes

Django session authentication is the browser authority. Login uses Django's
normal authentication and session rotation behavior; logout is POST-only and
CSRF-protected. `accounts.UserWebSession` tracks underlying Django sessions for
targeted revocation; it is not an authentication mechanism.

Password and credential revocation form one lifecycle:

- A self-service password change verifies the current password and applies
  Django's validators. Updating the password, clearing `must_change_password`,
  and revoking every other browser session and all Client API sessions share one
  transaction. Refreshing the authentication hash retains the current browser
  session.
- A managed password reset atomically sets a generated temporary password, sets
  `must_change_password`, and revokes all existing browser and Client API
  sessions for that user.
- Disabling a managed user revokes both credential types. Both authentication
  boundaries also reject inactive users, independently of revocation cleanup.

`must_change_password` is enforced on the server, after
`AuthenticationMiddleware` has resolved the Django session user. A flagged
browser session retains only the bootstrap/current-user, password-change,
logout, Product UI shell, and supporting public/static surface needed to finish
the change. Other APIs return JSON `403` with code
`password_change_required`, never an HTML redirect.

DRF resolves opt-in bearer authentication later at each API boundary. The
middleware therefore governs Django session users only; it does not mistake a
bearer-only request for a browser session or extend the browser flag to the
bearer contract. The credentials remain distinct authorities with coordinated
revocation. See [Client API authorization](client-api-auth.md) for bearer
lifecycle details and [Frontend](frontend.md) for Product UI handling.

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
group's display name and description, saves the advanced-library-groups setting,
creates the Manager `UserProfile`, and adds the Owner as a reader
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

The primary account lifecycle paths are Owner/Manager-managed local users and
local username/password login. Django `User` remains the canonical local
account, `UserProfile.id` remains the stable server-local public `profile_id`,
and SPL roles and LibraryGroup memberships remain local authorization data.
Django admin remains an acceptable service hatch for account recovery in
self-hosted deployments.

Email is optional contact and management metadata:

- SMTP and email are not required for core SPL operation or local login.
- Email is not an identity key for local login.
- Email may appear in existing management/admin contexts, but compact/public
  user payloads must not expose it.
- Accounts must not be linked solely by email, especially unverified email.

Invite-by-email, email verification, SMTP-dependent recovery, and external
OIDC/OAuth/SAML/LDAP authentication are not implemented. Self-hosted operation
does not assume working SMTP. Client API bearer pairing is a separate bounded
flow tied to local Django users; it is not OAuth/OIDC.

Browser Product UI:

- The active React Product UI uses Django session authentication and must preserve CSRF protection for authenticated mutations.
- HTTP Basic authentication is not part of the product auth model.

Client API pairing (human code + approval + bearer token) is documented in `docs/client-api-auth.md`.

## Runtime/user data layout

All runtime and user-generated data lives under `userdata/` (ignored by Git):

```text
userdata/
  db/
  media/
  imports/
```

## File storage

EPUB files are stored content-addressed by checksum (SHA-256). Imported filenames
are transient import diagnostics only and are not stored as Book provenance;
human-readable filenames are derived from metadata when downloading/exporting.

Product policy: Books are import-only and file-backed. `Book` owns the stored
file fields directly: `book_file`, `file_format`, `checksum`, `file_size`,
and optional `cover_file`.

If an existing Book loses its `book_file` or points to a missing physical EPUB
on disk, treat that as an operator repair state. Do not delete and re-import the
Book merely to restore the EPUB, because Book deletion can destroy related user
reading data.

File and cover diagnostics use bounded structured operational logs. Storage
failures identify the action, Book id, and authenticated profile id when
available, plus the exception class and a sanitized message. They must not log
storage keys, filesystem paths, checksums, uploads, or response payloads.
Missing EPUB downloads and primary cover-storage failures return stable bounded
API errors. Old-cover deletion remains best-effort post-commit cleanup and must
not turn a successful cover replacement or clear into an API failure.

## Library import boundary

Library imports validate untrusted files and metadata before persistence, then
apply changes through cohesive import services rather than views, serializers,
or model hooks. [Imports](imports.md) owns metadata precedence, normalization,
duplicate advisories, and archive safety; module layout remains discoverable
from `backend/library/imports/`.
