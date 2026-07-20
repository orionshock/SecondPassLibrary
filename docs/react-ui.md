# React Product UI

The new Product UI lives in `web/react`. The existing server-rendered Django UI remains functional at its original routes and is also mounted under `/legacy` during the migration. Its templates and static files remain in `web`; a physical move to `web/legacy` is deferred.

The legacy mount applies only to Product UI routes. REST APIs remain under `/api/v1/`, and `/static/`, `/media/`, `/admin/`, and `/api-auth/` are not duplicated below `/legacy`. Primary navigation and server-side Product UI redirects preserve the legacy prefix. Some page-specific templates and JavaScript still construct unprefixed Product UI links; converting those links should be handled in focused page-migration slices rather than as a broad routing rewrite.

## Development

Run Django on port 8000 and the Product UI Vite server on port 5174. Port 5173 remains available for the standalone Reading Client. From `web/react`, run `npm install` and `npm run dev`. Vite proxies `/api`, `/media`, `/admin`, and `/api-auth` to Django, so the app uses Django session authentication through same-origin-style URLs.

After `npm run build`, Django serves the shell at `/app/`; React Router deep links below `/app/` return the same shell. A missing build returns HTTP 503 with a build instruction. `/` remains the existing Django Product UI during this transition.

## Production target

The frontend build is `npm run build`. Vite writes hashed assets under the ignored `web/react/dist/`, using `/static/react/` asset URLs. Django staticfiles collects that build under the `react` prefix and WhiteNoise serves it. Production remains a single Django/Uvicorn container with no Node server or separate frontend container. Docker build integration is a later slice.

The local production helper runs the frontend build before Django deployment checks and static collection, then runs Uvicorn without a Node process. The shell is available at `/app/`; the existing Product UI remains at `/` until explicit cutover.

First-time setup, login/logout and session-auth screens, DRF `/api-auth/`, and the Django `/admin/` service hatch remain Django-rendered surfaces. The later React replacement scope includes the main library and management pages, self-service password change, manager password change/reset flows, imports, and Product UI server settings.

## Server boundary

`web/react/packages/spl-api` is the first-party, framework-light TypeScript server communication package. It owns `fetch`, credentials, JSON parsing, structured error normalization, pagination types, server response mapping, and domain calls. React routes, components, and hooks consume its stable app-facing objects; they do not scatter raw `fetch()` calls or API URLs.

The Product UI uses the existing REST/JSON endpoints under `/api/v1/`. Do not add GraphQL or a generated API client.
