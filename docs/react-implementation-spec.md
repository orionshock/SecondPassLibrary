# React Product UI migration reference

> **Document purpose:** This document records useful behavior from the parked
> Django Product UI and explains deliberate migration differences. It is not an
> implementation-status log. Current React behavior belongs in
> [`react-ui.md`](react-ui.md); durable cross-page rules belong in
> [`react-ui-rules.md`](react-ui-rules.md).

## Purpose and precedence

The retired Product UI under `reference/legacy_product_ui/` is reference
material only. It may explain an established workflow, product term, or visual
choice, but it is not runtime code and does not dictate React component or DOM
structure.

When sources disagree, use this order:

1. current security, permission, privacy, and API contracts;
2. current React rules and implemented Product UI behavior;
3. the migration guidance in this document;
4. parked UI behavior and visual semantics;
5. parked implementation details.

Do not use this document to decide whether a React feature is currently
implemented. Inspect `react-ui.md` and the current route/feature code instead.

## Useful legacy behavior

### Overall product character

The parked UI established a compact, dark, server-oriented application:
restrained headings, bounded content, muted metadata, small status treatments,
and actions near the section they affect. React should preserve useful workflow
and semantic detail without copying DOM quirks, inline styles, ad hoc HTML,
duplicated controls, or client-side permission guesses.

Historical behaviors worth retaining when a surface is rebuilt or revised:

- user and server content is plain text, never trusted HTML;
- server-side filtering, ordering, pagination, visibility, and authority remain
  authoritative;
- unavailable Books may leave durable user-owned reading history or locked
  Shelf placeholders without leaking hidden Book metadata;
- destructive actions explain their consequences and require deliberate
  confirmation;
- empty, unavailable, forbidden, and failure states stay bounded to the page or
  section that owns the operation;
- Public/Common Room is a real fallback Group, not a synthetic frontend label.

Exact cross-page presentation and interaction rules are intentionally maintained
in `react-ui-rules.md`, not duplicated here.

### Dashboard

The legacy Dashboard was an authenticated landing page rather than global shell
content. Its useful concepts were:

- the configured server banner belongs on Dashboard only;
- recent reading is the primary content;
- My Marginalia, Shelves, and Library remain obvious entry points;
- a failure to load recent activity must not make the rest of Dashboard unusable;
- unavailable Books do not receive open/continue actions.

The React Dashboard uses the canonical Marginalia recent-Session API and SDK
rather than reproducing the parked page's general-list query or static
JavaScript. Do not restore `/dashboard/`; `/` is the Product UI landing route.

### My Marginalia

The parked reading UI remains useful historical guidance for understanding
owner-scoped reading history, not general Library browsing. The React Product
UI implements this area under `/marginalia`; the canonical backend API is
`/api/v1/marginalia/`.

#### Session and Book browse

- Browse owned reading history by Session and, where useful, grouped Book.
- Preserve status filtering, search, pagination, and a Session/Book presentation
  choice in URL state.
- Show Session identity, active/closed state, dates, annotation
  count, and a visible Book summary when permitted.
- Keep owned history readable when its Book is no longer visible. Use bounded
  `Book unavailable` context and omit open/continue actions.
- If a client groups a server-paginated Session page by Book, describe counts as
  Books represented on that Session page; do not imply Book pagination.

#### Book sessions and Session detail

- A Book-sessions view should use the server-provided Book context even when no
  Sessions are returned.
- Session detail remains owner-scoped and may show progress, highlights,
  bookmarks, and notes after Book access changes.
- Raw selectors and locator internals are not primary Product UI prose.
- Book-open capability is separate from the right to inspect durable owned
  reading history.

#### Import and export

- Complete export includes owned reading data even when related Books are no
  longer visible.
- Selective export is organized around owned Sessions and safe Book context; it
  does not expose raw database identifiers as product labels.
- Import remains a preview-before-apply workflow with explicit selection,
  warnings, matched/unmatched Books, and bounded errors.
- Do not invent background jobs, polling, or persistent import history unless a
  separate product decision introduces them.

### Library, Groups, and Shelves

The following legacy semantics remain useful even though their React surfaces
are now established:

- Library browsing has distinct Books, Authors, and Series axes. Catalog Tag
  filtering is Library-owned; it is not shared route state for Groups or Shelves.
- Selecting an Author or Series is a browsing context over Books. Lifecycle
  creation/editing is a separate workflow.
- Book Detail is read-only discovery. Mutations belong in explicit edit/manage
  workflows.
- Group membership curation never edits a user's global role.
- Public Group identity is managed through Server Settings, not normal Group
  metadata editing.
- A Group Book removal may affect Shelves owned by that Group and must not be
  presented as a harmless local detach.
- Shelf rows and item lists must preserve visibility and placeholder semantics;
  clients do not reconstruct hidden Book identity.
- Shelf ownership and `canEdit` come from server contracts. React does not infer
  existing-Shelf authority from a global role alone.

