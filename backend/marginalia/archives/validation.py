from __future__ import annotations

import json

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker

from marginalia.profile import MARGINALIA_PROFILE_URI

from .types import (
    ArchiveAnnotation,
    ArchiveBook,
    ArchiveBookmark,
    ArchiveHighlight,
    ArchiveHighlightBody,
    ArchiveProgress,
    ArchiveReadingSession,
    MarginaliaArchive,
    SessionStatus,
)


MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
MAX_ARCHIVE_SESSIONS = 100_000
MAX_ARCHIVE_ANNOTATIONS = 1_000_000
MAX_VALIDATION_ISSUES = 20


@dataclass(frozen=True, slots=True)
class ArchiveValidationIssue:
    path: str
    rule: str


class MalformedArchiveError(ValueError):
    def __init__(self):
        super().__init__("The Marginalia archive is not valid JSON.")


class UnsupportedArchiveProfileError(ValueError):
    def __init__(self):
        super().__init__("The Marginalia archive profile is not supported.")


class ArchiveValidationError(ValueError):
    def __init__(self, issues: tuple[ArchiveValidationIssue, ...]):
        super().__init__("The Marginalia archive does not satisfy the canonical contract.")
        self.issues = issues


def _load_schema() -> dict[str, Any]:
    schema_path = Path(__file__).with_name("schema.json")
    return json.loads(schema_path.read_text(encoding="utf-8"))


_VALIDATOR = Draft202012Validator(_load_schema(), format_checker=FormatChecker())


def parse_archive(data: bytes | str) -> MarginaliaArchive:
    raw = _decode_json(data)
    validate_archive_value(raw)
    return _archive_from_wire(raw)


def validate_archive_value(value: Any) -> None:
    if isinstance(value, dict):
        profile = value.get("profile")
        if isinstance(profile, str) and profile != MARGINALIA_PROFILE_URI:
            raise UnsupportedArchiveProfileError

    errors = sorted(_VALIDATOR.iter_errors(value), key=_validation_error_key)
    issues = [_issue(error.absolute_path, error.validator) for error in errors]
    issues.extend(_identity_and_collection_issues(value))
    if issues:
        raise ArchiveValidationError(tuple(issues[:MAX_VALIDATION_ISSUES]))


def _decode_json(data: bytes | str) -> Any:
    if isinstance(data, bytes) and len(data) > MAX_ARCHIVE_BYTES:
        raise ArchiveValidationError(
            (ArchiveValidationIssue(path="$", rule="maxBytes"),)
        )
    if isinstance(data, str) and len(data.encode("utf-8")) > MAX_ARCHIVE_BYTES:
        raise ArchiveValidationError(
            (ArchiveValidationIssue(path="$", rule="maxBytes"),)
        )
    try:
        if isinstance(data, bytes):
            text = data.decode("utf-8")
        elif isinstance(data, str):
            text = data
        else:
            raise MalformedArchiveError
        return json.loads(text, parse_constant=_reject_non_json_number)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise MalformedArchiveError from None


def _reject_non_json_number(_value: str):
    raise ValueError


def _validation_error_key(error) -> tuple[str, str]:
    return (_path(error.absolute_path), str(error.validator))


def _issue(path_parts, rule: object) -> ArchiveValidationIssue:
    return ArchiveValidationIssue(path=_path(path_parts), rule=str(rule))


def _path(parts) -> str:
    path = "$"
    for part in parts:
        path += f"[{part}]" if isinstance(part, int) else f".{part}"
    return path


