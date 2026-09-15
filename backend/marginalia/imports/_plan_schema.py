from __future__ import annotations

from copy import deepcopy
from typing import Mapping

MATCHED = "matched"
UNMATCHED = "unmatched"
BOOK_INACCESSIBLE = "book_inaccessible"
UNMATCHED_REASONS = frozenset({"not_found", "ambiguous_match", BOOK_INACCESSIBLE})
IMPORT_STATUS = "closed"


class StagedImportPlanError(ValueError):
    pass


def decode_and_index(
    persisted: object,
) -> tuple[
    Mapping,
    list,
    list,
    dict[str, dict],
    dict[str, tuple[dict, dict]],
    dict[str, str],
]:
    try:
        value = _mapping(persisted)
        books = deepcopy(_list(value["books"]))
        warnings = deepcopy(_list(value["warnings"]))
        book_index, candidate_index, source_index = validate_and_index(
            books,
            warnings,
        )
        return (
            value,
            books,
            warnings,
            book_index,
            candidate_index,
            source_index,
        )
    except StagedImportPlanError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise StagedImportPlanError from exc


def validate_and_index(
    books: list,
    warnings: list,
) -> tuple[
    dict[str, dict],
    dict[str, tuple[dict, dict]],
    dict[str, str],
]:
    if not books:
        raise StagedImportPlanError
    book_ids = set()
    candidate_ids = set()
    source_ids = set()
    book_index = {}
    candidate_index = {}
    source_index = {}
    for raw_book in books:
        book = _mapping(raw_book)
        book_id = text(book["candidate_id"])
        if book_id in book_ids:
            raise StagedImportPlanError
        book_ids.add(book_id)
        book_index[book_id] = book
        text(book["file_hash"], allow_blank=True)
        text(book["title"], allow_blank=True)
        tuple(text(author) for author in _list(book["authors"]))
        match = _mapping(book["match"])
        status = text(match["status"])
        if status == MATCHED:
            text(match["book_id"])
            if match.get("reason") is not None:
                raise StagedImportPlanError
            if match.get("cover_url") is not None and not isinstance(
                match["cover_url"], str
            ):
                raise StagedImportPlanError
        elif (
            status != UNMATCHED
            or text(match["reason"]) not in UNMATCHED_REASONS
            or match.get("book_id") is not None
            or match.get("cover_url") is not None
        ):
            raise StagedImportPlanError
        sessions = _list(book["reading_sessions"])
        if not sessions:
            raise StagedImportPlanError
        for raw_session in sessions:
            row = _mapping(raw_session)
            candidate_id = text(row["candidate_id"])
            source_id = text(row["source_reading_session_id"])
            if candidate_id in candidate_ids or source_id in source_ids:
                raise StagedImportPlanError
            candidate_ids.add(candidate_id)
            source_ids.add(source_id)
            candidate_index[candidate_id] = (book, row)
            source_index[source_id] = candidate_id
            validate_session(row, matched=status == MATCHED)
    _validate_warnings(warnings, candidate_ids=set(candidate_index))
    return book_index, candidate_index, source_index


def validate_session(row: Mapping, *, matched: bool) -> None:
    text(row["name"], allow_blank=True)
    text(row["notes"], allow_blank=True)
    text(row["source_status"])
    text(row["started_at"])
    if row["closed_at"] is not None and not isinstance(row["closed_at"], str):
        raise StagedImportPlanError
    if row["will_import_as_status"] != IMPORT_STATUS:
        raise StagedImportPlanError
    count = row["annotation_count"]
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise StagedImportPlanError
    if not isinstance(row["will_import"], bool) or not isinstance(
        row["possible_duplicate"], bool
    ):
        raise StagedImportPlanError
    reason = row.get("unmatched_reason")
    if reason is not None and reason not in UNMATCHED_REASONS:
        raise StagedImportPlanError
    if matched and row["will_import"] == (reason is not None):
        raise StagedImportPlanError
    if not matched and (row["will_import"] or reason is not None):
        raise StagedImportPlanError


def _validate_warnings(warnings: list, *, candidate_ids: set[str]) -> None:
    for raw in warnings:
        warning = _mapping(raw)
        text(warning["code"])
        text(warning["message"])
        if text(warning["candidate_id"]) not in candidate_ids:
            raise StagedImportPlanError


def text(value: object, *, allow_blank: bool = False) -> str:
    if not isinstance(value, str) or (not allow_blank and not value):
        raise StagedImportPlanError
    return value


def _mapping(value: object) -> Mapping:
    if not isinstance(value, Mapping):
        raise StagedImportPlanError
    return value


def _list(value: object) -> list:
    if not isinstance(value, list):
        raise StagedImportPlanError
    return value
