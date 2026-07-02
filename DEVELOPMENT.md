# Developer documentation

Developer documentation has moved under `docs/`:

- `docs/development.md` (local setup/workflow)
- `docs/api.md` (API index)
- `docs/architecture.md` (project structure and rules)
- `docs/permissions.md` (roles/groups/curation rules)
- `docs/imports.md` (import workflow)
- `docs/reading.md` (reading behavior + locator conventions)
- `docs/metadata.md` (metadata/identifiers philosophy)

Common commands:

```powershell
.\scripts\start-dev.ps1
python manage.py check
python manage.py test
```

The startup script opts into Django debug mode and applies migrations before
`runserver`. The first-run setup
wizard creates the initial Owner account after the schema exists.
Production static output is generated under `var/static/`; durable app data
lives under `userdata/`.
