# React Product UI Rules

This is the running list of cross-page presentation and interaction rules that are easy to lose when implementing individual React branches. API storage shapes remain documented in `docs/api.md`; these rules describe Product UI meaning.

## File responsibilities

- Feature route controllers use the `Orchestrator` suffix and own SDK calls and workflow state.
- Major page sections use the `PageRegion` suffix and receive explicit data/action props.
- Presentational pieces use `Component`; use `SubComponent` only for a clearly subordinate element.
- Promote genuinely cross-feature behavior into a focused `src/shared` module. Do not promote feature-specific rules merely to reduce line count.
- A feature may contain many focused files. Prefer explicit responsibility names over a large page file.
- Keep all Vitest files centralized under `web/react/src/__tests__/`; organize them by subject rather than colocating them with production modules.

## User identity and roles

- Owner is presented as the highest user role, above Manager.
- The API intentionally exposes `role` and `is_owner` separately. UI role displays resolve `is_owner` first and show `Owner`; they do not show a redundant separate Owner row.
- Use the shared user-role presentation helper so role precedence stays consistent across Profile and future user surfaces.

## Account management

- A user with `must_change_password` may use only the React `/profile/password` workflow (and Django logout) until a successful change refreshes current-user state.
- Profile displays group membership and curator/Public status, but does not mutate memberships.
- Profile may revoke connected client sessions and log out other web sessions. It never displays bearer tokens.
- Client pairing approval is React-only at `/profile/client-pairing`; `/client-api/authorize/` does not exist.

## Destructive collection actions

- Use the shared `RemoveIconButton` for remove, revoke, detach, and delete actions presented as compact row/list controls.
- It owns the Material Symbols `remove_circle` token, danger styling, tooltip, and accessible label. Do not recreate this button with ad hoc icon spans or local styles.
- The calling branch still owns confirmation and the actual operation; the shared button remains server-blind.

## Form actions

- Form and workflow action rows are right-aligned unless a page-specific interaction explicitly calls for another placement.
- Put secondary or canceling actions before the default/desirable primary action so the primary action is farthest right.
- Put success, error, or other action status immediately left of the buttons and right-align it toward the controls. Reserve the feedback area where practical so status changes do not cause large layout jumps.
