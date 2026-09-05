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
3. Page Regions and other presentational roles render plain application or
   presentation models and emit user intent through callbacks. They do not know
   endpoints, perform requests, inspect wire fields, or interpret runtime SDK error classes.
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
  concrete presentation roles, behavior/state modules, and styles; use workflow
  folders only when they form a useful ownership/dependency cluster;
- `frontend/src/components/`: reusable server-blind UI primitives;
- `frontend/src/shared/`: cross-feature server-blind behavior and layout;
- `frontend/src/domain/`: application-facing domain presentation helpers;
- `frontend/packages/spl-api/`: the first-party transport and adaptation package;
- `frontend/tests/`: dedicated Product UI test root, mirroring meaningful
  production ownership while remaining physically separate from runtime source;
- `frontend/packages/spl-api/src/__tests__/`: current SDK contract test root;

Feature route controllers use the `*Orchestrator` suffix. Major local page
sections use `*PageRegion`. Other React files use PascalCase names matching
their primary export and prefer concrete roles such as `Dialog`, `Panel`,
`Toolbar`, `Row`, `Item`, `Card`, `Editor`, `Frame`, `Button`, `Icon`, `Layout`,
`Shell`, or `Guard`; use `Component` only when no clearer role exists. Preserve
this project-native vocabulary rather than introducing dotted filenames. A
workflow folder must materially improve ownership, dependency direction,
navigation, or future placement; route variants alone do not justify one.

Tests never live inside runtime feature directories. During normalization,
current tests will move only after Vitest and the test TypeScript project are
prepared for `frontend/tests/`; until then the two current dedicated test roots
remain authoritative.

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
  -> Page Region / concrete presentation role
```

Mutations return through the same boundary. Orchestrators convert successful
domain results and failures into plain loading, pending, validation, success,
empty, or error states. Regions render those states and call supplied actions;
they do not catch `ApiError`, examine HTTP status codes, or translate server
field names. API-provided text is normally rendered through React's escaped
text handling. Book descriptions, Server Description, and Server Banner
Message are the narrow exceptions: they follow the server-owned
[sanitized limited HTML](api.md#sanitized-limited-html) contract. Product UI
renders them through one shared boundary and must not scatter additional
unsafe-HTML sites or add an independently configured React sanitizer. Server
Identity editing uses a restricted Tiptap WYSIWYG surface for the supported
subset; its controls are UX constraints, while the server allowlist remains the
security boundary. The shared editor also offers a raw-HTML source mode; moving
back to rendered mode reapplies the restricted Tiptap schema, and persistence
still passes through the server sanitizer. No Markdown interpretation exists.

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

The SDK exposes explicit global and Group Library read methods for Book browse,
broad search, Authors, Series, and Catalog Tags. Paired methods share query
serialization and response mapping internally while retaining resource-specific
public names; callers do not select scope through a generic SDK abstraction or
deep-import domain internals.

Book, broad-search, Author, and Series result pages expose server-computed
`catalogTags` metadata for the full filtered result population. The Product UI
Catalog Tag rail uses those contextual counts after a result loads and uses the
scope-level Tag list only as loading/fallback identity data. React must not
recount Tags from the current page.

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

A future Marginalia Session delete control is only an intent and confirmation
surface. The Product UI may ask the owner to confirm, send the one
single-Session delete request, display pending/error/success state, and navigate
away after success. It must not delete annotations individually, infer whether
the server-side cascade completed, issue multiple destructive requests for one
Session, implement bulk Session deletion, or reproduce server ownership and
visibility rules. Authorization and the complete destructive lifecycle remain
server-owned.

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

- A Page Region or other presentational file importing SDK runtime operations or error classes.
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
- general roles, Group mutations, and Shelves: [Permissions](permissions.md)
- Advanced/Simple Mode presentation: [Advanced Library Groups
  Mode](advanced-library-groups.md)
- current Book authority: [Library Book Visibility](book-visibility.md)
- Marginalia-linked Book authority and preservation: [Marginalia-Linked
  Books](marginalia-book-visibility.md)
- focused product contracts and archive formats: [Specifications](specs/)
