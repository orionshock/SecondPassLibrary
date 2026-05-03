# Second Pass Library

Second Pass Library is a self-hosted EPUB-focused reading system.

It is intended to provide:
- Library management for EPUB files
- User-owned reading metadata
- Reading progress sync
- Highlights and annotations
- Reading history / reread support
- Exportable user data
- A stable REST/JSON API for reader clients

The project is not intended to be:
- A Kindle clone dependent on Amazon or cloud services
- An AI-powered reading product
- A PDF annotation system
- A SaaS-first multi-tenant platform

Core principles:
- Self-hosted first
- EPUB first
- SQLite-first, PostgreSQL-compatible later
- External authentication eventually, not custom password logic
- User reading state must be durable and exportable
- The API should be boring, documented, and versioned