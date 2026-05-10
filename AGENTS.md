# Second Pass Library - Agent Coding Guidelines

These guidelines exist to keep the codebase simple, maintainable, and aligned with the project goals.

## Project Identity

Second Pass Library is a self-hosted EPUB-focused reading system.

It provides:

- EPUB library management
- User-owned reading metadata
- Reading progress
- Highlights, notes, and bookmarks
- Reading sessions / reread support
- A stable REST/JSON API for future reader clients

It is not:

- A Kindle clone dependent on Amazon or cloud services
- A SaaS-first multi-tenant platform
- A PDF annotation system
- An AI-powered product
- A general document-management system

## Core Principles

- Self-hosted first.
- EPUB first.
- SQLite-first, PostgreSQL-compatible later.
- Boring, conventional Django is preferred.
- Business logic lives in explicit service modules, not framework glue.
- Avoid clever abstractions unless they solve a current problem.
- Favor explicit code over magical behavior.
- User data must be durable, exportable, and not silently destroyed.
- Do not add features outside the current requested scope.

## Architecture Rules

### Keep business logic out of framework glue

**Business logic should live in explicit service modules, not in DRF serializers, views/viewsets, model `save()` methods, or signals.**

Business/domain logic should live in explicit service modules, not in:

- DRF serializers
- DRF views/viewsets
- Django model `save()` methods
- Django signals
- Django admin classes
- management commands

Preferred pattern:

```text
views.py / commands.py / admin.py
  -> call services.py
  -> services.py performs business operation
  -> models.py stores state
```

Examples:

```text
Good:
library/services.py::import_epub()
reading/services.py::get_or_create_active_session()
reading/services.py::start_new_reading_session()

Avoid:
Putting import logic directly in a management command.
Putting session rollover logic directly in a view.
Putting metadata extraction in BookFile.save().
```

### Models should describe data, not orchestrate workflows

Models may contain:

* field definitions
* constraints
* simple helper properties
* simple display helpers
* small validation helpers

Models should not contain:

* file import workflows
* sync behavior
* API-specific logic
* cross-model orchestration
* external service calls

### Serializers should serialize

DRF serializers may:

* validate simple input
* expose safe fields
* create/update straightforward model records

Serializers should not contain major business workflows.

If serializer logic starts coordinating multiple models, move that logic to a service.

### Views should coordinate HTTP, not domain behavior

DRF views/viewsets may:

* enforce authentication
* scope querysets to the current user
* parse request inputs
* call service functions
* return responses

Views should not contain large business logic.

### Signals should be rare

Signals are allowed only for simple framework-adjacent behavior, such as:

* creating a `UserProfile` when a Django `User` is created

Do not use signals for core workflows like importing books, creating reading sessions, sync, or annotation processing.

## App Boundaries

Current apps:

```text
core      -> shared base models, health checks, utilities
accounts  -> user profile, roles, current-user API
library   -> books, authors, series, EPUB files, import
reading   -> devices, reading sessions, progress, annotations
```

Do not create new apps unless there is a clear domain boundary.

## Data Ownership Rules

### Books and files

* A `Book` represents the conceptual work.
* A `BookFile` represents the stored EPUB file (one Book has at most one BookFile).
* EPUB files are stored content-addressed by SHA-256.
* Imported filenames are only fallback/diagnostic context.
* Human-readable filenames should be generated from metadata when exporting or downloading.

### Identifier Position

* `Book.isbn` is a convenience/display field (prefer ISBN-13 when available), not the only identifier.
* Future metadata/import work should preserve non-ISBN identifiers.
* `BookIdentifier` stores external/source identifiers such as ISBN-10, ISBN-13, ASIN, DOI, OCLC, LCCN, Open Library IDs, Calibre IDs, EPUB unique identifiers, publisher IDs, URI/URN identifiers, and other source-specific identifiers.
* Duplicate EPUB detection is based on file checksum, not identifiers.

## Library Access Model

For now, the library is shared among authenticated users.

This means:

- `Book`, `Author`, `Series`, and `BookFile` APIs may expose shared library records to authenticated users.
- Reading metadata remains user-owned and must be scoped to the authenticated user.
- Future permissions may restrict book/file access, but existing reading metadata should remain recoverable/exportable by its owner.

Do not implement per-user private libraries unless explicitly requested.

### Public group

- The default shared group is the **Public** group, identified by canonical slug `public`.
- Public is protected: it should not be deleted, and it must not allow Curator memberships.
- Public is the only special built-in `LibraryGroup` right now; special behavior is based on `PUBLIC_GROUP_SLUG` / `is_public_group()`, not a boolean flag.
- Book access remains controlled by `LibraryGroupMembership` and `BookGroupAssignment`.
- Group assignment changes should go through `library.group_services.add_book_to_group()` / `remove_book_from_group()` (avoid scattered `BookGroupAssignment` writes).

### Reading metadata

Reading metadata belongs to the user.

This includes:

* reading sessions
* progress
* annotations
* highlights
* notes
* bookmarks
* devices

### EPUB locators

Reading locators are stored as flexible JSON for now. Prefer EPUB locators that include CFI and href when available, plus progression (0-1) and optional text quote context (exact/prefix/suffix) to help re-anchor highlights if a CFI fails.

Do not add PDF locator support unless explicitly requested.

