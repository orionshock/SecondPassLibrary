# React Product UI

> **Document purpose:** This is the running record of the current React Product UI: implemented surfaces, active behavior, architecture, and deferred work. Historical migration guidance belongs in `docs/react-implementation-spec.md`; durable cross-page rules belong in `docs/react-ui-rules.md`.

The Product UI lives in `web/react`. Retired Django Product UI templates, static assets, views, and routes are isolated under `reference/legacy_product_ui` for reference only. They are outside the Django application and must not be imported, discovered, or mounted. Old Product UI tests are not maintained as executable tests.

## Development

Run Django on port 8000 and the Product UI Vite server on port 5174. Port 5173 remains available for the standalone Reading Client. From `web/react`, run `npm install` and `npm run dev`. Vite proxies `/api`, `/media`, `/admin`, `/login`, `/logout`, and `/setup` to Django, so the app uses Django session authentication through same-origin-style URLs.

Vite is the primary development surface. Django serves the authenticated React shell at `/` and intended Product UI deep links when a local build exists. Before bootstrap, these routes redirect to `/setup/`; afterward unauthenticated requests redirect to `/login/`.

There are no `/app/` or `/legacy/` mounts. Retired paths are not redirected or otherwise special-cased.

The React shell bootstraps the authenticated user through `getCurrentUser()` and server identity through `getServerInfo()` from `@second-pass/spl-api`. Server identity comes from `/.well-known/secondpass`. Components do not make raw `fetch()` calls. The shell provides loading, login-required, retryable error, server identity/banner, user identity, and logout states. `/logout/` remains a Django endpoint.

Dashboard (`/`) and My Marginalia remain placeholders. Shelves implements list/detail plus metadata and immediate Book membership management at `/shelves`, `/shelves/:shelfId`, `/shelves/new`, and `/shelves/:shelfId/edit`; the list exposes Personal, Shared by Others, and Group Shelves scopes. Groups implements an advanced-mode-only list/detail branch plus metadata lifecycle at `/groups`, `/groups/:groupId`, `/groups/new`, and `/groups/:groupId/edit`; Group detail has read-only Books and Members tabs. Library (`/library`) implements top-level Books, Authors, and Series browse axes plus selected Author and Series Book contexts with URL-backed search, ordering, and pagination. Books retains its paginated Catalog Tag facet and compact rows; Author and Series rows show visible Book counts and bounded cover previews without biography or summary prose. Selecting an Author or Series name reuses the compact Book list inside the stable Library shell. `/library/books/:bookId` is real read-only Book Detail and `/library/books/:bookId/edit` is the Librarian+ core bibliographic editor. Imports (`/imports`) provides the synchronous EPUB/ZIP library-upload workflow for Librarian, Manager, and Owner users. Users (`/users`) is a server-driven React list: its search, role/status filters, ordering, page, and page size live in the URL, while the API owns filtering, sorting, and pagination. User creation is available at `/users/new`; managed-user editing is `/users/:profileId/edit`, with no separate User Detail route. Profile (`/profile`) owns self-profile editing, membership display, session actions, and connected clients. Password changes use `/profile/password`; pairing approval uses `/profile/client-pairing`. The pairing page accepts `?code=...`, immediately looks up a supplied code, and otherwise presents code entry before approval. Server Settings is available to the Owner at `/server`, with General, Public Library, and Library Groups selected through `?tab=`. Unknown paths within Django's explicit React route policy render an in-shell not-found page.

## Deferred production integration

The current local build and root-shell integration may be used for smoke checks. Docker and production React build integration are explicitly deferred.

First-time setup, `/login/`, `/logout/`, and the Django `/admin/` service hatch are the only retained Django-rendered application surfaces. DRF browsable pages and `/api-auth/` are disabled. The old Reader Client authorization webpage is retired. React pairing approval uses authenticated JSON endpoints under `/api/v1/client-api/`; token delivery remains confined to external-client polling. Dashboard, library/catalog, books, groups, shelves, users, imports, and Product UI server settings are React scope.

## Server boundary

`web/react/packages/spl-api` is the first-party, framework-light TypeScript server communication package. It owns `fetch`, credentials, JSON parsing, structured error normalization, pagination types, server response mapping, and domain calls. React routes, components, and hooks consume its stable app-facing objects; they do not scatter raw `fetch()` calls or API URLs.

SDK errors expose operation fields with app-facing camelCase names. Wire field names remain inside the SDK. Local form validation uses the React shared validation error rather than manufacturing an HTTP `ApiError`. Text returned in API payloads may be rendered normally through React's escaped text rendering; never inject API strings as raw HTML. The source boundary check enforces communication and field-name hygiene, not distrust of returned payload values.

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

