# Agent Instructions

Second Pass Library is a pre-release, self-hosted, SQLite-first EPUB library with durable, exportable user-owned reading data. The Django/DRF backend lives under `backend/`; the React/TypeScript Product UI and first-party SDK workspace live under `frontend/`. Do not introduce a new category of product capabilities, protocol families, persistence systems, runtime frameworks, or extension mechanisms unless the current task explicitly requires them.

Repository files, current tests, and observed runtime behavior are authoritative over historical prose or codebase-memory results, except for the immutable policies identified below, which override dependent implementation and secondary documentation. Read the targeted documents below only when relevant to the task.

## Runtime and architecture

- React owns the Product UI. Django-rendered pages are limited to setup, login, logout, optional Admin, errors, and other explicitly retained server pages.
- Docker builds `frontend/`, installs the generated Product UI at `backend/web/product_ui/`, and collects its static assets.
- The first-party SDK owns HTTP transport, wire-shape adaptation, and API-error normalization. Orchestrators own SDK calls and server-aware interpretation. Page regions and presentational components remain server-blind. The React/source boundary checker is authoritative for these boundaries.
- Authorization belongs in backend query/service boundaries and must never rely on React filtering or route guards. Views, serializers, Admin classes, and management commands should translate framework inputs/outputs and delegate multi-step domain work. When behavior coordinates validation, authorization, persistence, or several related model changes as one operation, place that workflow behind one clearly owned service/function rather than distributing it across framework entrypoints.
- This project is pre-release. Do not add compatibility shims, legacy aliases, transitional wrappers, or broad abstractions without a concrete current need; update callers directly.
- Keep REST/JSON APIs under `/api/v1/`. Never expose filesystem paths, storage identities, secrets, or authentication internals.
- Runtime and user data belongs under ignored `userdata/`, never in source control or database file blobs.

## Costly domain invariants

- Three immutable agent policies override secondary documentation and implementation: [Advanced Library Groups](docs/advanced-library-groups.md), [Library Book visibility](docs/book-visibility.md), and [Marginalia-linked Books](docs/marginalia-book-visibility.md). Do not edit these files. If code, tests, or prose disagree, stop and make the dependent boundary conform.
- A Series index is absent or a positive decimal with at most two fractional digits. Storage uses `DecimalField(max_digits=8, decimal_places=2)`; API output is an exact fixed two-decimal string, never a binary float.
- A Book's primary Author is the lowest-positioned `BookAuthor` row, with through-row identity as deterministic fallback. Secondary Authors do not affect primary-Author sorting.
- Author and Series UUIDs are identities. Names and normalized names are non-unique descriptive/search values; renaming must preserve identity and relationships.
- Django Admin is an intentional operator repair surface when enabled, not the Product UI.

## Tests and verification

- Run the smallest relevant modules, classes, or cases first, with generous timeouts for integration-heavy tests. Do not run the full suite automatically unless the scope or focused failures justify it.
- For meaningful backend changes, normally run focused pytest, Django system checks, migration consistency, and Ruff. For frontend/SDK changes, run focused Vitest, TypeScript checks, the production build, and the React/source boundary checker as applicable. Finish with static hygiene and `git diff --check`.
- Tests protect runtime behavior and contracts, not prose wording or deployment-file text unless that text is executable input.
- List every changed test and why in the final report and classify it as `invariant`, `contract`, `regression`, or `implementation detail`. Do not weaken an invariant test without explicitly calling it out.
- Report focused and skipped verification accurately; never imply the full suite ran when it did not.

## File naming and organization

