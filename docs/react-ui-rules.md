# React Product UI Rules

> **Document purpose:** This contains durable cross-page React presentation, interaction, and architectural rules. It is neither a historical migration specification nor a running implementation log; those belong in `docs/react-implementation-spec.md` and `docs/react-ui.md`, respectively.

This is the running list of cross-page presentation and interaction rules that are easy to lose when implementing individual React branches. API storage shapes remain documented in `docs/api.md`; these rules describe Product UI meaning.

## File responsibilities

- Folders must earn their keep. A folder for one or two files is usually noise unless it marks a real architectural boundary.
- Use a folder for a coherent group of three or more files, or for a group expected to grow there.
- Prefer responsibility suffixes (`Orchestrator`, `PageRegion`, `Component`, and `SubComponent`) before adding directory depth.
- Feature route controllers use the `Orchestrator` suffix and own SDK calls and workflow state.
- Major page sections use the `PageRegion` suffix and receive explicit data/action props.
- Presentational pieces use `Component`; use `SubComponent` only for a clearly subordinate element.
- Feature folders may use shared `regions/` and `components/` folders when each contains several related files.
- Do not prematurely create `list/`, `create/`, or `edit/` folders unless each workflow has grown its own coherent cluster.
- Promote genuinely cross-feature behavior into a focused `src/shared` module. Do not promote feature-specific rules merely to reduce line count.
- A feature may contain many focused files. Prefer explicit responsibility names over a large page file.
- Keep app and feature Vitest files centralized under `web/react/src/__tests__/`; organize them by subject rather than colocating them with production modules. Keep SDK contract tests package-local under `web/react/packages/spl-api/src/__tests__/`.

## User identity and roles

- Product UI permissions are derived from stable SDK role facts, not invented
  generic capability fields. `CurrentUser` exposes mutually exclusive
  `isOwner`, `isManager`, `isLibrarian`, and `isReader` facts from the existing
  `is_owner` and `role` wire fields. Presentation helpers such as
  `isAtLeastLibrarian`, `isAtLeastManager`, `canSeeImports`, `canSeeUsers`, and
  `canSeeServerSettings` may compose those facts; they do not create backend
  authority.
- Owner is presented as the highest user role, above Manager.
- The API intentionally exposes `role` and `is_owner` separately. UI role displays resolve `is_owner` first and show `Owner`; they do not show a redundant separate Owner row.
- Use the shared user-role presentation helper so role precedence stays consistent across Profile and future user surfaces.
- The Users list uses the same effective-role rule, so Owner is displayed as the user's role rather than as a second status.
- Users surfaces display role names as `Owner`, `Manager`, `Librarian`, `Curator`, and `Reader`.
- Primary navigation shows My Marginalia, Library, and Shelves to every
  authenticated user; Imports to Librarian+; Users to Manager+; and Server
  Settings to Owner. Groups is visible to every authenticated role only when
  advanced Library Groups are enabled.
- Simple mode hides the Groups branch, custom-group controls, and advanced
  relationship tabs. It does not mean groups cease to exist: the designated
  Public group remains a real access and shelf-ownership scope, and Shelves may
  still present Public group ownership where the API returns it.
- Owner may create Manager, Librarian, or Reader accounts. Manager may create only Librarian or Reader accounts; lower roles cannot create users.
- React user creation does not expose activity state. New users are active by default and receive a generated one-time temporary password that must not be persisted in frontend storage.
- Managed User Edit uses `Active` and `Inactive` labels rather than exposing boolean values. There is no separate User Detail/View page.

## Server-driven lists

- List Orchestrators own URL query state and send it through `@second-pass/spl-api`; the server owns filtering, sorting, and pagination.
- Search, filters, ordering, page, and page size must survive Back/Forward navigation. Query-shape changes reset the page, while pager navigation changes only the page.
- Row Components render the returned page. They do not re-filter or re-sort server results.
- Promote paging controls only when their inputs are stable page metadata and callbacks; shared pagers must remain server-blind.
- Product list pagers offer 20/30/40/50 by default. A feature with an established different contract supplies its own sizes explicitly.
- Main list frames use a lean top pager without page-size selection and a full bottom pager. Nested detail and mutation lists remain free to use a single pager when duplicate controls would add clutter.
- List ordering controls use the shared icon menu with the `Order` label inline to the left. The closed control shows the selected option's icon and label; every menu row shows its associated icon, and standard focus, Escape, blur, and outside-click dismissal remain available.
- Main paginated-list frames may accept server-blind top controls such as ordering. `PagerComponent` remains unaware of ordering values and feature query semantics.
- Library Books search is title/sort-title search through the Book list endpoint. Broad Library search is reserved for picker and Add Books workflows.
- Product language and app-facing fields use Catalog Tags. Compact Book wire `catalog_tags` is normalized to `catalogTags` by the SDK; row Components never inspect wire names.