The SDK public index exports domain operations, app-facing types, and errors—not its low-level request client. `npm test` runs a lightweight source check that rejects raw server communication in app source, production feature-to-feature imports, SDK imports in shared UI primitives, React imports in the SDK, wire field-error lookups in React, runtime SDK operation imports in presentational PageRegions/Components, and query construction in presentational files. Type-only imports of stable SDK app-facing models are allowed there. Vite proxy declarations are development transport configuration, not an application communication layer.

Within the SDK, `accounts.ts` owns current-user/profile/password mapping while `accountSessions.ts` owns web-session and connected-client operations and metadata mapping.

Profile at `/profile` is the first real React feature page. It displays current identity and group/curator status, edits supported self-profile fields, logs out other web sessions, and lists/revokes connected clients. The App orchestrator forces `must_change_password` users through the dedicated password route until refreshed current-user state clears the requirement. All operations use `@second-pass/spl-api`. Dashboard at `/` is a styled shell placeholder only; it has no metrics or dashboard-specific API calls yet.

Users list behavior is owned by `UsersListOrchestrator`; its PageRegions render filters and paginated results, while row Components remain presentational. The shared pager consumes stable page metadata and callbacks without knowing server URLs. `@second-pass/spl-api/users.ts` adapts managed-user wire payloads and query names to app-facing objects.

`LibraryOrchestrator` owns axis-aware URL normalization, the active Books/Authors/Series list load, bounded out-of-range recovery, and independent Catalog Tag retry state. Selected contexts use `view=authors&author=<uuid>` or `view=series&series=<uuid>`; the entity parameter follows `view` before `tag`, optional `ordering`, `page`, `page_size`, and `q`. Default Books view, per-context ordering, page 1, and page size 20 are omitted. Entering or clearing a context preserves Catalog Tag and page size while clearing search, ordering, and page. Every axis button navigates to that axis's canonical base, including the already-active axis: selected context, Catalog Tag, search, ordering, and page are cleared, while non-default page size is preserved. Book search calls `/library/books/`, not broad Library search; Author and Series requests include bounded previews, while selected contexts send `author` or `series` to the compact Book endpoint. Selected contexts independently load the role-scoped Author or Series detail so direct loads render the real entity name and a three-line expandable plain-text biography or summary; Router state is only an optimistic loading fallback. Missing and unavailable entities share one bounded context state, and retryable detail failures do not block the filtered Book list. The Catalog Tag rail filters every top-level axis and selected context. Its counts remain role-scoped Book counts, not context-specific counts. The SDK maps compact wire `catalog_tags` to app-facing `catalogTags` and axis wire fields to stable camelCase summaries. Book rows display title, authors, series/index, publisher, and at most six Catalog Tag pills. Author and Series rows display name, role-scoped Book count, and up to six previews, but not biography or summary. Reader sessions and bearer clients receive visibility-scoped axes; Librarian+ sessions receive the complete Author/Series catalog through the same endpoints. Shared Book cover, metadata, and preview-strip components remain server-blind. App list pagers default to 20/30/40/50 unless a caller supplies an intentional exception; Users retains its established 20/50/100/200 sizes.

`BookDetailOrchestrator` owns the visibility-scoped detail read, loading/retry/not-found states, current group-mode context, contextual breadcrumbs, and an independently retryable lazy read of visible shelves containing the Book. The page renders the large cover identity, bibliographic metadata, Catalog Tags, escaped plain-text description, and restrained actions as its primary surface. Lightweight local Shelves, optional advanced-mode Groups, and Metadata tabs sit below the hero: Shelves renders a read-only compact list of visible shelf identity, ownership, visibility, and viewer-visible item counts; Groups renders only read-only visible detail summaries; and Metadata contains publication, identifier, and file facts, including the checksum in the nested File panel. Shelf names in this independently loaded Book Detail section link to Shelf Detail while preserving Book breadcrumb context; shelf mutation remains deferred. Catalog Tags remain in the primary detail area rather than being repeated in Metadata. The nested API `file` object is a projection of canonical EPUB fields on the Book. A `null` projection is handled once in the hero as an exceptional unavailable-EPUB repair state, never as ordinary optional metadata; Download EPUB is shown only when the projection supplies `downloadUrl`. The SDK normalizes the server-built absolute download URL to its same-origin API path so Product UI session credentials pass through the active React/Django proxy boundary. Storage/source details, Reader/Open, deletion, cover mutation, shelf actions, and group assignment actions are not rendered. Edit is shown only to Librarian, Manager, and Owner.

