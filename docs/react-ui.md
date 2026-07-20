# React Product UI

The Product UI lives in `web/react`. Retired Django Product UI templates, static assets, views, and routes are isolated under `reference/legacy_product_ui` for reference only. They are outside the Django application and must not be imported, discovered, or mounted. Old Product UI tests are not maintained as executable tests.

## Development

Run Django on port 8000 and the Product UI Vite server on port 5174. Port 5173 remains available for the standalone Reading Client. From `web/react`, run `npm install` and `npm run dev`. Vite proxies `/api`, `/media`, `/admin`, `/login`, `/logout`, and `/setup` to Django, so the app uses Django session authentication through same-origin-style URLs.

Vite is the primary development surface. Django serves the authenticated React shell at `/` and intended Product UI deep links when a local build exists. Before bootstrap, these routes redirect to `/setup/`; afterward unauthenticated requests redirect to `/login/`.

There are no `/app/` or `/legacy/` mounts. Retired paths are not redirected or otherwise special-cased.

The React shell bootstraps the authenticated user through `getCurrentUser()` and server identity through `getServerInfo()` from `@second-pass/spl-api`. Server identity comes from `/.well-known/secondpass`. Components do not make raw `fetch()` calls. The shell provides loading, login-required, retryable error, server identity/banner, user identity, and logout states. `/logout/` remains a Django endpoint.

Dashboard (`/`) is a styled placeholder. My Marginalia, Library, Groups, Shelves, Users, Import, and Server Settings (`/server`) remain placeholder routes. Profile (`/profile`) owns profile editing, membership display, session actions, and connected clients. Password changes use `/profile/password`; pairing approval uses `/profile/client-pairing`. The pairing page accepts `?code=...`, immediately looks up a supplied code, and otherwise presents code entry before approval. Unknown paths within Django's explicit React route policy render an in-shell not-found page.

## Deferred production integration

The current local build and root-shell integration may be used for smoke checks. Docker and production React build integration are explicitly deferred.

First-time setup, `/login/`, `/logout/`, and the Django `/admin/` service hatch are the only retained Django-rendered application surfaces. DRF browsable pages and `/api-auth/` are disabled. The old Reader Client authorization webpage is retired. React pairing approval uses authenticated JSON endpoints under `/api/v1/client-api/`; token delivery remains confined to external-client polling. Dashboard, library/catalog, books, groups, shelves, users, imports, and Product UI server settings are React scope.

## Server boundary

`web/react/packages/spl-api` is the first-party, framework-light TypeScript server communication package. It owns `fetch`, credentials, JSON parsing, structured error normalization, pagination types, server response mapping, and domain calls. React routes, components, and hooks consume its stable app-facing objects; they do not scatter raw `fetch()` calls or API URLs.

The Product UI uses the existing REST/JSON endpoints under `/api/v1/`. Do not add GraphQL or a generated API client.

## Application layers

- `App` owns bootstrap plus global loading, login-required, and retryable error states.
- `AppFrame` owns the server/user header, top navigation, footer, and route outlet.
- Branch orchestrators such as Dashboard and Profile assemble their own regions. Regions do not reach into sibling branches.
- Shared components are dumb, server-blind primitives. Data and operations cross layers through typed props, callbacks, or outlet context.
- `@second-pass/spl-api` is the only server communication layer. It owns URLs, fetch, same-origin credentials, CSRF, parsing, error normalization, and response mapping.

The SDK public index exports domain operations, app-facing types, and errors—not its low-level request client. `npm test` runs a lightweight source check that rejects raw server communication in app source, SDK imports in shared UI primitives, and React imports in the SDK. Vite proxy declarations are development transport configuration, not an application communication layer.

Profile at `/profile` is the first real React feature page. It displays current identity and group/curator status, edits supported self-profile fields, logs out other web sessions, and lists/revokes connected clients. The App orchestrator forces `must_change_password` users through the dedicated password route until refreshed current-user state clears the requirement. All operations use `@second-pass/spl-api`. Dashboard at `/` is a styled shell placeholder only; it has no metrics or dashboard-specific API calls yet.

The parked UI under `reference/legacy_product_ui` may inform palette, spacing, and interaction tone only. It is not an implementation dependency or active contract.

Cross-page product semantics that are not API shapes are tracked in [React Product UI Rules](react-ui-rules.md).

## Shell and UI conventions

`AppFrame` owns the compact server/navigation/account header and the low-emphasis product/version footer. Profile owns its controlled form drafts, cancellation, mutation feedback, and field errors; Cancel never calls the server.

Use the shared `MaterialIcon` component for Material Symbols instead of ad hoc icon spans. It centralizes the outlined-font class, token rendering, sizing, and decorative versus labeled accessibility behavior.
Use `RemoveIconButton` for compact remove/delete/revoke controls so those operations share the established `remove_circle` danger treatment. Branches remain responsible for confirmation and mutation behavior.
