# Agent Instructions

## EXTREMELY HIGH IMPORTANCE: THIS PROJECT IS PRE-RELEASE

- The project is pre-release. There is no user base to preserve compatibility for.
- Do not add compatibility shims, transitional wrappers, legacy aliases, compatibility migrations, or other compatibility machinery.
- Database migrations are a development convenience. Use them when useful, but expect them to be periodically collapsed; do not treat migration history as a permanent compatibility contract.
- Churn is highly permitted when it produces a real, desirable effect.
- Do not block a good change merely because it creates legitimate downstream cleanup. Make the correct change and update affected callers and boundaries directly.

Read `PROJECT.md` before editing. Use the focused documents under `docs/` for domain and operational detail; this file contains only repository-wide guardrails.

## Code and architecture

- Prefer boring, conventional Django and explicit code.
- Put business workflows in service modules. Do not orchestrate them in serializers, views/viewsets, model `save()` methods, signals, admin classes, or management commands.
- Keep framework glue thin and avoid abstractions that do not solve a current problem.
- Preserve existing API paths and user-owned reading data unless the task explicitly changes them. Reading history, progress, and annotations must not be silently destroyed when access or active sessions change.
- Do not add compatibility shims or re-export wrappers for deleted or renamed modules; update callers to the current boundary.
- Add dependencies only when necessary, maintained, compatible, and not already covered by Python, Django, or an existing dependency.

## Product and security boundaries

- Keep REST/JSON APIs under `/api/v1/`. Never expose filesystem paths, storage identities, secrets, or authentication internals.
- The Product UI is React under `web/react`. Retired Django Product UI source is parked under `reference/legacy_product_ui` and must never be imported, discovered, routed, or tested as runtime code.
- Use Vite, React Router, and Vitest for the React app. Frontend dependencies are acceptable when they solve established infrastructure problems; do not add GraphQL or a generated API client unless explicitly requested.
- React routes and components must use the first-party TypeScript API package rather than ad hoc `fetch()` calls or raw API URLs. The package owns server-shape normalization and returns stable app-facing objects. React hooks may wrap it, but the package itself remains framework-light plain TypeScript.
- Keep React layered: the app orchestrator owns bootstrap and the global frame; branch orchestrators own page assembly; regions own only their local operations; shared components stay server-blind. Communicate through explicit props, callbacks, outlet context, or stable contracts. Only `@second-pass/spl-api` may know server URLs or perform server communication.
- Vite is the primary Product UI development surface and proxies same-origin-style requests to Django. Production and Docker React integration are deferred.
- React owns `/` and intended Product UI deep links after setup and login. Only first-time setup, `/login/`, `/logout/`, and Django Admin remain Django-rendered application surfaces. Do not add separate Product UI mounts, DRF browsable pages, or Django-rendered Reader Client authorization pages.
- Selected reader-client APIs use bearer tokens. Do not redesign authentication unless asked.
- Django Admin is a technical service hatch, not the Product UI.
- Preserve user ownership and scoping for reading data.
- The Public group identity is Owner-managed through Server Settings only. Normal Group PATCH must reject attempts to change Public identity.

## Files and operations

- Runtime and user data belongs under `userdata/` and must not be committed. Do not store uploaded book files in the database.
- Add operational logging when it materially helps diagnosis or operation. Never log secrets, tokens, passwords, raw uploads, unsafe archive paths, marginalia, request payloads, filesystem paths, hashes, or routine request success.
- Files under `scripts/` are self-contained local/operator conveniences, not production contracts. Do not use script-behavior tests as production guarantees.
- Docker deployment behavior and support files belong under `docker/` and `docs/deployment.md`. Docker runs direct Uvicorn against the ASGI application, and WhiteNoise is mandatory in Docker rather than an operator `.env` option.
- Do not restore retired Product UI routes or preserve their layout/static tests. Keep tests only for retained Django surfaces and backend/API invariants; add React tests with new React behavior.
- Release version, label, and date belong in checked-in source, not environment files or scripts.

## Scope guardrails

Unless explicitly requested, do not add:

- PDF support
- a sync protocol
- background jobs
- OIDC
- a plugin system

## Tests and verification

- For meaningful code changes, run `python manage.py check` and focused pytest coverage for the changed area. Use the full suite only when the scope or risk warrants it.
- Classify changed tests as `invariant`, `contract`, `regression`, or `implementation detail` in the final report.
- Do not weaken invariant or contract tests without explicitly explaining why.
- Do not add tests that pin documentation wording, headings, or capitalization.
- Keep every React/Vitest test under `web/react/src/__tests__`; do not colocate Vitest files with runtime components or SDK source.
- Do not treat local helper scripts as production contracts.
- Docs-only changes do not require application tests.
- Do not claim the full suite passed unless it was actually run; report focused and skipped verification accurately.
- Playwright is optional and should be limited to focused rendered-UI or interaction diagnosis. Keep artifacts under ignored `test-artifacts/`.

## Use focused docs for details

- `docs/architecture.md`
- `docs/api.md`
- `docs/permissions.md`
- `docs/development.md`
- `docs/deployment.md`
- `docs/ui.md`
