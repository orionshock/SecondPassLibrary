# React Product UI

The Product UI lives in `web/react`. Retired Django Product UI templates, static assets, views, and routes are isolated under `reference/legacy_product_ui` for reference only. They are outside the Django application and must not be imported, discovered, or mounted. Old Product UI tests are not maintained as executable tests.

## Development

Run Django on port 8000 and the Product UI Vite server on port 5174. Port 5173 remains available for the standalone Reading Client. From `web/react`, run `npm install` and `npm run dev`. Vite proxies `/api`, `/media`, `/admin`, `/login`, `/logout`, and `/setup` to Django, so the app uses Django session authentication through same-origin-style URLs.

Vite is the primary development surface. Django serves the authenticated React shell at `/` and intended Product UI deep links when a local build exists. Before bootstrap, these routes redirect to `/setup/`; afterward unauthenticated requests redirect to `/login/`.

There are no `/app/` or `/legacy/` mounts. Retired paths are not redirected or otherwise special-cased.

The React shell bootstraps the authenticated user through `getCurrentUser()` and server identity through `getServerInfo()` from `@second-pass/spl-api`. Server identity comes from `/.well-known/secondpass`. Components do not make raw `fetch()` calls. The shell provides loading, login-required, retryable error, server identity/banner, user identity, and logout states. `/logout/` remains a Django endpoint.

Dashboard (`/`) is a styled placeholder. My Marginalia, Library, Groups, Shelves, and Import remain placeholder routes. Users (`/users`) is the first server-driven React list: its search, role/status filters, ordering, page, and page size live in the URL, while the API owns filtering, sorting, and pagination. User creation is available at `/users/new`; managed-user editing is `/users/:profileId/edit`, with no separate User Detail route. Profile (`/profile`) owns self-profile editing, membership display, session actions, and connected clients. Password changes use `/profile/password`; pairing approval uses `/profile/client-pairing`. The pairing page accepts `?code=...`, immediately looks up a supplied code, and otherwise presents code entry before approval. Server Settings is available to the Owner at `/server`, with General, Public Library, and Library Groups selected through `?tab=`. Unknown paths within Django's explicit React route policy render an in-shell not-found page.

## Deferred production integration

The current local build and root-shell integration may be used for smoke checks. Docker and production React build integration are explicitly deferred.

First-time setup, `/login/`, `/logout/`, and the Django `/admin/` service hatch are the only retained Django-rendered application surfaces. DRF browsable pages and `/api-auth/` are disabled. The old Reader Client authorization webpage is retired. React pairing approval uses authenticated JSON endpoints under `/api/v1/client-api/`; token delivery remains confined to external-client polling. Dashboard, library/catalog, books, groups, shelves, users, imports, and Product UI server settings are React scope.

## Server boundary

`web/react/packages/spl-api` is the first-party, framework-light TypeScript server communication package. It owns `fetch`, credentials, JSON parsing, structured error normalization, pagination types, server response mapping, and domain calls. React routes, components, and hooks consume its stable app-facing objects; they do not scatter raw `fetch()` calls or API URLs.

The Product UI uses the existing REST/JSON endpoints under `/api/v1/`. Do not add GraphQL or a generated API client.

## Application layers and naming

- `App` owns bootstrap plus global loading, login-required, and retryable error states.
- `AppFrame` owns the server/user header, top navigation, contextual breadcrumb slot, footer, and route outlet.
- Feature route controllers end in `Orchestrator`. They own SDK calls, branch workflow state, route/outlet context, and assembly of their page regions.
- Files that contain a major local page section end in `PageRegion`. PageRegions receive data and actions through props and contain only their section's form or display sprawl.
- Presentational building blocks end in `Component`; use `SubComponent` only for a clearly subordinate piece. Features may have many focused files—the naming is meant to make that safe, not force a one-file feature.
- Promote behavior to `src/shared` when it plausibly serves multiple branches such as Profile, Users, Imports, Server Settings, or Book Edit. Keep domain-specific drafts, messages, and rules inside their feature.
- Shared components and behaviors are server-blind. Data and operations cross layers through typed props, callbacks, outlet context, or stable structural error contracts.
- `@second-pass/spl-api` is the only server communication layer. It owns URLs, fetch, same-origin credentials, CSRF, parsing, error normalization, and response mapping.

