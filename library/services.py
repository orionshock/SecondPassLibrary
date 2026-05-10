import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import re
import uuid
import zipfile
from typing import Optional, Any, cast
import shutil

from ebooklib import epub
from django.conf import settings
from django.core.files import File
from django.core.files.uploadedfile import UploadedFile

from .models import Author, Book, BookFile
from .models import BookIdentifier
from .models import ImportJob, ImportJobItem
from .group_services import ensure_book_public_assignment


class ImportStatus(str, Enum):
    IMPORTED = "imported"
    DUPLICATE = "duplicate"
    FAILED = "failed"


@dataclass
class ImportResult:
    status: ImportStatus
    book_file: Optional[BookFile] = None
    book: Optional[Book] = None
    message: str = ""
    warnings: list[str] = field(default_factory=list)
    checksum: Optional[str] = None


_FILENAME_SAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9 .,_()\\-]+")
_FILENAME_SPACES_RE = re.compile(r"\\s+")


def _sanitize_filename_component(value: str) -> str:
    value = (value or "").strip()
    value = _FILENAME_SAFE_CHARS_RE.sub("_", value)
    value = _FILENAME_SPACES_RE.sub(" ", value).strip()
    value = value.strip(" .")
    return value or "Unknown"


def generate_epub_download_filename(*, book: Book) -> str:
    """
    Generate a human-readable, safe filename for downloading an EPUB.

    Examples:
      - "<Author> - <Title>.epub"
      - "<Author> - <Series> <series_index> - <Title>.epub"
    """
    author = (
        book.authors.order_by("name").values_list("name", flat=True).first()
        or "Unknown Author"
    )
    parts: list[str] = [_sanitize_filename_component(author)]

    if book.series is not None:
        series_name = _sanitize_filename_component(book.series.name)
        if book.series_index is not None:
            parts.append(f"{series_name} {book.series_index}")
        else:
            parts.append(series_name)

    parts.append(_sanitize_filename_component(book.title))
    filename = " - ".join(parts)
    return f"{filename}.epub"


def import_epub(file_path):
    """
    Import a single EPUB file from the filesystem.

    Args:
        file_path (str): Path to the EPUB file.

    Returns:
        ImportResult: Explicit result of the import.

    Raises:
        ValueError: If file doesn't exist, not .epub, or other issues.
    """
    path = Path(file_path)

    # Verify file exists
    if not path.exists():
        raise ValueError(f"File does not exist: {file_path}")

    # Verify .epub extension
    if path.suffix.lower() != ".epub":
        raise ValueError(f"File must have .epub extension: {file_path}")

    # Calculate SHA-256 checksum and get file size
    with open(path, "rb") as f:
        content = f.read()
        checksum = hashlib.sha256(content).hexdigest()
        file_size = len(content)

    # Check if BookFile with this checksum already exists
    existing = BookFile.objects.filter(checksum=checksum).first()
    if existing:
        return ImportResult(
            status=ImportStatus.DUPLICATE,
            book_file=existing,
            book=existing.book,
            checksum=checksum,
            message="EPUB already exists.",
        )

    # Parse EPUB metadata
    book_epub = epub.read_epub(str(path))
    metadata = _extract_metadata(book_epub)

    # Create or reuse Author records
    authors = []
    for author_name in metadata.get("authors", []):
        author, _ = Author.objects.get_or_create(name=author_name.strip())
        authors.append(author)

    # Create Book record
    isbn = metadata.get("isbn") or ""
    book = Book.objects.create(
        title=metadata.get("title") or path.stem,  # fallback to filename stem
        subtitle=metadata.get("subtitle", ""),
        summary=metadata.get("summary", ""),
        publisher=metadata.get("publisher", ""),
        language=metadata.get("language", ""),
        published_date=metadata.get("published_date"),
        isbn=isbn,
        subjects=metadata.get("subjects") or [],
    )
    if authors:
        book.authors.set(authors)

    ensure_book_public_assignment(book=book, added_by=None)

    identifiers: list[dict[str, Any]] = metadata.get("identifiers") or []
    _create_book_identifiers(book=book, identifiers=identifiers)

    # Create BookFile record
    with open(path, "rb") as f:
        # One-to-one invariant: a Book has at most one stored EPUB BookFile.
        # Import creates a new Book, but keep the invariant explicit.
        try:
            _existing_file = cast(Any, book).file
        except BookFile.DoesNotExist:
            _existing_file = None
        if _existing_file is not None:
            raise ValueError(
                "Book already has a file; refusing to create a second BookFile."
            )
        book_file = BookFile.objects.create(
            book=book,
            file=File(
                f, name=f"{checksum}.epub"
            ),  # Name doesn't matter, upload_to uses checksum
            format=BookFile.FORMAT_EPUB,
            checksum=checksum,
            file_size=file_size,
            source_filename=path.name,
        )

    return ImportResult(
        status=ImportStatus.IMPORTED,
        book_file=book_file,
        book=book,
        checksum=checksum,
        message="Successfully imported EPUB.",
    )


