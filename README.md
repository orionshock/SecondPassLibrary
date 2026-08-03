# Second Pass Library

Your books, your notes, your reading history.

Second Pass Library is a self-hosted reading library for EPUB collections. It is built for readers who want to keep their books, highlights, bookmarks, notes, reading progress, and reread history under their own control.

It is EPUB-first, private by default, and designed around durable user-owned reading data.

## What It Does

- Store and browse an EPUB library
- Import single EPUB files or simple ZIP archives of EPUBs
- Keep book metadata, authors, series, identifiers, and cover images
- Organize books with shelves
- Manage shared library access with groups and roles
- Track reading sessions, including rereads and closed historical sessions
- Store reading progress per session
- Store bookmarks, highlights, and notes
- View session marginalia in the product UI
- Export marginalia as JSON for one session, selected sessions, one book, or the whole library
- Preview SPL native marginalia imports without writing data
- Provide a REST/JSON API for reader clients

## Product Direction

Second Pass Library is for people who want a personal or small shared EPUB library that is not tied to a vendor cloud.

The project is not trying to be:

- A Kindle clone
- A PDF annotation system
- A Calibre replacement
- A SaaS platform
- An AI reading product

The focus is a dependable home for EPUB files and reading data.

## Current UI

The product UI includes:

- Dashboard with recent reading activity
- Library browsing and book detail pages
- Shelves
- Reading session history
- Session marginalia pages
- Marginalia export center
- User/profile and basic administration pages

The reader client is separate from this repository. This app provides the library, product UI, and API backing it.

## Data Ownership

Runtime and user data live under `userdata/`:

- `userdata/db/` for the SQLite database
- `userdata/media/` for uploaded/stored EPUBs and covers. Only covers are
  raw-public under `/media/covers/`; EPUB/book files are delivered through
  authenticated app/API endpoints.
- `userdata/imports/` for staged imports

`userdata/` is ignored by Git and should be backed up separately.
Collected static files are generated deploy artifacts under `backend/var/static/`.
Docker images generate them during the build; local deployments can regenerate
them with `collectstatic`. They are not part of normal user-data backups.

EPUB files are stored by SHA-256 checksum for deduplication. Human-readable filenames are derived from book metadata when files are downloaded or exported.

The production Docker build compiles the Product UI into
`backend/web/product_ui/` and collects its hashed assets into
`backend/var/static/`, which WhiteNoise serves under `/static/`. WhiteNoise does not
serve `userdata/media/`.
The only public raw media namespace is `/media/covers/`; books, imports,
exports, marginalia, and other protected user data are not exposed as raw media.
Production deployments must provide a non-default `DJANGO_SECRET_KEY`,
`DJANGO_DEBUG=0`, and explicit `DJANGO_ALLOWED_HOSTS`; see
[Production startup](docs/deployment.md).

## Import And Export

Imports currently support:

- `.epub`
- `.zip` archives containing EPUB files
- OPF sidecar metadata for new books when present in ZIP imports

Marginalia export is available for:

- All reading data
- All sessions for one book
- Selected sessions for one book
- One reading session

The canonical Marginalia interchange profile is documented in
[docs/specs/reading-session-annotation-profile/](docs/specs/reading-session-annotation-profile/).
The export-only envelope is documented in
[docs/specs/marginalia-export.md](docs/specs/marginalia-export.md).

Importing Marginalia back into the system supports canonical SPL Marginalia archives. The Product UI previews the file, stages the validated payload with a short-lived import token, and imports selected Sessions as closed Sessions. Foreign annotation formats should be normalized by a Reader client through the Marginalia API or converted externally into the canonical archive format.

## Documentation

Useful docs:

- [Project overview](PROJECT.md)
- [Development setup](docs/development.md)
- [Production startup](docs/deployment.md)
- [Architecture](docs/architecture.md)
- [API index](docs/api.md)
- [Imports](docs/imports.md)
- [Marginalia](docs/marginalia.md)
- [Permissions](docs/permissions.md)
