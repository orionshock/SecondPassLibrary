# Agent Instructions

Second Pass Library is a pre-release, self-hosted, SQLite-first EPUB library with durable, exportable user-owned reading data. The Django/DRF backend lives under `backend/`; the React/TypeScript Product UI and first-party SDK workspace live under `frontend/`. Do not add PDF, speculative formats, sync protocols, background-job frameworks, OIDC, or plugins unless explicitly requested.

Repository files, current tests, and observed runtime behavior are authoritative over historical prose or codebase-memory results. Read the targeted documents below only when relevant to the task.

## Runtime and architecture

- React owns the Product UI. Django-rendered pages are limited to setup, login, logout, optional Admin, errors, and other explicitly retained server pages.
- Docker builds `frontend/`, installs the generated Product UI at `backend/web/product_ui/`, and collects its static assets.
- The first-party SDK owns HTTP transport, wire-shape adaptation, and API-error normalization. Orchestrators own SDK calls and server-aware interpretation. Page regions and presentational components remain server-blind. The React/source boundary checker is authoritative for these boundaries.
- Authorization belongs in backend query/service boundaries and must never rely on React filtering or route guards. Keep views, serializers, admin classes, and management commands thin; put workflows in cohesive services.
- This project is pre-release. Do not add compatibility shims, legacy aliases, transitional wrappers, or broad abstractions without a concrete current need; update callers directly.
- Keep REST/JSON APIs under `/api/v1/`. Never expose filesystem paths, storage identities, secrets, or authentication internals.
- Runtime and user data belongs under ignored `userdata/`, never in source control or database file blobs.

## Costly domain invariants

- Advanced Library Groups gates only the controls explicitly documented as advanced. It does not invalidate normal Group Shelf or Public-group behavior. Group Shelves, including Public Group shelves, remain valid in both modes. Public Group identity is Owner-managed through Server Settings, not normal Group editing.
- A Series index is absent or a positive decimal with at most two fractional digits. Storage uses `DecimalField(max_digits=8, decimal_places=2)`; API output is an exact fixed two-decimal string, never a binary float.
- A Book's primary Author is the lowest-positioned `BookAuthor` row, with through-row identity as deterministic fallback. Secondary Authors do not affect primary-Author sorting.
- Author and Series UUIDs are identities. Names and normalized names are non-unique descriptive/search values; renaming must preserve identity and relationships.
- User-owned Marginalia survives later loss of Library visibility. Current visibility may gate opening or new writes, but must not silently destroy history, progress, or annotations.
- Django Admin is an intentional operator repair surface when enabled, not the Product UI.

## Tests and verification

- Run the smallest relevant modules, classes, or cases first, with generous timeouts for integration-heavy tests. Do not run the full suite automatically unless the scope or focused failures justify it.
- For meaningful backend changes, normally run focused pytest, Django system checks, migration consistency, and Ruff. For frontend/SDK changes, run focused Vitest, TypeScript checks, the production build, and the React/source boundary checker as applicable. Finish with static hygiene and `git diff --check`.
- Tests protect runtime behavior and contracts, not prose wording or deployment-file text unless that text is executable input.
- List every changed test in the final report and classify it as `invariant`, `contract`, `regression`, or `implementation detail`. Do not weaken an invariant test without explicitly calling it out.
- Report focused and skipped verification accurately; never imply the full suite ran when it did not.

## Logging and maintenance

- Log meaningful lifecycle success, conflict, retry, cleanup failure, and unexpected failure at appropriate levels with bounded context. Never log passwords, tokens, session identifiers, payload contents, or unnecessary personal data. Avoid noisy per-request or per-poll logging.
- Give touched modules and files descriptive purpose/role names. Avoid unrelated broad rename sweeps, speculative general abstractions, and compatibility layers.

## Read when relevant

- Deployment, runtime, and security settings: [docs/deployment.md](docs/deployment.md)
- Backups, cleanup, maintenance, and Admin repair: [docs/operations.md](docs/operations.md)
- Development commands and focused checks: [docs/development.md](docs/development.md)
- Roles, Groups, Books, Shelves, and visibility: [docs/permissions.md](docs/permissions.md)
- Library imports and metadata: [docs/imports.md](docs/imports.md)
- Marginalia: [docs/marginalia.md](docs/marginalia.md) and relevant [specs](docs/specs/)
- React/SDK work: [docs/frontend.md](docs/frontend.md)
- External Reader pairing and bearer authentication: [docs/client-api-auth.md](docs/client-api-auth.md)
- Broad architecture: [docs/architecture.md](docs/architecture.md)