def _clean_str(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text


def _normalize_language(value: str) -> str:
    # Conservative normalization only.
    return value.strip().lower()


def _dedupe_nonblank(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        v = _clean_str(raw)
        if not v:
            continue
        key = v.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out


_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _looks_like_doi(value: str) -> bool:
    v = value.strip()
    if v.lower().startswith("doi:"):
        v = v[4:].strip()
    return v.startswith("10.") and "/" in v


def _parse_isbn(value: str) -> tuple[str, str] | None:
    """
    Return (scheme, normalized_value) if value looks like ISBN-10/ISBN-13.

    Normalization removes spaces/hyphens and uppercases X for ISBN-10 check digit.
    """
    raw = value.strip()
    if not raw:
        return None

    # Strip common prefixes.
    lowered = raw.lower()
    if lowered.startswith("urn:isbn:"):
        raw = raw.split(":", 2)[-1]
    if lowered.startswith("isbn:"):
        raw = raw.split(":", 1)[-1]

    cleaned = re.sub(r"[^0-9xX]", "", raw)
    if len(cleaned) == 13 and cleaned.isdigit():
        return (BookIdentifier.SCHEME_ISBN_13, cleaned)
    if len(cleaned) == 10 and re.fullmatch(r"[0-9]{9}[0-9xX]", cleaned):
        return (BookIdentifier.SCHEME_ISBN_10, cleaned.upper())
    return None


def _identifier_scheme_for(*, value: str, attrs: dict[str, Any]) -> str:
    v = value.strip()
    v_lower = v.lower()

    isbn = _parse_isbn(v)
    if isbn is not None:
        return isbn[0]

    if _looks_like_doi(v):
        return BookIdentifier.SCHEME_DOI

    if v_lower.startswith(("http://", "https://", "urn:")):
        if v_lower.startswith("urn:uuid:"):
            return BookIdentifier.SCHEME_UUID
        return BookIdentifier.SCHEME_URI

    if _UUID_RE.match(v):
        return BookIdentifier.SCHEME_UUID

    # ASIN only when hinted.
    hinted = any(
        "asin" in str(attrs.get(k, "")).lower() for k in ("scheme", "type", "id")
    ) or v_lower.startswith(("asin:", "urn:asin:"))
    if hinted and re.fullmatch(r"[A-Z0-9]{10}", v.upper()):
        return BookIdentifier.SCHEME_ASIN

    return BookIdentifier.SCHEME_OTHER


def _normalize_identifier_value(*, scheme: str, value: str) -> str:
    v = value.strip()
    if scheme in {BookIdentifier.SCHEME_ISBN_10, BookIdentifier.SCHEME_ISBN_13}:
        parsed = _parse_isbn(v)
        if parsed is not None:
            return parsed[1]
    if scheme == BookIdentifier.SCHEME_DOI and v.lower().startswith("doi:"):
        return v[4:].strip()
    if scheme == BookIdentifier.SCHEME_ASIN and v.lower().startswith("asin:"):
        return v.split(":", 1)[-1].strip().upper()
    return v


def _extract_identifiers(book_epub) -> list[dict[str, Any]]:
    identifiers: list[dict[str, Any]] = []
    raw_identifiers = book_epub.get_metadata("DC", "identifier") or []
    for raw_value, raw_attrs in raw_identifiers:
        value = _clean_str(raw_value)
        if not value:
            continue
        attrs = raw_attrs or {}
        scheme = _identifier_scheme_for(value=value, attrs=attrs)
        normalized_value = _normalize_identifier_value(scheme=scheme, value=value)
        if not normalized_value:
            continue
        identifiers.append(
            {
                "scheme": scheme,
                "value": normalized_value,
                "source": "epub",
                "is_primary": False,
            }
        )

    # Mark a primary identifier if we can (prefer ISBN-13, then ISBN-10, else first).
    primary_index: int | None = None
    for idx, ident in enumerate(identifiers):
        if ident["scheme"] == BookIdentifier.SCHEME_ISBN_13:
            primary_index = idx
            break
    if primary_index is None:
        for idx, ident in enumerate(identifiers):
            if ident["scheme"] == BookIdentifier.SCHEME_ISBN_10:
                primary_index = idx
                break
    if primary_index is None and identifiers:
        primary_index = 0
    if primary_index is not None:
        identifiers[primary_index]["is_primary"] = True

    # Dedupe (scheme,value) preserving order.
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for ident in identifiers:
        key = (ident["scheme"], ident["value"].lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(ident)
    return out


def _best_isbn_from_identifiers(identifiers: list[dict[str, Any]]) -> str:
    isbn13 = next(
        (i["value"] for i in identifiers if i["scheme"] == BookIdentifier.SCHEME_ISBN_13),
        "",
    )
    if isbn13:
        return isbn13
    isbn10 = next(
        (i["value"] for i in identifiers if i["scheme"] == BookIdentifier.SCHEME_ISBN_10),
        "",
    )
    return isbn10 or ""


def _create_book_identifiers(*, book: Book, identifiers: list[dict[str, Any]]) -> None:
    for ident in identifiers:
        scheme = _clean_str(ident.get("scheme"))
        value = _clean_str(ident.get("value"))
        if not scheme or not value:
            continue
        source = _clean_str(ident.get("source", ""))
        is_primary = bool(ident.get("is_primary", False))
        BookIdentifier.objects.get_or_create(
            book=book,
            scheme=scheme,
            value=value,
            defaults={"source": source, "is_primary": is_primary},
        )

    # Ensure the primary flag is consistent if multiple were marked.
    primaries = list(BookIdentifier.objects.filter(book=book, is_primary=True).order_by("created_at"))
    if len(primaries) > 1:
        for extra in primaries[1:]:
            extra.is_primary = False
            extra.save(update_fields=["is_primary", "updated_at"])


def _imports_dir() -> Path:
    return Path(getattr(settings, "IMPORTS_DIR", getattr(settings, "USERDATA_DIR")))  # type: ignore[arg-type]


def _stage_uploaded_file(
    *, uploaded_file: UploadedFile, job_id: uuid.UUID, source_type: str
) -> tuple[str, Path]:
    imports_dir = _imports_dir()
    job_dir = imports_dir / "jobs" / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)

    extension = ".zip" if source_type == ImportJob.SOURCE_ZIP else ".epub"
    staged_name = f"{uuid.uuid4().hex}{extension}"
    staged_path = job_dir / staged_name

    with staged_path.open("wb") as out:
        for chunk in uploaded_file.chunks():
            out.write(chunk)

    staged_rel = str(Path("jobs") / str(job_id) / staged_name)
    return staged_rel, staged_path


def create_import_job_from_upload(*, user, uploaded_file: UploadedFile) -> ImportJob:
    """
    Create an ImportJob and stage the uploaded file under userdata/imports.

    This does not process the job; call process_import_job(job=...) for that.
    """
    name = (uploaded_file.name or "").strip()
    lower = name.lower()
    if lower.endswith(".epub"):
        source_type = ImportJob.SOURCE_EPUB
    elif lower.endswith(".zip"):
        source_type = ImportJob.SOURCE_ZIP
    else:
        raise ValueError("Upload must be a .epub or .zip file.")

    job = ImportJob.objects.create(
        user=user,
        status=ImportJob.STATUS_PENDING,
        source_type=source_type,
        source_filename=name,
    )
    staged_rel, _staged_path = _stage_uploaded_file(
        uploaded_file=uploaded_file, job_id=job.id, source_type=source_type
    )
    job.staged_path = staged_rel
    job.save(update_fields=["staged_path", "updated_at"])
    return job


def _safe_zip_epub_members(zip_file: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members: list[zipfile.ZipInfo] = []
    for info in zip_file.infolist():
        if info.is_dir():
            continue
        name = info.filename
        # Prevent path traversal or absolute paths
        if not name or name.startswith(("/", "\\")) or ":" in name:
            continue
        normalized = Path(name)
        if any(part in {"..", ""} for part in normalized.parts):
            continue
        if normalized.suffix.lower() != ".epub":
            continue
        members.append(info)
    return members


def process_import_job(*, job: ImportJob) -> ImportJob:
    """
    Process an ImportJob synchronously.

    Keeps business logic in services so it can later be called from a task runner.
    """
    if job.status not in {ImportJob.STATUS_PENDING, ImportJob.STATUS_FAILED}:
        return job

    staged_rel = (job.staged_path or "").strip()
    if not staged_rel:
        job.status = ImportJob.STATUS_FAILED
        job.message = "Missing staged upload."
        job.save(update_fields=["status", "message", "updated_at"])
        return job

    imports_dir = _imports_dir()
    staged_path = imports_dir / staged_rel
    if not staged_path.exists():
        job.status = ImportJob.STATUS_FAILED
        job.message = "Staged upload missing on disk."
        job.save(update_fields=["status", "message", "updated_at"])
        return job

    job.status = ImportJob.STATUS_PROCESSING
    job.message = ""
    job.total_found = 0
    job.imported_count = 0
    job.duplicate_count = 0
    job.failed_count = 0
    job.save(
        update_fields=[
            "status",
            "message",
            "total_found",
            "imported_count",
            "duplicate_count",
            "failed_count",
            "updated_at",
        ]
    )

    extracted_dir: Path | None = None
    try:
        if job.source_type == ImportJob.SOURCE_EPUB:
            job.total_found = 1
            result = import_epub(str(staged_path))
            item_status = (
                ImportJobItem.STATUS_IMPORTED
                if result.status == ImportStatus.IMPORTED
                else ImportJobItem.STATUS_DUPLICATE
                if result.status == ImportStatus.DUPLICATE
                else ImportJobItem.STATUS_FAILED
            )
            ImportJobItem.objects.create(
                job=job,
                status=item_status,
                source_name=job.source_filename or "",
                book=result.book,
                book_file=result.book_file,
                message=result.message or "",
            )
        else:
            extracted_dir = imports_dir / "jobs" / str(job.id) / "extracted"
            extracted_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(staged_path, "r") as zf:
                members = _safe_zip_epub_members(zf)
                job.total_found = len(members)
                job.save(update_fields=["total_found", "updated_at"])
                for info in members:
                    source_name = info.filename
                    try:
                        extracted_name = f"{uuid.uuid4().hex}.epub"
                        extracted_path = extracted_dir / extracted_name
                        with zf.open(info, "r") as src, extracted_path.open(
                            "wb"
                        ) as dst:
                            shutil.copyfileobj(src, dst)
                        result = import_epub(str(extracted_path))
                        item_status = (
                            ImportJobItem.STATUS_IMPORTED
                            if result.status == ImportStatus.IMPORTED
                            else ImportJobItem.STATUS_DUPLICATE
                            if result.status == ImportStatus.DUPLICATE
                            else ImportJobItem.STATUS_FAILED
                        )
                        ImportJobItem.objects.create(
                            job=job,
                            status=item_status,
                            source_name=source_name,
                            book=result.book,
                            book_file=result.book_file,
                            message=result.message or "",
                        )
                    except Exception as e:
                        ImportJobItem.objects.create(
                            job=job,
                            status=ImportJobItem.STATUS_FAILED,
                            source_name=source_name,
                            message=f"Failed to import EPUB: {e}",
                        )
                        continue

        # Recompute counts from items (authoritative)
        job.imported_count = ImportJobItem.objects.filter(
            job=job, status=ImportJobItem.STATUS_IMPORTED
        ).count()
        job.duplicate_count = ImportJobItem.objects.filter(
            job=job, status=ImportJobItem.STATUS_DUPLICATE
        ).count()
        job.failed_count = ImportJobItem.objects.filter(
            job=job, status=ImportJobItem.STATUS_FAILED
        ).count()
        job.status = (
            ImportJob.STATUS_COMPLETED
            if job.failed_count == 0
            else ImportJob.STATUS_FAILED
        )
        if job.status == ImportJob.STATUS_COMPLETED:
            job.message = "Import completed."
        else:
            job.message = "Import completed with failures."
        job.save(
            update_fields=[
                "status",
                "message",
                "imported_count",
                "duplicate_count",
                "failed_count",
                "updated_at",
            ]
        )
        return job
    finally:
        # Cleanup extracted temp files and staged upload once processed.
        if extracted_dir is not None and extracted_dir.exists():
            for child in extracted_dir.iterdir():
                if child.is_file():
                    child.unlink(missing_ok=True)
            try:
                extracted_dir.rmdir()
            except OSError:
                pass
        staged_path.unlink(missing_ok=True)


def _extract_metadata(book_epub):
    """
    Extract and lightly clean metadata from EPUB.

    Returns:
        dict: Metadata dictionary.
    """
    metadata: dict[str, Any] = {}

    # Title
    titles = book_epub.get_metadata("DC", "title") or []
    title_values = _dedupe_nonblank([t[0] for t in titles if t and t[0]])
    if title_values:
        metadata["title"] = title_values[0]
        if len(title_values) > 1:
            subtitle = title_values[1]
            if subtitle and subtitle != title_values[0]:
                metadata["subtitle"] = subtitle

    # Authors
    creators = book_epub.get_metadata("DC", "creator") or []
    metadata["authors"] = _dedupe_nonblank([c[0] for c in creators if c and c[0]])

    # Language
    language = book_epub.get_metadata("DC", "language") or []
    if language and language[0] and language[0][0]:
        lang = _clean_str(language[0][0])
        if lang:
            metadata["language"] = _normalize_language(lang)

    # Publisher
    publisher = book_epub.get_metadata("DC", "publisher") or []
    if publisher and publisher[0] and publisher[0][0]:
        pub = _clean_str(publisher[0][0])
        if pub:
            metadata["publisher"] = pub

    # Description -> summary (only used if Book.summary is empty on create)
    description = book_epub.get_metadata("DC", "description") or []
    if description and description[0] and description[0][0]:
        desc = _clean_str(description[0][0])
        if desc:
            metadata["summary"] = desc

    # Subjects
    subjects = book_epub.get_metadata("DC", "subject") or []
    metadata["subjects"] = _dedupe_nonblank([s[0] for s in subjects if s and s[0]])

    # Publication date
    date = book_epub.get_metadata("DC", "date") or []
    if date and date[0] and date[0][0]:
        raw_date = _clean_str(date[0][0])
        if len(raw_date) >= 10 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date[:10]):
            metadata["published_date"] = raw_date[:10]

    identifiers = _extract_identifiers(book_epub)
    metadata["identifiers"] = identifiers
    metadata["isbn"] = _best_isbn_from_identifiers(identifiers)

    return metadata
