# Frontend

## Scope

React and TypeScript own the active Second Pass Library Product UI. The npm
workspace lives under `frontend/`; there is no repository-root JavaScript
workspace. Django continues to render only setup, login, logout, optional
Admin, error pages, and other explicitly retained server surfaces. Product UI
routes and deep links render the React application.

Vite builds the workspace into `backend/web/product_ui/`. Docker builds the
same frontend workspace independently, installs that artifact into the prepared
backend tree, and makes its hashed assets available to `collectstatic`.
Everything under the generated Product UI directory is build output: never edit
it by hand or treat it as the source of frontend behavior.

This document owns frontend architecture and contributor rules. The router,
SDK types, and tests own current routes and features; this is deliberately not
a screen inventory.

## Layering and authority

The Product UI has three practical layers:

1. `@second-pass/spl-api` owns communication with Django. It provides the HTTP
   client, same-origin credentials, CSRF handling for unsafe methods, attachment
   handling, JSON/media-type validation, wire-to-application mapping, and
   bounded API error normalization. Snake-case wire fields stop here; exported
   application models and errors use stable frontend naming.
2. App and feature Orchestrators own SDK calls, route/query state, workflow
   state, server-aware error interpretation, and assembly of page sections.
   Runtime SDK operations and SDK error classes belong at this boundary.
3. Page Regions and Components render plain application or presentation models
   and emit user intent through callbacks. They do not know endpoints, perform
   requests, inspect wire fields, or interpret runtime SDK error classes.
   Type-only imports of stable application-facing SDK models are acceptable;
   runtime SDK imports are not.

Shared UI primitives under `src/components` and cross-feature code under
`src/shared` are server-blind and do not import the SDK. Production feature
branches do not import one another; promote genuinely reusable behavior to an
appropriate app, shared, component, or domain module. The SDK itself remains
framework-light and must not depend on React.

These boundaries keep transport churn out of rendering code and make UI states
testable without a server client. They are also security boundaries of
responsibility, not security enforcement: React route guards and capability
hints improve navigation, but object authorization and visibility always
belong to backend queries and services. Components must not recreate server
policy by filtering objects or inferring privileges.

## Frontend workspace ownership

The durable source layout is:

- `frontend/src/app/`: bootstrap, global frame, router, route modules, and
  application-wide navigation/error boundaries;
- `frontend/src/features/`: feature Orchestrators plus their local Page Regions,
  Components, presentation helpers, query state, and styles;
- `frontend/src/components/`: reusable server-blind UI primitives;
- `frontend/src/shared/`: cross-feature server-blind behavior and layout;
- `frontend/src/domain/`: application-facing domain presentation helpers;
- `frontend/packages/spl-api/`: the first-party transport and adaptation package;
- `frontend/src/__tests__/`: Product UI tests;
- `frontend/packages/spl-api/src/__tests__/`: SDK contract tests.

Feature route controllers use the `*Orchestrator` suffix. Major local page
sections use `*PageRegion`; reusable presentational pieces use `*Component`
(`*SubComponent` only for a clearly subordinate piece). Prefer descriptive
responsibility names over extra directory depth. A feature may contain several
focused files without creating a folder for every route or operation.

Keep feature-specific drafts, messages, and policy presentation with their
feature. Promote code only when it has a real cross-feature owner. Frontend
source, not emitted JavaScript/CSS or the backend artifact, is authoritative.

## Data and error flow

A normal page flow is:

```text
route / user intent
  -> Orchestrator
  -> @second-pass/spl-api
  -> Django API
  -> SDK validation and wire adaptation
  -> Orchestrator presentation state
  -> Page Region / Component
```

Mutations return through the same boundary. Orchestrators convert successful
domain results and failures into plain loading, pending, validation, success,
empty, or error states. Regions render those states and call supplied actions;
they do not catch `ApiError`, examine HTTP status codes, or translate server
field names. API-provided text is rendered through React's normal escaped text
handling and is never injected as raw HTML.

Downloads and other attachments use the shared SDK attachment client. The SDK
owns credentials, safe filenames, content types, JSON error detection, and
generic handling for non-JSON proxy failures. A domain operation may provide a
specific error mapper, but React presentation code receives only the resulting
application state. Do not add status-only parsing or duplicate download clients
inside features.

When a structured API contract changes, update the whole path in one change:

