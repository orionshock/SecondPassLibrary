from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils.dateparse import parse_datetime
from jsonschema import Draft202012Validator

from library import policies as library_policies
from library.models import Book
from reading.marginalia_profile import count_profile_annotations, profile_selectors
from reading.models import ReadingSession


MAX_MARGINALIA_IMPORT_BYTES = 25 * 1024 * 1024


class MarginaliaImportError(ValueError):
    def __init__(self, message: str, errors: list[dict[str, str]] | None = None):
        super().__init__(message)
        self.errors = errors or [{"path": "$", "message": message}]


def _format_import_size(byte_count: int) -> str:
    if byte_count >= 1024 * 1024 and byte_count % (1024 * 1024) == 0:
        return f"{byte_count // (1024 * 1024)} MiB"
    return f"{byte_count} bytes"


def _marginalia_limit_message() -> str:
    return f"Marginalia import JSON exceeds the {_format_import_size(MAX_MARGINALIA_IMPORT_BYTES)} limit."


def read_uploaded_marginalia_json(uploaded) -> dict[str, Any]:
    if uploaded is None:
        raise MarginaliaImportError(
            "Upload a JSON file.",
            [{"path": "$.file", "message": "Upload a JSON file."}],
        )
    size = getattr(uploaded, "size", None)
    if isinstance(size, int) and size > MAX_MARGINALIA_IMPORT_BYTES:
        message = _marginalia_limit_message()
        raise MarginaliaImportError(message, [{"path": "$.file", "message": message}])

    raw = uploaded.read(MAX_MARGINALIA_IMPORT_BYTES + 1)
    if len(raw) > MAX_MARGINALIA_IMPORT_BYTES:
        message = _marginalia_limit_message()
        raise MarginaliaImportError(message, [{"path": "$.file", "message": message}])
    return parse_marginalia_json(raw)


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
        "can_apply": apply_plan["sessions_to_create"] > 0,
        "apply_plan": apply_plan,
    }


def preview_marginalia_import(*, user, payload: dict[str, Any]) -> dict[str, Any]:
    plan = plan_marginalia_import(user=user, payload=payload)
    unmatched_books = sum(
        1 for book in plan["books"] if book["match"]["status"] == "unmatched"
    )
    unmatched_sessions = sum(
        1
        for book in plan["books"]
        for session in book["sessions"]
        if session.get("needs_reader")
    )
    unmatched_entries = unmatched_books + unmatched_sessions
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
        "unmatched_entries": unmatched_entries,
        "unmatched_books": unmatched_books,
        "unmatched_sessions": unmatched_sessions,
    }


def unmatched_marginalia_export(*, user, payload: dict[str, Any]) -> dict[str, Any]:
    plan = plan_marginalia_import(user=user, payload=payload)
    unmatched_books = []
    for book_plan in plan["book_plans"]:
        summary = book_plan["summary"]
        if summary["match"]["status"] == "unmatched":
            unmatched_books.append(book_plan["exported"])
            continue
        invalid_session_ids = {
            session["export_session_id"]
            for session in summary["sessions"]
            if session.get("needs_reader")
        }
        if invalid_session_ids:
            exported = deepcopy(book_plan["exported"])
            exported["sessions"] = [
                session
                for session in exported.get("sessions") or []
                if session.get("export_session_id") in invalid_session_ids
            ]
            unmatched_books.append(exported)
    return {
        "type": payload.get("type"),
        "schema_version": payload.get("schema_version"),
        "profile": payload.get("profile"),
        "generated_at": payload.get("generated_at"),
        "generator": payload.get("generator") or "Second Pass Library",
        "scope": {
            "type": "selected",
            "books": [
                {
                    "book": _exported_book_source(book),
                    "session_filter": "all",
                }
                for book in unmatched_books
            ],
        },
        "books": unmatched_books,
    }