`BookEditOrchestrator` owns the guarded `/library/books/:bookId/edit` workflow, Book initialization, independently retryable role-scoped picker reads, local draft/dirty state, validation, and one transactional Book PATCH. Its core tabs edit Book identity text, catalog/publication data and complete Catalog Tag names, ordered existing Author plus existing Series assignment, and the complete identifier replacement set. Identifier edit rows use canonical schemes and scheme/value only; response ids are unstable replacement-row identities and are never sent. Librarian+ picker reads use the normal Author/Series endpoints, which already return the complete catalog for those sessions. A successful save replaces the baseline from the returned detail and remains on Edit; dirty cancel and browser unload request confirmation. Cover replace/clear is a separate immediate multipart/DELETE workflow opened by the single Change Cover control. Clear confirmation stays inside that dialog; backend content validation remains authoritative, there is no local preview, and a returned cover URL updates only the displayed Book cover without resetting the metadata draft or baseline. When advanced Library Groups are enabled, Librarian+ users also receive a Library Groups tab. Its all-page group picker and immediate assignment POST/DELETE operations are independent from metadata Save; every successful mutation refreshes Book Detail and merges only the returned groups. The tab is absent in simple mode and is not a Reader-curator management surface. Removal requires confirmation because same-group shelf relationships may be affected, and removing the final non-Public assignment allows the backend to restore Public/Common Room. Shelves, file fields, deletion, and Reader/Open remain outside this slice. React does not create Authors or Series inline.

Author and Series lifecycle create/edit routes are guarded by the existing Librarian+ role facts: `/library/authors/new`, `/library/authors/:authorId/edit`, `/library/series/new`, and `/library/series/:seriesId/edit`. The small parallel forms edit name, sort name, and biography or summary through explicit SDK POST/PATCH operations. Duplicate names remain allowed, blank sort names use the backend normalization contract, dirty navigation asks for confirmation, Create replaces to the new Edit route, and Edit remains in place with returned values as its new baseline. Top-level axis actions expose creation, while selected contexts and Book Edit provide bounded lifecycle navigation; Author and Series browse rows remain focused on contextual browsing rather than editing. Book Edit never embeds lifecycle forms. Author/Series deletion remains absent.

`UserCreateOrchestrator` owns the create workflow and one-time temporary-password result. The React form never exposes or sends account activity; new managed users use the backend's active-by-default contract and must change the generated password on first login. Create forms use the shared label-left fields and right-oriented action/feedback row.

`UserEditOrchestrator` owns managed-user detail updates, password controls, and advanced-group membership operations. It adapts the existing group-scoped membership API through the SDK. Password reset results reuse the shared read-only temporary-password display and remain only in component state. Public membership is removable when another membership remains, never receives a membership-level curator flag, and is restored by the backend when it is the last-resort fallback. Simple mode omits custom membership controls.

`ImportsOrchestrator` owns the synchronous library import workflow. It submits exactly one EPUB or ZIP through `@second-pass/spl-api`, keeps only the latest result in transient React state, and renders every returned item without a client-side cap. Book-associated rows use the API's title, ordered author names, and optional series/index summary; successful rows fall back to the safe source label only when that summary is unavailable. Duplicate, skipped, failed, and conflicting rows retain bounded safe source/message detail. The page does not create jobs, poll, persist history, stage records, or expose Book IDs and storage details.

`ServerSettingsOrchestrator` owns the Owner-only `/server` branch. Tabs are URL-backed (`general`, `public-library`, and `library-groups`), while editing remains inline and does not create child routes. General and Public Library forms use the shared label/control and action-feedback conventions. Advanced groups can be enabled only from Library Groups edit mode after explicit confirmation; ordinary React UI does not offer disable/collapse. Django Admin remains an external recovery boundary and is linked only when the SDK-normalized `canAccessDjangoAdmin` capability is true.