def _identity_and_collection_issues(value: Any) -> list[ArchiveValidationIssue]:
    if not isinstance(value, dict) or not isinstance(value.get("books"), list):
        return []

    issues: list[ArchiveValidationIssue] = []
    book_hashes: set[str] = set()
    session_ids: set[str] = set()
    session_count = 0
    annotation_count = 0
    for book_index, book in enumerate(value["books"]):
        if not isinstance(book, dict):
            continue
        file_hash = book.get("fileHash")
        if isinstance(file_hash, str):
            if file_hash in book_hashes:
                issues.append(
                    ArchiveValidationIssue(
                        path=f"$.books[{book_index}].fileHash",
                        rule="uniqueBookFileHash",
                    )
                )
            book_hashes.add(file_hash)
        sessions = book.get("readingSessions")
        if not isinstance(sessions, list):
            continue
        session_count += len(sessions)
        for session_index, session in enumerate(sessions):
            if not isinstance(session, dict):
                continue
            session_id = session.get("sourceReadingSessionId")
            if isinstance(session_id, str):
                if session_id in session_ids:
                    issues.append(
                        ArchiveValidationIssue(
                            path=(
                                f"$.books[{book_index}].readingSessions"
                                f"[{session_index}].sourceReadingSessionId"
                            ),
                            rule="uniqueSourceReadingSessionId",
                        )
                    )
                session_ids.add(session_id)
            annotations = session.get("annotations")
            if not isinstance(annotations, list):
                continue
            annotation_count += len(annotations)
            client_ids: set[str] = set()
            for annotation_index, annotation in enumerate(annotations):
                if not isinstance(annotation, dict):
                    continue
                client_id = annotation.get("clientAnnotationId")
                if isinstance(client_id, str):
                    if client_id in client_ids:
                        issues.append(
                            ArchiveValidationIssue(
                                path=(
                                    f"$.books[{book_index}].readingSessions"
                                    f"[{session_index}].annotations"
                                    f"[{annotation_index}].clientAnnotationId"
                                ),
                                rule="uniqueClientAnnotationIdPerSession",
                            )
                        )
                    client_ids.add(client_id)
    if session_count > MAX_ARCHIVE_SESSIONS:
        issues.append(ArchiveValidationIssue(path="$.books", rule="maxSessions"))
    if annotation_count > MAX_ARCHIVE_ANNOTATIONS:
        issues.append(ArchiveValidationIssue(path="$.books", rule="maxAnnotations"))
    return issues


def _archive_from_wire(value: dict[str, Any]) -> MarginaliaArchive:
    return MarginaliaArchive(
        type="SecondPassMarginaliaExport",
        schema_version="0.1.0",
        profile=value["profile"],
        generated_at=value["generatedAt"],
        generator=value["generator"],
        books=tuple(_book_from_wire(book) for book in value["books"]),
    )


def _book_from_wire(value: dict[str, Any]) -> ArchiveBook:
    return ArchiveBook(
        file_hash=value.get("fileHash", ""),
        title=value["title"],
        authors=tuple(value["authors"]),
        reading_sessions=tuple(
            _session_from_wire(session) for session in value["readingSessions"]
        ),
    )


def _session_from_wire(value: dict[str, Any]) -> ArchiveReadingSession:
    progress = value["progress"]
    return ArchiveReadingSession(
        source_reading_session_id=value["sourceReadingSessionId"],
        name=value["name"],
        notes=value["notes"],
        status=cast(SessionStatus, value["status"]),
        started_at=value["startedAt"],
        closed_at=value["closedAt"],
        created_at=value["createdAt"],
        updated_at=value["updatedAt"],
        progress=(
            ArchiveProgress(
                cfi=progress["cfi"],
                location_label=progress.get("locationLabel"),
                updated_at=progress["updatedAt"],
            )
            if progress is not None
            else None
        ),
        annotations=tuple(_annotation_from_wire(item) for item in value["annotations"]),
    )


def _annotation_from_wire(value: dict[str, Any]) -> ArchiveAnnotation:
    location = value["location"]
    common = {
        "client_annotation_id": value["clientAnnotationId"],
        "location_cfi": location["cfi"],
        "location_label": location.get("locationLabel"),
        "created_at": value["createdAt"],
        "updated_at": value["updatedAt"],
    }
    if value["kind"] == "bookmark":
        return ArchiveBookmark(**common)
    body = value["body"]
    return ArchiveHighlight(
        **common,
        body=ArchiveHighlightBody(
            text=body["text"],
            prefix=body.get("prefix"),
            suffix=body.get("suffix"),
            color=body["color"],
            note=body.get("note"),
        ),
    )