def _load_schema() -> dict[str, Any]:
    path = Path(settings.BASE_DIR) / "docs" / "specs" / "marginalia-export.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _exported_book_source(book: dict[str, Any]) -> str:
    return (
        str(book.get("source") or "").strip()
        or str(book.get("file_hash") or "").strip()
        or str(book.get("title") or "").strip()
        or "unmatched"
    )


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
    annotation_counts = count_profile_annotations(sessions)
    local_book, match = match_exported_book(user=user, exported=exported)
    book_matched = match["status"] == "matched"
    skipped_warning = (
        "No visible local book matched this export book. It will be skipped."
        if not book_matched
        else ""
    )
    active_sessions = _active_session_count(sessions)
    session_summaries = [
        _session_summary(
            user=user,
            book=local_book,
            exported=session,
            book_matched=book_matched,
        )
        for session in sessions
    ]
    invalid_sessions = sum(1 for session in session_summaries if session.get("needs_reader"))
    duplicate_sessions = (
        _possible_duplicate_count(user=user, book=local_book, sessions=sessions)
        if local_book is not None
        else 0
    )
    will_import = any(session["will_import"] for session in session_summaries)
    summary = {
        "title": exported.get("title") or "",
        "authors": exported.get("authors") or [],
        "source": exported.get("source") or "",
        "file_hash": exported.get("file_hash") or "",
        "isbn": exported.get("isbn") or "",
        "session_count": len(sessions),
        **annotation_counts,
        "match": match,
        "cover_url": _cover_url(local_book) if local_book is not None else "",
        "will_import": will_import,
        "skip_reason": None if book_matched else "unmatched_book",
        "warning": skipped_warning or (
            "Some sessions have malformed locators and need Reader-assisted import."
            if invalid_sessions
            else ""
        ),
        "active_sessions_will_import_as_historical": active_sessions if book_matched else 0,
        "invalid_locator_sessions": invalid_sessions,
        "possible_duplicate_sessions": duplicate_sessions,
        "sessions": session_summaries,
    }
    return {"exported": exported, "local_book": local_book, "summary": summary}


def _session_summary(*, user, book: Book | None, exported: dict[str, Any], book_matched: bool) -> dict[str, Any]:
    counts = count_profile_annotations([exported])
    is_active = exported.get("status") == ReadingSession.STATUS_ACTIVE
    locator_warning = _locator_warning(exported) if book_matched else ""
    will_import = bool(book_matched and not locator_warning)
    duplicate = (
        _possible_duplicate_session(user=user, book=book, session=exported)
        if book is not None and will_import
        else False
    )
    return {
        "export_session_id": exported.get("export_session_id") or "",
        "name": exported.get("name") or "",
        "notes": exported.get("notes") or "",
        "status": exported.get("status") or "",
        "started_at": exported.get("started_at"),
        "completed_at": exported.get("completed_at"),
        **counts,
        "will_import": will_import,
        "needs_reader": bool(book_matched and locator_warning),
        "active_will_import_as_historical": bool(will_import and is_active),
        "possible_duplicate": duplicate,
        "warning": locator_warning or ("Possible duplicate session." if duplicate else ""),
    }


def _locator_warning(session: dict[str, Any]) -> str:
    values = []
    progress = session.get("progress") or {}
    current_location = progress.get("current_location") if isinstance(progress, dict) else {}
    if isinstance(current_location, dict):
        if current_location.get("cfi"):
            values.append(current_location.get("cfi"))
        selector = current_location.get("selector")
        if isinstance(selector, dict) and selector.get("type") == "FragmentSelector":
            values.append(selector.get("value"))

    for annotation in session.get("annotations") or []:
        target = annotation.get("target") or {}
        if isinstance(target, dict):
            for item in profile_selectors(target):
                if item.get("type") == "FragmentSelector":
                    values.append(item.get("value"))

    malformed = any(not _is_cfi_shaped(value) for value in values if value is not None)
    return "Malformed EPUB CFI locator. Needs Reader." if malformed else ""