These are migration constraints, not a checklist of current components. Shared
Book, Group, Shelf, paging, tab, form, and page-shell primitives are documented
where they are current: `react-ui.md` and `react-ui-rules.md`.

### Accounts, Imports, and Server Settings

Useful historical boundaries are:

- generated temporary passwords are one-time transient results;
- connected-client tokens are never displayed after pairing;
- Library import is a synchronous EPUB/ZIP workflow, not a job system;
- Server Settings owns server display identity and Public Group identity;
- disabling and consolidating advanced Groups is an operator recovery workflow,
  not an ordinary Product UI toggle.

## React migration principles

### Runtime ownership

- React owns `/` and intended Product UI deep links.
- Django-rendered application surfaces are limited to first-time setup,
  login/logout, bounded framework error handling, and Django Admin as a service
  hatch.
- Retired templates, static assets, views, and routes remain parked under
  `reference/legacy_product_ui/` and are never imported, mounted, discovered, or
  tested as runtime behavior.
- There are no `/app/` or `/legacy/` compatibility mounts and no redirects or
  aliases for retired Product UI routes.

### Server and SDK boundary

- Existing REST/JSON APIs under `/api/v1/` are the server boundary.
- `@second-pass/spl-api` owns server communication, request paths, wire mapping,
  pagination shapes, and structured error normalization.
- React production code does not issue ad hoc `fetch()` calls or construct raw
  API URLs.
- The SDK returns app-facing camelCase objects. Wire names and server URL details
  do not leak into PageRegions or Components.
- Do not add compatibility aliases for pre-release SDK or route changes; update
  callers directly.

### Current user and server context

- `CurrentUser` contains authenticated account identity, role, memberships, and
  user-specific authority facts.
- Authenticated `ServerInfo` contains server-wide Product UI context: server
  identity, banner text, advanced-Group mode, Public Group identity, and version
  metadata.
- Authenticated bootstrap uses `/api/v1/server/info/`; anonymous
  `/.well-known/secondpass` remains public discovery and is not an authenticated
  Product UI bootstrap substitute.
- Public Group information in `ServerInfo` is display/configuration context, not
  proof of membership or edit authority.

### React layers

- App owns authenticated bootstrap and the global frame.
- Feature `*Orchestrator` files own SDK calls, route/query state, mutation
  workflows, and page assembly.
- `*PageRegion` files receive explicit data/actions and own only their section's
  presentation and local form sprawl.
- reusable `*Component` files are server-blind;
- production feature branches do not import one another;
- promote a shared component only after a real cross-feature contract exists.

Specific shared-component inventory and current adoption do not belong here.
In particular, this document does not mandate a generic row frame merely
because several feature rows look similar.

## Intentional migration deltas

These differences from the parked UI are deliberate and should not be
"restored" as missing parity:

- `/` replaces the legacy Dashboard route. Dashboard/banner copy is page
  content, not global AppFrame navigation chrome.
- `/profile/client-pairing` and authenticated JSON pairing APIs replace the
  retired Django `/client-api/authorize/` page.
- DRF browsable pages and `/api-auth/` are not Product UI surfaces.
- Author and Series read context lives in Library browsing; React does not add
  separate read-only entity routes merely to mirror old views.
- Managed Users have list/create/edit workflows without a separate User Detail
  page.
- Library Import renders the complete bounded API result; the parked client-side
  result cap is retired.
- Book Edit shelf management is intentionally restricted to Group-owned Shelves
  containing the Book. It includes the designated Public Group in simple mode,
  excludes personal and other users' listed Shelves, and does not provide
  add-to-shelf behavior.
- The Book Edit Library Groups section remains advanced-mode-only even though
  Group Shelves remains meaningful in simple mode.
- Group Detail Shelves is read-only discovery. Shelf mutation continues through
  Shelf Detail/Edit.
- Shelf editing uses server-supported immediate add/remove/up-down operations.
  It does not fake arbitrary position changes or drag/drop around unavailable
  placeholders.
- Product UI server context comes from authenticated `ServerInfo`, not `/me` or
  public discovery. The removed `server_release` field has no replacement.
- Contextual breadcrumbs use validated Router state plus canonical fallbacks;
  they do not infer navigation from browser history.
- Meaningful page-section tabs use controlled shared tabs and `?tab=`. Library
  axes, Shelf scopes, and list filters are not tabs.
- SDK contract tests are package-local. App and feature tests remain under the
  React app test area.

## Remaining migration work and open decisions

Only genuinely unresolved legacy-derived work belongs here:

1. **Additional Book lifecycle actions.** EPUB/file replacement, Book deletion,
   and Reader/Open integration remain outside the current Book editor/detail
   scope. Treat each as a focused product/API decision, not automatic legacy
   parity.
2. **Arbitrary Shelf positioning.** Current up/down mutation is the supported
   workflow. Move-to-position and drag/drop remain deferred until unavailable
   placeholder semantics can be preserved without frontend fiction.

Production/Docker React integration and dependency advisories are tracked in
their operational documents and tooling, not in this migration reference.
