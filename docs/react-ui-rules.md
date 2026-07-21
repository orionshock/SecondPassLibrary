# React Product UI Rules

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
- Keep all Vitest files centralized under `web/react/src/__tests__/`; organize them by subject rather than colocating them with production modules.

## User identity and roles

- Owner is presented as the highest user role, above Manager.
- The API intentionally exposes `role` and `is_owner` separately. UI role displays resolve `is_owner` first and show `Owner`; they do not show a redundant separate Owner row.
- Use the shared user-role presentation helper so role precedence stays consistent across Profile and future user surfaces.
- The Users list uses the same effective-role rule, so Owner is displayed as the user's role rather than as a second status.
- Users surfaces display role names as `Owner`, `Manager`, `Librarian`, `Curator`, and `Reader`.
- Owner may create Manager, Librarian, or Reader accounts. Manager may create only Librarian or Reader accounts; lower roles cannot create users.
- React user creation does not expose activity state. New users are active by default and receive a generated one-time temporary password that must not be persisted in frontend storage.
- Managed User Edit uses `Active` and `Inactive` labels rather than exposing boolean values. There is no separate User Detail/View page.

## Server-driven lists

- List Orchestrators own URL query state and send it through `@second-pass/spl-api`; the server owns filtering, sorting, and pagination.
- Search, filters, ordering, page, and page size must survive Back/Forward navigation. Query-shape changes reset the page, while pager navigation changes only the page.
- Row Components render the returned page. They do not re-filter or re-sort server results.
- Promote paging controls only when their inputs are stable page metadata and callbacks; shared pagers must remain server-blind.

## Account management

- A user with `must_change_password` may use only the React `/profile/password` workflow (and Django logout) until a successful change refreshes current-user state.
- Profile displays group membership and curator/Public status, but does not mutate memberships.
- Profile may revoke connected client sessions and log out other web sessions. It never displays bearer tokens.
- Client pairing approval is React-only at `/profile/client-pairing`; `/client-api/authorize/` does not exist.
- Generated temporary passwords use a selectable read-only input with the one-time warning immediately below it. They remain only in transient React state.
- Advanced group membership editing uses distinct membership rows and a separate Add-to-group form. Public membership has no remove or curator control; simple mode omits unsupported custom-group controls.

## Breadcrumbs

- Breadcrumbs describe explicit in-app navigation context first and use the destination Orchestrator's canonical workflow fallback when context is unavailable or invalid.
- Child links may carry a structured trail of labels and internal URLs in React Router location state. Breadcrumb data never contains raw HTML, and separators belong to AppFrame CSS rather than the data.
- Do not infer context from browser history, persist or replay a history trail, or rely only on static route metadata.
- AppFrame renders breadcrumbs; branch Orchestrators own fallback trails and outgoing child context. Top-level navigation starts a new branch.
- Base branch routes such as `/profile` and `/users` do not render breadcrumbs. Breadcrumbs begin when navigation enters a child or contextual workflow.
- Direct loads and refreshes use the canonical fallback. Forced password change suppresses breadcrumbs.

## Destructive collection actions

- Use the shared `RemoveIconButton` for remove, revoke, detach, and delete actions presented as compact row/list controls.
- It owns the Material Symbols `remove_circle` token, danger styling, tooltip, and accessible label. Do not recreate this button with ad hoc icon spans or local styles.
- The calling branch still owns confirmation and the actual operation; the shared button remains server-blind.

## Form actions

- Form and workflow action rows are right-aligned unless a page-specific interaction explicitly calls for another placement.
- Put secondary or canceling actions before the default/desirable primary action so the primary action is farthest right.
- Put success, error, or other action status immediately left of the buttons and right-align it toward the controls. Reserve the feedback area where practical so status changes do not cause large layout jumps.
