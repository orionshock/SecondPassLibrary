# SecondPassLibrary

Your books, your notes, your reading history.

## Data Storage

This application stores all runtime and user-generated data in the `userdata/` directory:

- `userdata/db/`: SQLite database files
- `userdata/media/books/`: EPUB files stored content-addressed (e.g., `ab/cd/abcdef...epub`)
- `userdata/static/`: Collected static files
- `userdata/logs/`: Application logs
- `userdata/imports/`: Temporary import files

### Important Notes

- The `userdata/` directory is intentionally ignored by Git and should be backed up separately.
- EPUB files are stored using their SHA-256 checksum for deduplication and content addressing.
- Human-readable filenames come from metadata, not stored filenames.
- The application automatically creates required subdirectories on startup.

## Development Setup

1. Clone the repository
2. Create a virtual environment: `python -m venv .venv`
3. Activate (PowerShell): `.\.venv\Scripts\Activate.ps1`
4. Install dependencies: `pip install -r requirements.txt`
5. Run migrations: `python manage.py migrate`
6. Create superuser: `python manage.py createsuperuser`
7. Run server: `python manage.py runserver`

See `docs/development.md` for the full development workflow (including checks/tests).

## Importing EPUBs

Imports are intended to be API-mediated (product direction):

- `POST /api/v1/library/imports/` (multipart field name: `file`)

See `docs/imports.md` for details and supported upload types.

The management command remains available as a dev/admin utility (host-side):

```bash
python manage.py import_epub "path/to/book.epub"
```

Also see:
- `docs/imports.md` (API-mediated imports)
- `docs/api.md` (API index)
