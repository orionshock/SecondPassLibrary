from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from django.conf import settings
from jsonschema import Draft202012Validator

from core import policies
from library.models import Book, BookIdentifier


class MarginaliaImportPreviewError(ValueError):
    def __init__(self, message: str, errors: list[dict[str, str]] | None = None):
        super().__init__(message)
        self.errors = errors or [{"path": "$", "message": message}]


def parse_marginalia_json(raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        raise MarginaliaImportPreviewError("Upload must be UTF-8 JSON.") from None
    except json.JSONDecodeError as exc:
        raise MarginaliaImportPreviewError(
            "Upload must be valid JSON.",
            [{"path": f"$.line:{exc.lineno}:column:{exc.colno}", "message": exc.msg}],
        ) from None
    if not isinstance(payload, dict):
        raise MarginaliaImportPreviewError("Upload must be a JSON object.")
    return payload


def validate_marginalia_export(payload: dict[str, Any]) -> None:
    schema = _load_schema()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.absolute_path))
    if errors:
        raise MarginaliaImportPreviewError(
            "Upload does not match the SPL marginalia export schema.",
            [{"path": _json_path(err.absolute_path), "message": err.message} for err in errors[:20]],
        )


def preview_marginalia_import(*, user, payload: dict[str, Any]) -> dict[str, Any]:
    validate_marginalia_export(payload)
    books = payload.get("books") or []
    book_summaries = [_book_summary(user=user, exported=book) for book in books]

    total_sessions = sum(book["session_count"] for book in book_summaries)
    total_annotations = sum(book["annotation_count"] for book in book_summaries)
    return {
        "valid": True,
        "type": payload.get("type"),
        "schema_version": payload.get("schema_version"),
        "profile": payload.get("profile"),
        "generated_at": payload.get("generated_at"),
        "scope": payload.get("scope") or {},
        "summary": {
            "books": len(books),
            "sessions": total_sessions,
            "annotations": total_annotations,
        },
        "books": book_summaries,
        "warnings": [],
        "can_apply": False,
    }


def _load_schema() -> dict[str, Any]:
    path = Path(settings.BASE_DIR) / "docs" / "specs" / "marginalia-export.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _json_path(parts) -> str:
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}"
    return path


def _book_summary(*, user, exported: dict[str, Any]) -> dict[str, Any]:
    sessions = exported.get("sessions") or []
    annotation_counts = _annotation_counts(sessions)
    return {
        "title": exported.get("title") or "",
        "authors": exported.get("authors") or [],
        "source": exported.get("source") or "",
        "file_hash": exported.get("file_hash") or "",
        "isbn": exported.get("isbn") or "",
        "session_count": len(sessions),
        **annotation_counts,
        "match": _match_book(user=user, exported=exported),
    }


def _annotation_counts(sessions: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "annotation_count": 0,
        "bookmark_count": 0,
        "highlight_count": 0,
        "commented_highlight_count": 0,
    }
    for session in sessions:
        for annotation in session.get("annotations") or []:
            motivations = set(annotation.get("motivation") or [])
            bodies = annotation.get("body") or []
            has_comment = "commenting" in motivations or any(
                body.get("purpose") == "commenting" for body in bodies if isinstance(body, dict)
            )
            counts["annotation_count"] += 1
            if "bookmarking" in motivations and "highlighting" not in motivations:
                counts["bookmark_count"] += 1
            if "highlighting" in motivations:
                counts["highlight_count"] += 1
                if has_comment:
                    counts["commented_highlight_count"] += 1
    return counts


def _match_book(*, user, exported: dict[str, Any]) -> dict[str, str | None]:
    visible_books = [
        book
        for book in Book.objects.select_related("file")
        .prefetch_related("authors", "identifiers", "group_assignments__group__memberships")
        .all()
        if policies.can_view_book(user=user, book=book)
    ]

    file_hash = _hash_value(exported.get("file_hash") or exported.get("source") or "")
    if file_hash:
        for book in visible_books:
            checksum = getattr(getattr(book, "file", None), "checksum", "") or ""
            if checksum.lower() == file_hash:
                return _matched(book=book, method="file_hash")

    exported_isbn = _normalize_isbn(exported.get("isbn") or "")
    if exported_isbn:
        for book in visible_books:
            if _book_isbns(book) & {exported_isbn}:
                return _matched(book=book, method="isbn")

    title = _normalize_text(exported.get("title") or "")
    authors = {_normalize_text(author) for author in exported.get("authors") or [] if author}
    if title and authors:
        for book in visible_books:
            book_authors = {_normalize_text(author.name) for author in book.authors.all()}
            if _normalize_text(book.title) == title and bool(book_authors & authors):
                return _matched(book=book, method="title_author")

    return {"status": "unmatched", "method": None, "confidence": "none", "book_title": None}


def _matched(*, book: Book, method: str) -> dict[str, str]:
    return {
        "status": "matched",
        "method": method,
        "confidence": "exact",
        "book_title": book.title or "",
    }


def _hash_value(value: str) -> str:
    text = str(value or "").strip().lower()
    match = re.search(r"sha256:([0-9a-f]{64})", text)
    return match.group(1) if match else ""


def _normalize_isbn(value: str) -> str:
    return re.sub(r"[^0-9xX]", "", str(value or "")).upper()


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _book_isbns(book: Book) -> set[str]:
    values = {_normalize_isbn(book.isbn)}
    for identifier in book.identifiers.all():
        if identifier.scheme in {BookIdentifier.SCHEME_ISBN_10, BookIdentifier.SCHEME_ISBN_13}:
            values.add(_normalize_isbn(identifier.value))
    return {value for value in values if value}