Reading metadata should not be deleted just because a user starts over or loses current access to a book file.

### Sessions

Sessions are mostly invisible to users.

Expected behavior:

```text
Open book for reading
-> get or create active session

Start over
-> deactivate old active session
-> create new active session
-> preserve old progress and annotations
```

`status` describes what happened to a session.

`is_active` determines whether it is the current/default session.

## File and Runtime Data Rules

Runtime/user data belongs under:

```text
userdata/
  db/
  media/
  static/
  logs/
  imports/
```

Do not commit runtime data.

Do not store EPUB/PDF/book files in the database.

Do not expose absolute filesystem paths in the API.

## API Rules

* API routes should live under `/api/v1/`.
* APIs should be REST/JSON and boring.
* API behavior should be predictable and testable.
* Do not introduce GraphQL.
* Do not introduce a sync protocol until explicitly requested.
* Do not expose sensitive auth internals.
* Do not expose local filesystem paths.
* Scope user-owned data to the authenticated user.

## Authentication Position

For now, the project uses Django's built-in auth for local development, bootstrap administration, and early API testing.

This is acceptable.

Current expectation:

- DRF uses Django session authentication and DRF basic authentication for development/testing convenience.
- `/api-auth/` exists for the DRF browsable API login/logout flow.
- Django `/admin/` remains a service hatch (not the product UI).

Guardrails:

- Do not add, replace, or redesign authentication/authorization systems without explicit instruction.
- Do not implement custom password handling.

Long-term, the project may support external authentication such as OIDC, auth proxy, or trusted auth headers, but this is not required yet.

Django auth may remain as:

- local development auth
- bootstrap admin auth
- fallback self-hosted auth

## Roles (Current Direction)

Global in-app roles are `manager`, `librarian`, and `reader` (stored on `UserProfile.role`). System Owner is represented by Django `is_superuser` and is not a normal app role.

## Error Handling

Prefer clear, stable, user-helpful errors.

For custom API errors (where the view is hand-crafting a Response), prefer the helpers in `core/errors.py` (`api_error_payload`, `api_error_response`) so custom errors consistently use the `{"error": {...}}` envelope.

Future direction:

```json
{
  "error": {
    "code": "BOOK_FILE_DUPLICATE",
    "message": "This EPUB has already been imported.",
    "detail": "A BookFile with the same checksum already exists.",
    "hint": "Open the existing book entry instead of importing it again."
  }
}
```

Do not add a full error-code system unless explicitly requested.

Avoid vague errors like:

```text
Something went wrong.
Invalid request.
Failed.
```

## Testing Rules

Every meaningful change should include or update tests.

At minimum, run:

```bash
python manage.py check
python manage.py test
```

Prefer focused tests for:

* model behavior
* service behavior
* API permissions
* user data isolation
* import behavior
* duplicate handling
* non-destructive reading-session behavior

## Testing strategy

- Prefer focused tests during implementation:
  - `py manage.py test <app>`
  - `py manage.py test <module>`
  - `py manage.py test <TestCase>`
- Use `--keepdb` for repeated local runs when appropriate.
- Run the full suite before finalizing broad changes, shared policy changes, migrations, or before committing.
- Always run `python manage.py check` for meaningful code changes.
- Do not skip tests entirely unless the user explicitly asks.

## Dependency Rules

Do not add dependencies casually.

Before adding a dependency, consider:

* Is it necessary now?
* Is it maintained?
* Is it compatible with Django 6 and Python 3.13?
* Does the standard library or Django already solve this?
* Does it add runtime complexity?

Avoid adding:

* frontend frameworks
* background job systems
* Docker-specific tooling
* AI/LLM dependencies
* PDF libraries
* complex auth systems

unless explicitly requested.

## Current Explicit Non-Goals

Do not add these unless specifically requested:

* React/frontend UI
* reader UI
* mobile app
* sync protocol
* Celery/background jobs
* Docker packaging
* OIDC implementation
* PDF support
* AI features
* plugin system
* complex permissions
* multi-tenant SaaS features

## Admin UI Position

The Django `/admin` site is a technical service hatch for advanced administration, debugging, and recovery.

It is not the primary product UI.

Long-term, the product should have a separate UI (and potentially a separate simplified admin UI) that is not the Django admin.

Do not remove Django admin.

In the future, the project should support disabling Django admin by configuration. For development, Django admin should remain enabled.

Do not build a frontend yet.

## Permissions Design (Future)

Permission model documentation lives in `docs/permissions.md` (roles, groups, and policy direction). Treat it as design guidance and keep it aligned with current behavior when possible.

## Coding Style

* Prefer simple Django conventions.
* Prefer small service functions over large classes.
* Prefer explicit names.
* Avoid premature abstraction.
* Avoid large files doing many unrelated things.
* Keep imports clean.
* Keep migrations intentional.
* Preserve existing tests.
* Preserve existing API paths unless asked to change them.

## Before Finishing Any Task

Run:

```bash
python manage.py check
python manage.py test
```

Then summarize:

* what changed
* which files changed
* whether migrations were created
* verification results
* any follow-up concerns

## Documentation

Prefer updating the focused docs under `docs/`:

- `docs/architecture.md`
- `docs/permissions.md`
- `docs/imports.md`
- `docs/reading.md`
- `docs/metadata.md`
- `docs/api.md`
