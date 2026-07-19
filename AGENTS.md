# Agent Instructions

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
- The Product UI uses server-rendered Django templates and JavaScript with session authentication and CSRF. Do not introduce React or another frontend framework unless asked.
- Selected reader-client APIs use bearer tokens. Do not redesign authentication unless asked.
- Django Admin is a technical service hatch, not the Product UI.
- Preserve user ownership and scoping for reading data.
- The Public group identity is Owner-managed through Server Settings only. Normal Group PATCH must reject attempts to change Public identity.

## Files and operations

- Runtime and user data belongs under `userdata/` and must not be committed. Do not store uploaded book files in the database.
- Add operational logging when it materially helps diagnosis or operation. Never log secrets, tokens, passwords, raw uploads, unsafe archive paths, marginalia, request payloads, filesystem paths, hashes, or routine request success.
- Files under `scripts/` are self-contained local/operator conveniences, not production contracts. Do not use script-behavior tests as production guarantees.
- Docker deployment behavior and support files belong under `docker/` and `docs/deployment.md`. Docker runs direct Uvicorn against the ASGI application, and WhiteNoise is mandatory in Docker rather than an operator `.env` option.
- Release version, label, and date belong in checked-in source, not environment files or scripts.

## Scope guardrails

Unless explicitly requested, do not add:

- PDF support
- React or another frontend framework
- a sync protocol
- background jobs
- OIDC
- a plugin system

## Tests and verification

- For meaningful code changes, run `python manage.py check` and focused pytest coverage for the changed area. Use the full suite only when the scope or risk warrants it.
- Classify changed tests as `invariant`, `contract`, `regression`, or `implementation detail` in the final report.
- Do not weaken invariant or contract tests without explicitly explaining why.
- Do not add tests that pin documentation wording, headings, or capitalization.
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
