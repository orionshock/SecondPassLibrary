# Architecture

## Apps

Current apps:

- `core`: shared base models, policy helpers, utilities
- `accounts`: user profile, roles, current-user API
- `library`: books/authors/series, stored EPUB files, imports, LibraryGroups
- `reading`: devices, reading sessions, progress, annotations

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
- DRF **basic authentication** (convenience for local development/testing)
- DRF browsable API login/logout at `/api-auth/`
- Django admin at `/admin/` (service hatch; not the product UI)

Position:

- Django `User` is the canonical local user record.
- `accounts.UserProfile` stores the app-level global role (`manager|librarian|reader`).
- Product UI uses session auth + CSRF and the REST API under `/api/v1/`.
- Email verification, password reset flows, MFA, and invite systems are not implemented yet.

API endpoints under `/api/v1/` require authentication unless an endpoint explicitly documents otherwise.

### Future direction (intentionally deferred)

The production/self-hosted client authentication story is intentionally not settled yet. Near-term priorities are:

- Keep a stable REST/JSON API surface while the domain model hardens.
- Avoid committing to an auth protocol that would force early client/UI decisions.

Expected future options include external authentication (OIDC), reverse-proxy/auth-header setups, or other self-host-friendly approaches, but none are implemented by default today.

If/when external auth is added, it is expected to map into the same canonical Django `User` record (not replace it).

Notes for future browser UI:

- Session/CSRF behavior matters; any future web UI should account for CSRF when using session auth.
- Basic auth should not be treated as the final production/client authentication strategy.

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