- backend response and error contract;
- SDK wire type, validation/adaptation, and application-facing type;
- Orchestrator interpretation;
- user-visible presentation state;
- focused backend, SDK, and Product UI coverage as applicable.

Server-driven lists keep filtering, ordering, counts, and pagination on the
server. Orchestrators own navigation-restorable URL state; row and region code
renders the returned page rather than re-sorting or re-filtering it. Client
validation may improve feedback but must not replace server validation.

## Routing and shell behavior

React Router owns Product UI navigation. Django's retained shell routes serve
the same built `index.html` for supported Product UI deep links, so refresh and
direct navigation resolve through the same application. Route definitions and
role guards live in the app router; do not duplicate a route catalog in prose
or individual components.

In development, Vite proxies Django-owned paths so the same SDK requests use
session authentication through same-origin-style URLs. Proxy declarations are
development transport configuration, not an alternate communication layer or
authorization boundary.

Feature route modules use lazy loading where it materially separates branches.
The global frame supplies a route-level loading fallback and error boundary;
feature Orchestrators own retryable data errors within an otherwise loaded
route. Unknown Product UI paths render an in-shell not-found state.

Authentication-sensitive navigation preserves server contracts. Session login
and setup remain Django surfaces. Logout is a CSRF-protected POST performed
through the SDK, never a mutating link or GET. A user required to change their
password is routed to the password workflow, while backend middleware remains
the authoritative restriction. Reader-client bearer behavior is a separate
contract and must not be inferred from Product UI session behavior.

## Accessibility and interaction

Use semantic buttons for actions and links for navigation. Essential behavior
must be keyboard-operable and expose a visible focus state; a click handler on
a visually interactive non-control is not an acceptable substitute. Hover may
supplement interaction feedback but cannot be its only signal.

Loading, pending, retryable error, empty, unavailable, success, and disabled
states must be explicit where they affect the workflow. Pending actions prevent
unsafe duplicate submission without erasing useful context. Destructive actions
must be visually distinguishable and receive confirmation where the current
product policy requires it. Shared controls remain server-blind and require
caller-supplied accessible labels and operation callbacks.

Prefer native form and control semantics. Labels, validation messages, live
status, and disabled state must remain available to assistive technology. Do
not encode essential meaning only through color, iconography, hover, or layout.

## Testing and verification

Run the smallest affected Vitest file or group first, then the TypeScript check,
production build, and React/source boundary checker as appropriate. Exact
commands and the broader contributor workflow are in
[Development](development.md#run-checks-and-tests). Run static hygiene when
frontend documentation or other checked text changes. Test classification and
reporting rules remain in [AGENTS.md](../AGENTS.md#tests-and-verification).

Boundary-check failures are architecture failures, not optional lint. The
checker rejects raw app communication, raw API paths and CSRF details,
snake-case field-error handling outside the SDK, runtime SDK imports in
presentational files, SDK imports in shared code, feature-to-feature production
imports, query construction in presentational files, and React dependencies in
the SDK. Its own rule tests protect the checker. Do not weaken it merely to make
a new dependency direction pass.

Product UI tests should assert user-visible state and interaction. SDK tests
should assert transport, adaptation, and error contracts. Outside the explicit
source-boundary checks, avoid tests coupled only to file placement, current
component composition, prose, styling trivia, or private SDK implementation.

## Common prohibited drift

- A Page Region or Component importing SDK runtime operations or error classes.
- A component issuing `fetch`, constructing raw API URLs, or handling CSRF.
- React reimplementing authorization, visibility, or sparse wire semantics.
- Snake-case response or field-error names escaping the SDK.
- A feature importing production code from another feature to avoid a proper
  shared owner.
- Hand-editing `backend/web/product_ui/` or treating it as source.
- Adding compatibility shims for superseded frontend contracts without a
  concrete current need.
- Copying router, serializer, SDK export, package, or screen inventories into
  documentation.

## Task-specific references

Read these only when the task touches their subject:

- broad system boundaries: [Architecture](architecture.md)
- setup and exact commands: [Development](development.md)
- shared HTTP conventions and external contracts: [API](api.md)
- external Reader pairing and bearer authentication:
  [Client API authentication](client-api-auth.md)
- Marginalia behavior: [Marginalia](marginalia.md)
- roles, Groups, Books, Shelves, and visibility: [Permissions](permissions.md)
- focused product contracts and archive formats: [Specifications](specs/)
