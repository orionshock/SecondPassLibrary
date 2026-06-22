# Production startup

Second Pass Library's first-run setup works in development and production. The
database schema must exist before the web process accepts requests; the setup
wizard does not create tables from request handling.

## Single-instance POSIX startup

Install the runtime dependencies, configure the environment, and run:

```sh
sh scripts/start-production.sh
```

The script fails fast and performs these steps in order:

1. `python manage.py migrate --noinput`
2. `python manage.py collectstatic --noinput`
3. Gunicorn serving `secondpass.wsgi:application`

Environment variables:

- `PYTHON`: Python executable, default `python`
- `DJANGO_SETTINGS_MODULE`: optional Django settings module override; inherited
  by migration, static collection, and Gunicorn processes
- `BIND`: Gunicorn bind address, default `0.0.0.0:8000`
- `WEB_CONCURRENCY`: Gunicorn worker count, default `2`
- `GUNICORN_CONFIG`: optional Gunicorn configuration file

WhiteNoise serves only application assets under `/static/` from the collected
`STATIC_ROOT`: Product UI CSS, JavaScript, icons, favicon assets, and other
packaged static files. WhiteNoise runs inside the Django/Gunicorn application,
so a separate static-file web server is not required for these assets.
Production (`DEBUG=False`) uses compressed manifest storage for hashed,
cacheable filenames. Development keeps Django's normal `runserver` static-file
behavior and does not require `collectstatic`.

WhiteNoise does not serve `MEDIA_ROOT` or any user/library data. Books, EPUB
files, covers, imports, exports, or marginalia continue to use their existing
storage and authenticated Django/API paths. Do not point WhiteNoise at
`userdata/media/`, `userdata/imports/`, or any directory containing protected
content.

After the first startup, visit `/`. With a migrated database and no active
Django superuser, `/`, Product UI routes, and login direct to `/setup/`.
Complete setup to save the server name and optional description, configure the
Public group's display name and description, save the advanced-groups UI
preference, and create the first active staff/superuser, Manager profile, and
Public membership. The defaults are `Second Pass Library`, a blank server
description, `Common Room`, `Main Public Library Room for everyone`, and
advanced groups disabled. Common Room is the shared public library space
managed by librarians and managers. Advanced groups expose separate
curator-managed rooms without changing the underlying permission model.
Subsequent starts use normal login because the bootstrap Owner already exists.

`seed_dev_users` is an optional local development/demo command. It is not part
of production startup and is not required for normal first-run setup.

## Raw commands

Raw `python manage.py runserver` and raw `gunicorn` remain usable only after
migrations have been applied manually. The recommended startup path is the
appropriate wrapper script so migrations finish before the web server starts.