React CSS follows the same ownership boundaries: `styles/base.css` contains only global tokens/reset/typography, AppFrame owns shell CSS, shared UI and icons own their component CSS, and feature branches import their own layout CSS. All Vitest files live centrally under `src/__tests__` and are named by subject.

The SDK public index exports domain operations, app-facing types, and errors—not its low-level request client. `npm test` runs a lightweight source check that rejects raw server communication in app source, SDK imports in shared UI primitives, and React imports in the SDK. Vite proxy declarations are development transport configuration, not an application communication layer.

Within the SDK, `accounts.ts` owns current-user/profile/password mapping while `accountSessions.ts` owns web-session and connected-client operations and metadata mapping.

Profile at `/profile` is the first real React feature page. It displays current identity and group/curator status, edits supported self-profile fields, logs out other web sessions, and lists/revokes connected clients. The App orchestrator forces `must_change_password` users through the dedicated password route until refreshed current-user state clears the requirement. All operations use `@second-pass/spl-api`. Dashboard at `/` is a styled shell placeholder only; it has no metrics or dashboard-specific API calls yet.

Users list behavior is owned by `UsersListOrchestrator`; its PageRegions render filters and paginated results, while row Components remain presentational. The shared pager consumes stable page metadata and callbacks without knowing server URLs. `@second-pass/spl-api/users.ts` adapts managed-user wire payloads and query names to app-facing objects.

`UserCreateOrchestrator` owns the create workflow and one-time temporary-password result. The React form never exposes or sends account activity; new managed users use the backend's active-by-default contract and must change the generated password on first login. Create forms use the shared label-left fields and right-oriented action/feedback row.

`UserEditOrchestrator` owns managed-user detail updates, password controls, and advanced-group membership operations. It adapts the existing group-scoped membership API through the SDK. Password reset results reuse the shared read-only temporary-password display and remain only in component state. Public membership is non-destructive and non-curatable in this UI; simple mode omits custom membership controls.

`ServerSettingsOrchestrator` owns the Owner-only `/server` branch. Tabs are URL-backed (`general`, `public-library`, and `library-groups`), while editing remains inline and does not create child routes. General and Public Library forms use the shared label/control and action-feedback conventions. Advanced groups can be enabled only from Library Groups edit mode after explicit confirmation; ordinary React UI does not offer disable/collapse. Django Admin remains an external recovery boundary and is not linked unless a reliable capability is exposed.

The parked UI under `reference/legacy_product_ui` may inform palette, spacing, and interaction tone only. It is not an implementation dependency or active contract.

Cross-page product semantics that are not API shapes are tracked in [React Product UI Rules](react-ui-rules.md).

## Contextual breadcrumbs

Breadcrumbs prefer explicit navigation context carried in React Router location state. A link to a child workflow builds a structured text/internal-URL trail; it never carries HTML. Context is marked for the current app runtime so a refresh cannot replay stale history state. On direct entry, refresh, external navigation, or malformed state, the destination Orchestrator supplies its canonical fallback. Breadcrumbs do not inspect browser history and are not defined solely as static route metadata.

`AppFrame` owns the consistent breadcrumb position and visual separators. Orchestrators register the resolved trail for their pathname; base branch routes such as `/profile` and `/users` do not render breadcrumbs, and top-level navigation starts a new branch without carrying stale context. Child workflows retain their canonical hierarchy. The forced password-change workflow suppresses breadcrumbs so it does not offer navigation away from the required action.

## Shell and UI conventions

`AppFrame` owns the compact server/navigation/account header and the low-emphasis product/version footer. Branch Orchestrators own mutations; PageRegions own controlled local form presentation where appropriate. Shared action rows, feedback, normalized mutation errors, and field-error extraction live above individual features. Cancel never calls the server.

Use the shared `MaterialIcon` component for Material Symbols instead of ad hoc icon spans. It centralizes the outlined-font class, token rendering, sizing, and decorative versus labeled accessibility behavior.
Use `RemoveIconButton` for compact remove/delete/revoke controls so those operations share the established `remove_circle` danger treatment. Branches remain responsible for confirmation and mutation behavior.

All Vitest files live together under `web/react/src/__tests__`; do not create colocated `*.test.*` files or component-specific test directories. `vite.config.ts` limits discovery to that directory. The workspace recommends the Vitest Explorer extension so the suite is available in VS Code's Testing panel; `npm run test:vitest` provides its watch-mode command.
