# React Product UI

The Product UI lives in `web/react`. Retired Django Product UI templates, static assets, views, and routes are parked under `web/legacy` for reference only and are not mounted. Old Product UI tests are not maintained.

## Development

Run Django on port 8000 and the Product UI Vite server on port 5174. Port 5173 remains available for the standalone Reading Client. From `web/react`, run `npm install` and `npm run dev`. Vite proxies `/api`, `/media`, `/admin`, and `/api-auth` to Django, so the app uses Django session authentication through same-origin-style URLs.

Vite is the primary development surface. `/` redirects to `/app/` after first-time setup; `/app/` remains a convenient Django shell mount when a local build exists. Production behavior is not the focus of the current phase.

## Deferred production integration

The current local build and `/app/` integration may be used for smoke checks. Docker and production React build integration are explicitly deferred.

First-time setup, login/logout and session-auth screens, Reader Client authorization, DRF `/api-auth/`, and the Django `/admin/` service hatch remain Django-rendered. Dashboard, library/catalog, books, groups, shelves, users and password flows, imports, and Product UI server settings are React scope.

## Server boundary

`web/react/packages/spl-api` is the first-party, framework-light TypeScript server communication package. It owns `fetch`, credentials, JSON parsing, structured error normalization, pagination types, server response mapping, and domain calls. React routes, components, and hooks consume its stable app-facing objects; they do not scatter raw `fetch()` calls or API URLs.

The Product UI uses the existing REST/JSON endpoints under `/api/v1/`. Do not add GraphQL or a generated API client.
