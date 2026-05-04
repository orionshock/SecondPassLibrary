import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import re
import uuid
import zipfile
from typing import Optional
import shutil

from ebooklib import epub
from django.conf import settings
from django.core.files import File
from django.core.files.uploadedfile import UploadedFile

from .models import Author, Book, BookFile
from .models import ImportJob, ImportJobItem


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
    book = Book.objects.create(
        title=metadata.get(
            "title", path.stem
        ),  # Use EPUB title or filename as fallback
        summary="",  # Leave empty for user to edit
        publisher=metadata.get("publisher", ""),
        language=metadata.get("language", ""),
        published_date=metadata.get("published_date"),
        isbn=metadata.get("isbn", ""),
        subjects=metadata.get("subjects") or [],
    )
    if authors:
        book.authors.set(authors)

    # Create BookFile record
    with open(path, "rb") as f:
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
    Extract basic metadata from EPUB.

    Returns:
        dict: Metadata dictionary.
    """
    metadata = {}

    # Title
    title = book_epub.get_metadata("DC", "title")
    if title:
        metadata["title"] = title[0][0]

    # Authors
    authors = book_epub.get_metadata("DC", "creator")
    if authors:
        metadata["authors"] = [author[0] for author in authors]

    # Language
    language = book_epub.get_metadata("DC", "language")
    if language:
        metadata["language"] = language[0][0]

    # Publisher
    publisher = book_epub.get_metadata("DC", "publisher")
    if publisher:
        metadata["publisher"] = publisher[0][0]

    # Subjects
    subjects = book_epub.get_metadata("DC", "subject")
    if subjects:
        metadata["subjects"] = [subject[0] for subject in subjects if subject and subject[0]]

    # Publication date
    date = book_epub.get_metadata("DC", "date")
    if date:
        # Assume YYYY-MM-DD format
        metadata["published_date"] = date[0][0][:10] if len(date[0][0]) >= 10 else None

    # ISBN (if available in identifier)
    identifiers = book_epub.get_metadata("DC", "identifier")
    for identifier in identifiers:
        if "isbn" in identifier[0].lower():
            metadata["isbn"] = identifier[0]
            break

    return metadata