## Server and validation boundaries

- React forms consume app-facing camelCase field-error names. Wire field names are normalized inside `@second-pass/spl-api` and never appear in PageRegion field lookups.
- Client-only validation uses the shared local validation error with an action message and optional app-facing field errors. It does not construct `ApiError`, because no HTTP request occurred.
- Values returned by an API payload may be rendered as ordinary escaped React text. Never render API strings as raw HTML. Boundary checks protect communication and wire-name mechanics; they do not impose additional payload distrust or client-side redaction.
- PageRegions and Components may import stable SDK types, but SDK operations belong in App or feature Orchestrators.
- Production feature branches do not import one another. Promote genuinely shared code to `app`, `shared`, or `components`; tests may compose subjects across features.

## Page-section tabs

- Real page-section tabs use the controlled, server-blind `TabListComponent`; callers own panels, data loading, and available content.
- Meaningful tab selection is URL-backed with `?tab=` through feature query helpers. Default tabs are omitted, invalid tabs normalize to the page default, and contextual Router state is preserved.
- Dirty editing and navigation confirmation remain page responsibilities. Immediate mutations may disable tab selection until they settle.
- Library axes, Shelf scopes, Catalog Tags, search, ordering, pagination, and other filters are navigation/filter controls rather than tabs.
- When current role facts clearly cannot access Users, Imports, or Server Settings, the route falls back to Dashboard before mounting the feature Orchestrator. Backend authorization remains authoritative for allowed roles and unexpected permission failures remain visible.

## Server settings

- Server Settings is Owner-only. Public Library identity is managed there and not through normal Group editing.
- `/me` capability flags may be omitted when false. `@second-pass/spl-api` normalizes them to stable app-facing booleans; React uses those booleans and never implements sparse-wire semantics itself.
- `/server` represents General without a tab query; Public Library and Library Groups use `?tab=public-library` and `?tab=library-groups`. Editing is inline; tabs do not create separate routes.
- Enabling advanced groups is shown only in Library Groups edit mode and requires deliberate confirmation. The normal React UI does not offer a disable action; disabling is a Django Admin Service Hatch recovery operation.
- Expose the Django Admin/Service Hatch link only when `CurrentUser.canAccessDjangoAdmin` is true. React does not probe `/admin/`.

## Account management

- A user with `must_change_password` may use only the React `/profile/password` workflow (and Django logout) until a successful change refreshes current-user state.
- Profile displays group membership and curator/Public status, but does not mutate memberships.
- Profile may revoke connected client sessions and log out other web sessions. It never displays bearer tokens.
- Client pairing approval is React-only at `/profile/client-pairing`; `/client-api/authorize/` does not exist.
- Generated temporary passwords use a selectable read-only input with the one-time warning immediately below it. They remain only in transient React state.
- Advanced group membership editing uses distinct membership rows and a separate Add-to-group form. Public membership is removable when another group remains; the backend owns last-group fallback repair. Public has no curator checkbox and uses the shared help component with `Only Librarians/Managers may Curate the Public Group`. Simple mode omits unsupported custom-group controls.
- Use the shared `HelpPopoverComponent` for short contextual help. It must remain server-blind, keyboard accessible, labelled and described for assistive technology, and expose the same content on hover, focus, and click without a native `title` tooltip.

## Breadcrumbs

