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
  → call services.py
  → services.py performs domain operation
  → models.py stores state
```

Avoid putting workflows in serializers, viewsets, `Model.save()`, admin classes, or signals (signals are reserved for small framework-adjacent behavior).

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
