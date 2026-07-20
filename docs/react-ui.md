# React Product UI

The Product UI lives in `web/react`. Retired Django Product UI templates, static assets, views, and routes are parked under `web/legacy` for reference only and are not mounted. Old Product UI tests are not maintained.

## Development

Run Django on port 8000 and the Product UI Vite server on port 5174. Port 5173 remains available for the standalone Reading Client. From `web/react`, run `npm install` and `npm run dev`. Vite proxies `/api`, `/media`, `/admin`, and `/api-auth` to Django, so the app uses Django session authentication through same-origin-style URLs.

Vite is the primary development surface. Django serves the authenticated React shell at `/` and intended Product UI deep links when a local build exists. Before bootstrap, these routes redirect to `/setup/`; afterward unauthenticated requests redirect to `/login/`. `/app/` is retired.

## Deferred production integration

The current local build and root-shell integration may be used for smoke checks. Docker and production React build integration are explicitly deferred.

First-time setup, `/login/`, `/logout/`, DRF `/api-auth/` internals, and the Django `/admin/` service hatch remain Django-rendered. The old Reader Client authorization webpage is retired; its backend API/token logic remains for later React work. Dashboard, library/catalog, books, groups, shelves, users and password flows, imports, and Product UI server settings are React scope.

## Server boundary

`web/react/packages/spl-api` is the first-party, framework-light TypeScript server communication package. It owns `fetch`, credentials, JSON parsing, structured error normalization, pagination types, server response mapping, and domain calls. React routes, components, and hooks consume its stable app-facing objects; they do not scatter raw `fetch()` calls or API URLs.

The Product UI uses the existing REST/JSON endpoints under `/api/v1/`. Do not add GraphQL or a generated API client.
