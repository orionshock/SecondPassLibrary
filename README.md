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

React provides the active Product UI. A separate Reader client can use the
bounded external API; it is not part of this repository. Runtime data remains
under operator-controlled `userdata/`, and portable Marginalia archives keep
reading history independent of a vendor cloud.

## Documentation

- [Project narrative](docs/Narrative%20of%20Second%20Pass%20Library.md) (optional, non-normative overview)
- [Development setup](docs/development.md)
- [Production startup](docs/deployment.md)
- [Operations and maintenance](docs/operations.md)

## License and project identity

Code is licensed under [Apache-2.0](LICENSE). Project names and branding are
governed separately by [TRADEMARKS.md](TRADEMARKS.md).