- Organize paths by owning runtime/domain, then workflow/subdomain when needed, then file responsibility. A path should indicate where related behavior belongs before the file is opened.
- Python uses `snake_case`. Keep normal Django names such as `models.py`, `views.py`, `serializers.py`, `services.py`, `queries.py`, `policies.py`, `admin.py`, and `urls.py` when their package has one clear owner. When an app root owns several bounded domains, introduce meaningful packages such as `accounts/users/`, `accounts/passwords/`, or `accounts/client_sessions/`, but do not create a package merely to house one generic filename when a direct capability module is clearer. Avoid production `utils.py`, `helpers.py`, and `misc.py` when a capability-specific name exists.
- React files use PascalCase names matching their primary export. Preserve `Orchestrator` for SDK-aware coordination and `PageRegion` for server-blind page sections. Prefer concrete roles such as `Dialog`, `Panel`, `Toolbar`, `Row`, `Item`, `Card`, `Tile`, `Badge`, `Menu`, `Editor`, `Field`, `Frame`, `List`, `Strip`, `Button`, `Icon`, `Layout`, `Shell`, or `Guard`; use `Component` only when no clearer role exists. Do not introduce a competing dotted-filename convention. Plain TypeScript names should state their behavior (for example query, mutation, draft/state, lifecycle, presentation, navigation, policy, or mapping) without forced suffixes where the name is already clear.
- A subfolder must do real organizational work and expose a clearer ownership or navigation seam: group multiple files with one owner, isolate a meaningful dependency cluster, separate interleaved responsibilities, clarify future placement, reduce an unscannable root, or restore meaning to conventional filenames. Do not create a folder merely to repeat a label already clear from one filename. Single-file folders require a real ownership or boundary reason, not aesthetic consistency.
- Prefer folder topology that approximates a tree: local files primarily collaborate with siblings or broader ancestors, and parent/coordinator layers compose child clusters. Cross-imports into unrelated sibling internals should be uncommon; repeated bidirectional sibling imports signal an artificial boundary or misplaced ownership. This is design evidence, not a ban on legitimate sibling imports, and it does not require barrels.
- The SDK remains transport/wire focused, React-free, and presentation-free. Large SDK domains may use domain folders with narrow type, wire-mapping, and resource-operation responsibilities while preserving the public package API. Do not use Product UI terminology in SDK filenames.
- Tests remain physically separate from production source and mirror meaningful production ownership. Backend paths mirror under `tests/`; the frontend normalization target is `frontend/tests/`. Do not reproduce every production path token when it adds no test ownership or navigation value, and do not colocate `__tests__` in runtime feature directories. Keep test helpers domain-local where practical.
- Line count is a review signal, not a limit: roughly 100 lines is comfortable, 150-220 is normally fine for focused UI, 250+ warrants a cohesion review, and 350-400+ requires an explicit keep/split decision. Apply similar pressure to Python while allowing cohesive atomic transactions, declarative configuration, Django aggregates, management commands, and Admin modules. Do not create micro-files solely to reduce size; a small unclear file may still need rename/move.
- Do not manually normalize generated Product UI output, Django migrations, framework-controlled entrypoints, package-manager files, or generated/static runtime output. Normalize their source or generator instead.

## Logging and maintenance

- Log meaningful lifecycle success, conflict, retry, cleanup failure, and unexpected failure at appropriate levels with bounded context. Never log passwords, tokens, session identifiers, payload contents, or unnecessary personal data. Avoid noisy per-request or per-poll logging.
- Give touched modules and files descriptive purpose/role names. Avoid unrelated broad rename sweeps. Do not introduce a general abstraction merely because similar code might exist later. An abstraction should earn its place by serving multiple current callers/responsibilities, protecting an established boundary, or isolating an external dependency that genuinely needs substitution. Do not add compatibility layers unless a current supported caller or contract requires them.

## Read when relevant

- Deployment, runtime, and security settings: [docs/deployment.md](docs/deployment.md)
- Backups, cleanup, maintenance, and Admin repair: [docs/operations.md](docs/operations.md)
- Development commands and focused checks: [docs/development.md](docs/development.md)
- General roles and mutation authority: [docs/permissions.md](docs/permissions.md)
- Advanced/Simple Mode policy: [docs/advanced-library-groups.md](docs/advanced-library-groups.md) (immutable)
- Current Library Book visibility: [docs/book-visibility.md](docs/book-visibility.md) (immutable)
- Library imports and metadata: [docs/imports.md](docs/imports.md)
- Marginalia lifecycle: [docs/marginalia.md](docs/marginalia.md); visibility and preservation: [docs/marginalia-book-visibility.md](docs/marginalia-book-visibility.md) (immutable); interchange: [specs](docs/specs/)
- Cross-API conventions and external contracts: [docs/api.md](docs/api.md)
- React/SDK work: [docs/frontend.md](docs/frontend.md)
- External Reader pairing and bearer authentication: [docs/client-api-auth.md](docs/client-api-auth.md)
- Broad architecture: [docs/architecture.md](docs/architecture.md)
