# React Product UI

The new Product UI lives in `web/react`. The existing server-rendered Django UI remains functional during the migration; moving it under `/legacy` is a later, separate slice.

## Development

Run Django on port 8000 and the Product UI Vite server on port 5174. Port 5173 remains available for the standalone Reading Client. From `web/react`, run `npm install` and `npm run dev`. Vite proxies `/api`, `/media`, `/admin`, and `/api-auth` to Django, so the app uses Django session authentication through same-origin-style URLs.

The first scaffold is development-only and does not claim a Django route. Production shell integration is deferred.

## Production target

The frontend build is `npm run build`. Django will serve the React shell, and WhiteNoise will serve the built static assets. Production remains a single Django/Uvicorn container with no Node server or separate frontend container. Docker build integration is a later slice.

## Server boundary

`web/react/packages/spl-api` is the first-party, framework-light TypeScript server communication package. It owns `fetch`, credentials, JSON parsing, structured error normalization, pagination types, server response mapping, and domain calls. React routes, components, and hooks consume its stable app-facing objects; they do not scatter raw `fetch()` calls or API URLs.

The Product UI uses the existing REST/JSON endpoints under `/api/v1/`. Do not add GraphQL or a generated API client.
