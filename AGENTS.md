# AGENTS.md

AI coding agents (Copilot) working on Second Pass Library should follow these principles and conventions.

**Workflow**: You are prompted via natural language to execute implementation tasks. Use this document to understand project context, architecture decisions, and conventions before executing user requests.

## Project Overview

Second Pass Library is a self-hosted EPUB-focused reading system providing library management, user-owned metadata, annotations, reading history, and a stable REST/JSON API for reader clients.

See [PROJECT.md](PROJECT.md) for detailed project goals and non-goals.

## Core Principles

1. **Self-hosted first** — All features must be deployable on a single user's server
2. **EPUB first** — Primary format support; other formats are secondary
3. **SQLite-first** — Initial database; must be PostgreSQL-compatible for future scaling
4. **External authentication** — Use external auth providers; no custom password handling
5. **Data portability** — All user reading state must be durable and exportable
6. **Boring APIs** — REST/JSON API should be stable, documented, and versioned (no cutting-edge patterns)

## Execution Guidelines for Prompts

When executing a prompt, follow this order:

1. **Clarify intent** — Make sure you understand what's being built and why
2. **Check constraints** — Ensure the approach aligns with core principles above
3. **Reference patterns** — Use Django & DRF Patterns section for code structure
4. **Validate exports** — All user data must be portable and standardized
5. **Test on both DBs** — If modifying data layer, verify SQLite and PostgreSQL compatibility
6. **Ask before deviating** — If a constraint seems wrong, surface it rather than assuming

## Tech Stack

- **Language**: Python 3.x
- **Web Framework**: Django with Django REST Framework
- **Database**: SQLite (initially), PostgreSQL-compatible
- **File Storage**: Local filesystem (user-owned EPUB library)
- **Deployment**: Self-hosted (Docker considered later, not MVP priority)
- **API**: REST/JSON with versioned endpoints
- **Format**: EPUB 3.x standard

## Architecture Guidelines

### API Design

- Versioned endpoints (e.g., `/api/v1/...`)
- Standard REST conventions (GET, POST, PUT, DELETE)
- JSON request/response bodies
- Consistent error responses

### Data Durability

- User reading state (progress, highlights, annotations) must survive app updates
- Schema migrations must be reversible where possible
- Exports should be in standard formats (JSON, EPUB with annotations)

### Authentication

- Delegate to external auth providers (OAuth2, SAML, etc.)
- Do not implement custom password logic
- User sessions should be stateless where possible

### EPUB Handling

- Parse EPUB 3.x standard format
- Extract metadata, chapters, and reading order
- Support embedded fonts and media
- Handle corrupted EPUBs gracefully

## Django & DRF Patterns

### Models

- Store user reading state in models (progress, bookmarks, highlights, annotations)
- Denormalize reading position (chapter, percentage) for efficient querying
- Include audit fields (`created_at`, `updated_at`) on all models
- Use `ForeignKey(User, on_delete=models.CASCADE)` for user-owned data with proper `related_name`

### API

- Use Django REST Framework serializers for request/response validation
- Include pagination on collection endpoints
- Add filtering by `user` to all queries (enforce user data isolation)
- Version API endpoints explicitly (e.g., `/api/v1/library/books/`)

### File Storage

- Store EPUBs on local filesystem with user-owned directory structure
- Generate deterministic paths to support portable exports
- Implement graceful handling of missing files

## Development Conventions

### Project Structure

(To be established as the project grows)

- Django app structure (models, views, serializers, tests per feature)
- Code style and linting rules
- Testing strategy
- Git workflow

### Database

- Use Django ORM models; avoid raw SQL unless necessary
- Ensure all queries work on both SQLite and PostgreSQL
- Test migrations on both databases before merging
- Include reversible migrations where feasible
- Store only standardized, portable data formats (no pickles, no proprietary formats)

## Key Resources

- **PROJECT.md** — Project goals, non-goals, and core principles
- **README.md** — Quick start guide
- Build and test commands (to be documented)

## Common Pitfalls to Avoid

- Tight coupling to SQLite-specific features (must work on PostgreSQL)
- Storing user data in formats that cannot be exported
- Custom authentication logic (use external auth)
- Non-standard REST patterns
- EPUB handling that breaks on edge cases