def _is_cfi_shaped(value: object) -> bool:
    text = str(value or "").strip()
    return text.startswith("epubcfi(") and text.endswith(")") and bool(text[8:-1].strip())


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
        if book["match"]["status"] == "matched":
            valid_sessions = [
                session for session in book["sessions"] if session["will_import"]
            ]
            plan["matched_books"] += 1
            plan["sessions_to_create"] += len(valid_sessions)
            plan["annotations_to_create"] += sum(
                session["annotation_count"] for session in valid_sessions
            )
            plan["bookmarks_to_create"] += sum(
                session["bookmark_count"] for session in valid_sessions
            )
            plan["highlights_to_create"] += sum(
                session["highlight_count"] for session in valid_sessions
            )
            plan["commented_highlights_to_create"] += sum(
                session["commented_highlight_count"] for session in valid_sessions
            )
            plan["active_sessions_will_import_as_historical"] += sum(
                1 for session in valid_sessions if session["active_will_import_as_historical"]
            )
            plan["possible_duplicate_sessions"] += sum(
                1 for session in valid_sessions if session["possible_duplicate"]
            )
        else:
            plan["skipped_books"] += 1
    return plan


def _warnings(book_summaries: list[dict[str, Any]], apply_plan: dict[str, int]) -> list[str]:
    warnings = [
        book["warning"]
        for book in book_summaries
        if book.get("warning") and book.get("will_import")
    ]
    if apply_plan["skipped_books"]:
        count = apply_plan["skipped_books"]
        noun = "book" if count == 1 else "books"
        subject = "It" if count == 1 else "They"
        warnings.append(
            f"{count} export {noun} did not match by file hash. "
            f"{subject} can be downloaded for Reader-assisted import."
        )
    if apply_plan["active_sessions_will_import_as_historical"]:
        warnings.append("Active exported sessions will be imported as historical sessions, not active sessions.")
    if apply_plan["possible_duplicate_sessions"]:
        warnings.append("Possible duplicate sessions were found. They are warnings only and do not block preview.")
    if any(book.get("invalid_locator_sessions") for book in book_summaries):
        count = sum(book.get("invalid_locator_sessions") or 0 for book in book_summaries)
        phrase = (
            "session has malformed locators and needs"
            if count == 1
            else "sessions have malformed locators and need"
        )
        warnings.append(f"{count} {phrase} Reader-assisted import.")
    return warnings


def match_exported_book(*, user, exported: dict[str, Any]) -> tuple[Book | None, dict[str, str | None]]:
    visible_books = [
        book
        for book in Book.objects.select_related("file")
        .prefetch_related("authors", "identifiers", "group_assignments__group__memberships")
        .all()
        if library_policies.can_view_book(user=user, book=book)
    ]

    file_hash = _hash_value(exported.get("file_hash") or exported.get("source") or "")
    if file_hash:
        for book in visible_books:
            checksum = getattr(getattr(book, "file", None), "checksum", "") or ""
            if checksum.lower() == file_hash:
                return book, _matched(book=book, method="file_hash")

    return None, {"status": "unmatched", "method": None, "confidence": "none", "book_title": None}


def _matched(*, book: Book, method: str) -> dict[str, str | None]:
    return {
        "status": "matched",
        "method": method,
        "confidence": "exact",
        "book_title": book.title or "",
    }


def _cover_url(book: Book) -> str:
    cover = getattr(book, "cover_file", None)
    if not cover:
        return ""
    try:
        return cover.url or ""
    except ValueError:
        return ""


def _hash_value(value: str) -> str:
    text = str(value or "").strip().lower()
    match = re.search(r"sha256:([0-9a-f]{64})", text)
    return match.group(1) if match else ""


def _active_session_count(sessions: list[dict[str, Any]]) -> int:
    return sum(1 for session in sessions if session.get("status") == ReadingSession.STATUS_ACTIVE)


def _possible_duplicate_count(*, user, book: Book, sessions: list[dict[str, Any]]) -> int:
    return sum(
        1
        for session in sessions
        if _possible_duplicate_session(user=user, book=book, session=session)
    )


def _possible_duplicate_session(*, user, book: Book, session: dict[str, Any]) -> bool:
    started_at = parse_datetime(str(session.get("started_at") or ""))
    completed_at = parse_datetime(str(session.get("completed_at") or ""))
    if started_at is None:
        return False
    return ReadingSession.objects.filter(
        user=user,
        book=book,
        name=session.get("name") or "",
        started_at=started_at,
        completed_at=completed_at,
    ).exists()
