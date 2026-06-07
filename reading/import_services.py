from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils.dateparse import parse_datetime
from jsonschema import Draft202012Validator

from core import policies
from library.models import Book, BookIdentifier
from reading.models import ReadingSession


class MarginaliaImportError(ValueError):
    def __init__(self, message: str, errors: list[dict[str, str]] | None = None):
        super().__init__(message)
        self.errors = errors or [{"path": "$", "message": message}]


def read_uploaded_marginalia_json(uploaded) -> dict[str, Any]:
    if uploaded is None:
        raise MarginaliaImportError(
            "Upload a JSON file.",
            [{"path": "$.file", "message": "Upload a JSON file."}],
        )
    return parse_marginalia_json(uploaded.read())


def parse_marginalia_json(raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        raise MarginaliaImportError("Upload must be UTF-8 JSON.") from None
    except json.JSONDecodeError as exc:
        raise MarginaliaImportError(
            "Upload must be valid JSON.",
            [{"path": f"$.line:{exc.lineno}:column:{exc.colno}", "message": exc.msg}],
        ) from None
    if not isinstance(payload, dict):
        raise MarginaliaImportError("Upload must be a JSON object.")
    return payload


def validate_marginalia_export(payload: dict[str, Any]) -> None:
    schema = _load_schema()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.absolute_path))
    if errors:
        raise MarginaliaImportError(
            "Upload does not match the SPL marginalia export schema.",
            [{"path": _json_path(err.absolute_path), "message": err.message} for err in errors[:20]],
        )


def plan_marginalia_import(*, user, payload: dict[str, Any]) -> dict[str, Any]:
    validate_marginalia_export(payload)
    books = payload.get("books") or []
    book_plans = [_book_plan(user=user, exported=book) for book in books]
    book_summaries = [book["summary"] for book in book_plans]

    total_sessions = sum(book["session_count"] for book in book_summaries)
    total_annotations = sum(book["annotation_count"] for book in book_summaries)
    apply_plan = _apply_plan(book_summaries)
    warnings = _warnings(book_summaries, apply_plan)
    return {
        "summary": {
            "books": len(books),
            "sessions": total_sessions,
            "annotations": total_annotations,
        },
        "books": book_summaries,
        "book_plans": book_plans,
        "warnings": warnings,
        "can_apply": apply_plan["matched_books"] > 0,
        "apply_plan": apply_plan,
    }


def preview_marginalia_import(*, user, payload: dict[str, Any]) -> dict[str, Any]:
    plan = plan_marginalia_import(user=user, payload=payload)
    return {
        "valid": True,
        "type": payload.get("type"),
        "schema_version": payload.get("schema_version"),
        "profile": payload.get("profile"),
        "generated_at": payload.get("generated_at"),
        "scope": payload.get("scope") or {},
        "summary": plan["summary"],
        "books": plan["books"],
        "warnings": plan["warnings"],
        "can_apply": plan["can_apply"],
        "apply_plan": plan["apply_plan"],
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


def _book_plan(*, user, exported: dict[str, Any]) -> dict[str, Any]:
    sessions = exported.get("sessions") or []
    annotation_counts = _annotation_counts(sessions)
    local_book, match = match_exported_book(user=user, exported=exported)
    will_import = match["status"] == "matched"
    skipped_warning = (
        "No visible local book matched this export book. It will be skipped."
        if not will_import
        else ""
    )
    active_sessions = _active_session_count(sessions)
    duplicate_sessions = (
        _possible_duplicate_count(user=user, book=local_book, sessions=sessions)
        if local_book is not None
        else 0
    )
    summary = {
        "title": exported.get("title") or "",
        "authors": exported.get("authors") or [],
        "source": exported.get("source") or "",
        "file_hash": exported.get("file_hash") or "",
        "isbn": exported.get("isbn") or "",
        "session_count": len(sessions),
        **annotation_counts,
        "match": match,
        "will_import": will_import,
        "skip_reason": None if will_import else "unmatched_book",
        "warning": skipped_warning,
        "active_sessions_will_import_as_historical": active_sessions if will_import else 0,
        "possible_duplicate_sessions": duplicate_sessions,
    }
    return {"exported": exported, "local_book": local_book, "summary": summary}


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


def _apply_plan(book_summaries: list[dict[str, Any]]) -> dict[str, int]:
    plan = {
        "matched_books": 0,
        "skipped_books": 0,
        "sessions_to_create": 0,
        "annotations_to_create": 0,
        "bookmarks_to_create": 0,
        "highlights_to_create": 0,
        "commented_highlights_to_create": 0,
        "active_sessions_will_import_as_historical": 0,
        "possible_duplicate_sessions": 0,
    }
    for book in book_summaries:
        if book["will_import"]:
            plan["matched_books"] += 1
            plan["sessions_to_create"] += book["session_count"]
            plan["annotations_to_create"] += book["annotation_count"]
            plan["bookmarks_to_create"] += book["bookmark_count"]
            plan["highlights_to_create"] += book["highlight_count"]
            plan["commented_highlights_to_create"] += book["commented_highlight_count"]
            plan["active_sessions_will_import_as_historical"] += book[
                "active_sessions_will_import_as_historical"
            ]
            plan["possible_duplicate_sessions"] += book["possible_duplicate_sessions"]
        else:
            plan["skipped_books"] += 1
    return plan


def _warnings(book_summaries: list[dict[str, Any]], apply_plan: dict[str, int]) -> list[str]:
    warnings = [
        book["warning"]
        for book in book_summaries
        if book.get("warning")
    ]
    if apply_plan["active_sessions_will_import_as_historical"]:
        warnings.append("Active exported sessions will be imported as historical sessions, not active sessions.")
    if apply_plan["possible_duplicate_sessions"]:
        warnings.append("Possible duplicate sessions were found. They are warnings only and do not block preview.")
    return warnings


def match_exported_book(*, user, exported: dict[str, Any]) -> tuple[Book | None, dict[str, str | None]]:
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
                return book, _matched(book=book, method="file_hash")

    exported_isbn = _normalize_isbn(exported.get("isbn") or "")
    if exported_isbn:
        for book in visible_books:
            if _book_isbns(book) & {exported_isbn}:
                return book, _matched(book=book, method="isbn")

    title = _normalize_text(exported.get("title") or "")
    authors = {_normalize_text(author) for author in exported.get("authors") or [] if author}
    if title and authors:
        for book in visible_books:
            book_authors = {_normalize_text(author.name) for author in book.authors.all()}
            if _normalize_text(book.title) == title and bool(book_authors & authors):
                return book, _matched(book=book, method="title_author")

    return None, {"status": "unmatched", "method": None, "confidence": "none", "book_title": None}


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


def _active_session_count(sessions: list[dict[str, Any]]) -> int:
    return sum(1 for session in sessions if session.get("status") == ReadingSession.STATUS_ACTIVE)


def _possible_duplicate_count(*, user, book: Book, sessions: list[dict[str, Any]]) -> int:
    count = 0
    for session in sessions:
        started_at = parse_datetime(str(session.get("started_at") or ""))
        completed_at = parse_datetime(str(session.get("completed_at") or ""))
        if started_at is None:
            continue
        matches = ReadingSession.objects.filter(
            user=user,
            book=book,
            name=session.get("name") or "",
            started_at=started_at,
            completed_at=completed_at,
        )
        if matches.exists():
            count += 1
    return count
