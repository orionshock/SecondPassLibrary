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

Static files collected under `STATIC_ROOT` and media under `MEDIA_ROOT` must be
served by the deployment's web server, reverse proxy, or static/media layer.
Gunicorn does not serve them.

After the first startup, visit `/`. With a migrated database and no active
Django superuser, `/`, Product UI routes, and login direct to `/setup/`.
Complete setup to create the first active staff/superuser, Manager profile, and
Public membership. Subsequent starts use normal login because the bootstrap
Owner already exists.

`seed_dev_users` is an optional local development/demo command. It is not part
of production startup and is not required for normal first-run setup.

## Raw commands

Raw `python manage.py runserver` and raw `gunicorn` remain usable only after
migrations have been applied manually. The recommended startup path is the
appropriate wrapper script so migrations finish before the web server starts.