- Breadcrumbs describe explicit in-app navigation context first and use the destination Orchestrator's canonical workflow fallback when context is unavailable or invalid.
- Child links may carry a structured trail of labels and internal URLs in React Router location state. Breadcrumb data never contains raw HTML, and separators belong to AppFrame CSS rather than the data.
- Breadcrumb icons use validated semantic keys that AppFrame maps to decorative Material Symbols. Raw icon tokens are never serialized into Router state; labels remain the accessible source of meaning, and action crumbs remain text-first unless deliberately designed otherwise.
- Do not infer context from browser history, persist or replay a history trail, or rely only on static route metadata.
- AppFrame renders breadcrumbs; branch Orchestrators own fallback trails and outgoing child context. Top-level navigation starts a new branch.
- Breadcrumb links preserve the validated trail through the destination by default. Canonical branch/base ancestors are explicit reset points; do not infer breadcrumb context from browser history.
- Base branch routes such as `/profile` and `/users` do not render breadcrumbs. Breadcrumbs begin when navigation enters a child or contextual workflow.
- Direct loads and refreshes use the canonical fallback. Forced password change suppresses breadcrumbs.

## Destructive collection actions

- Use the shared `RemoveIconButton` for remove, revoke, detach, and delete actions presented as compact row/list controls.
- It owns the Material Symbols `delete` token, danger styling, tooltip, and accessible label. Do not recreate this button with ad hoc icon spans or local styles.
- The calling branch still owns confirmation and the actual operation; the shared button remains server-blind.

## Interactive surfaces

- A mouse-interactive element presented with a surrounding box, border, card, row, or chip should normally provide at least a restrained decorative hover highlight so it does not appear inert. Keyboard-operable content should receive an equivalent `focus-visible` or `focus-within` treatment where appropriate.
- Do not add active-looking hover treatment to disabled controls or purely static containers. Hover decoration supplements accessible labels, focus behavior, and control semantics; it does not make a non-interactive box interactive.

## Group identity

- Group identity pills use the shared structural `GroupBadgeComponent`. Public/Common Room receives the green Public treatment; ordinary groups receive the neutral group treatment.
- Usernames are plain text without an `@` prefix, angle-bracket notation, or pill treatment. Identity displays place the shared person icon beside the username; full-name contexts use `First Last · username`. Group/Public ownership retains its shared pill treatment.
- Curator and membership state remain separate status badges. The group identity component has no permission or mutation behavior.

## Form actions

- Shared text buttons use the `small` or `medium` size vocabulary and `primary`, `secondary`, or `danger` tone. Page-level create/save actions are medium primary, manage/edit and cancel actions are secondary, destructive text actions are danger, and compact row or pager actions are small.
- Shared icon buttons use the same small/medium sizing; add/remove controls retain their established success/danger semantics.
- Product UI text-like inputs, native selects, and textareas use the shared React-shell form-control treatment. Use medium controls for forms and search/action rows, and the small class only for intentionally compact controls such as the pager page-size select.
- Keep native control semantics and keyboard behavior. File inputs, checkboxes, and radio buttons retain purpose-specific treatment rather than inheriting the text-control surface.
- Form and workflow action rows are right-aligned unless a page-specific interaction explicitly calls for another placement.
- Put secondary or canceling actions before the default/desirable primary action so the primary action is farthest right.
- Put success, error, or other action status immediately left of the buttons and right-align it toward the controls. Reserve the feedback area where practical so status changes do not cause large layout jumps.
- Successful action feedback clears itself after roughly five seconds. Errors remain visible until the user retries, cancels, or otherwise clears that workflow state.

## Page headings

- Product UI routes use `ProductPageShellComponent` for the shared content width, left edge, top/body rhythm, and optional title/action row. AppFrame breadcrumbs and footer align to the same frame.
- Feature pages must not add their own page-level max width or centering without an explicit product reason. Deliberately narrower forms or subregions may keep local widths inside the shared frame.
- Product page titles use the restrained legacy Product UI scale rather than oversized landing-page typography. Keep titles on one line at normal desktop widths and allow wrapping only when the viewport requires it.
- Book Detail may keep its distinct internal hero composition, but it still uses the shared page frame and breadcrumb alignment.

## Operational results

- Successful operational rows prefer human-facing names and metadata over UUIDs, hashes, storage identities, or filesystem details. When richer safe metadata is unavailable, use the backend-provided safe source label.
- Failure and conflict rows should include the bounded safe source label, status, and actionable safe message supplied by the API. Never render raw uploads, unsafe archive paths, tracebacks, or internal storage details.
