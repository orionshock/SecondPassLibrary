import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from ebooklib import epub
from django.core.files import File

from .models import Author, Book, BookFile, BookMetadata


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
    )
    if authors:
        book.authors.set(authors)

    # Create BookMetadata if applicable
    if any(
        metadata.get(key) for key in ["publisher", "language", "published_date", "isbn"]
    ):
        BookMetadata.objects.create(
            book=book,
            publisher=metadata.get("publisher", ""),
            language=metadata.get("language", ""),
            published_date=metadata.get("published_date"),
            isbn=metadata.get("isbn", ""),
        )

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