`GroupsListOrchestrator` owns advanced-mode `/groups` search, name ordering,
pagination, bounded page recovery, and preview-book reads. Rows show the
server-provided Public identity, exact current-user Curator membership, escaped
description excerpts, and bounded cover previews. They do not show a Book
count because the Group API does not return one. Manager/Owner sessions receive
the `/groups/new` metadata lifecycle. `GroupDetailOrchestrator` owns
`/groups/:groupId`, role-scoped detail loading, and URL-backed Books/Members
tabs. Books reuse the shared compact Book row with contextual Group
breadcrumbs; Members expose only username and curator state. Custom Group
metadata editing at `/groups/:groupId/edit` is operation-specific: Manager/Owner
may edit name and description, while Librarian and the exact custom-group
curator may edit description. Authorized Group curators and Librarian+ sessions
also receive immediate Books and Add Books tabs in Group Edit. Candidate search
uses Library search with `exclude_group`; add/remove operations remain independent
from metadata Save. Removal is confirmed because it also removes the Book from
Group-owned Shelves. A cleanup-conflict response leaves the assigned row intact
and is shown as a persistent section-local error. Public metadata remains owned
by Server Settings, while Librarian+ may curate Public Books. Member mutation,
Delete, and Group Shelves remain deferred.
Simple mode guards all Group routes before their Orchestrators issue API reads.

`ShelvesListOrchestrator` owns `/shelves` in both simple and advanced modes.
Its URL-backed Product scopes are Personal (default), Shared by Others, and
Group Shelves; API `scope=all` is not exposed. Rows render only server-provided
ownership, visibility, viewer-visible item count, description, Public identity,
and bounded previews. `ShelfDetailOrchestrator` owns `/shelves/:shelfId`, its
read-only Shelf header, URL-backed item ordering, pagination, bounded recovery,
and shared compact Book rows with contextual Shelf breadcrumbs. Separate Shelf
Create and Edit Orchestrators own metadata lifecycle at `/shelves/new` and
`/shelves/:shelfId/edit`. All authenticated users can create personal shelves;
manageable group ownership is offered only from existing role and exact-curator
facts. Ownership is create-only, personal visibility is editable, and group
shelves keep group-controlled visibility. Shelf responses provide the
authoritative `canEdit` affordance for existing shelves. Shelf Edit adds Books
and Add Books tabs. Books uses the editor inventory: visible Books can move
up/down across locked unavailable placeholders, and retained unavailable rows
can be removed by ShelfItem identity without exposing Book metadata. Add,
remove, and reorder mutations are immediate and independent from metadata Save;
adds remain append-only. Blank Add Books search performs no request;
personal shelves use broad Library search while group shelves use their owning
Group Books endpoint, both with `exclude_shelf`. Deleting a Shelf removes its
ShelfItems but never Books or files. Drag/drop, move-to-position, and the Group
Detail Shelves tab remain deferred.

The parked UI under `reference/legacy_product_ui` may inform palette, spacing, and interaction tone only. It is not an implementation dependency or active contract.

Cross-page product semantics that are not API shapes are tracked in [React Product UI Rules](react-ui-rules.md).

## Contextual breadcrumbs

Breadcrumbs prefer explicit navigation context carried in React Router location state. A link to a child workflow builds a structured text/internal-URL trail; it never carries HTML. Context is marked for the current app runtime so a refresh cannot replay stale history state. On direct entry, refresh, external navigation, or malformed state, the destination Orchestrator supplies its canonical fallback. Breadcrumbs do not inspect browser history and are not defined solely as static route metadata.

`AppFrame` owns the consistent breadcrumb position and visual separators. Orchestrators register the resolved trail for their pathname. Breadcrumb links preserve the validated trail through the destination by default; canonical branch/base ancestors explicitly reset it. Base branch routes such as `/profile` and `/users` do not render breadcrumbs, and top-level navigation starts a new branch without carrying stale context. Context is never inferred from browser history. Child workflows retain their canonical hierarchy. The forced password-change workflow suppresses breadcrumbs so it does not offer navigation away from the required action.

## Shell and UI conventions

`AppFrame` owns the compact server/navigation/account header and the low-emphasis product/version footer. Branch Orchestrators own mutations; PageRegions own controlled local form presentation where appropriate. Shared action rows, feedback, normalized mutation errors, and field-error extraction live above individual features. Cancel never calls the server.

Use the shared `MaterialIcon` component for Material Symbols instead of ad hoc icon spans. It centralizes the outlined-font class, token rendering, sizing, and decorative versus labeled accessibility behavior.
Use the shared `AddIconButton` and `RemoveIconButton` for compact draft-list add/remove controls. They use the Material Symbols `add` and `delete` treatments with caller-supplied accessible labels. Feature branches remain responsible for confirmation and mutation behavior; removable tag chips retain their compact close treatment.

All Vitest files live together under `web/react/src/__tests__`; do not create colocated `*.test.*` files or component-specific test directories. `vite.config.ts` limits discovery to that directory. The workspace recommends the Vitest Explorer extension so the suite is available in VS Code's Testing panel; `npm run test:vitest` provides its watch-mode command.
