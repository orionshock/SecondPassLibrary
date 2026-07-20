# Second Pass Library

Second Pass Library is a self-hosted, EPUB-focused system for keeping a reading library and durable, user-owned reading data.

It provides:

- EPUB library management
- Reading progress, sessions, highlights, notes, and bookmarks
- Exportable reading data
- A stable REST/JSON API for reader clients

It is not:

- A vendor-cloud Kindle clone
- A PDF annotation system
- An AI product
- A SaaS-first document platform

Principles:

- Self-hosted and EPUB first
- SQLite first, with conventional Django
- Explicit, maintainable code over clever abstractions
- Durable, exportable user data
- Predictable, versioned APIs

The current implementation is EPUB-only. Do not add PDF or speculative format support unless explicitly requested.

The Product UI is being rebuilt in React under `web/react` and owns `/`. Retired Django UI code is parked under `web/legacy`; only bootstrap setup, login/logout, and admin/auth internals remain Django-rendered.
