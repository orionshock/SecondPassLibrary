from __future__ import annotations

import hashlib
import json
import logging
import time

from copy import deepcopy
from dataclasses import dataclass
from functools import partial

from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from library.models import Book
from library.queries import visible_books_for_user
from marginalia.archives import (
    ArchiveBookmark,
    ArchiveHighlight,
    ArchiveReadingSession,
    ArchiveValidationError,
    MalformedArchiveError,
    UnsupportedArchiveProfileError,
    parse_archive,
)
from marginalia.models import Annotation, ImportStage, ReadingSession

from .staging import (
    ImportStageUnavailableError,
    claim_import_stage,
    delete_stage_file,
    read_staged_archive,
)


logger = logging.getLogger(__name__)
UNTITLED_BOOK = "Untitled Book"

# Preview validation, replay checks, and persistence stay together because they
# form one staged-import transaction boundary.


class ImportApplyError(Exception):
    pass


class ImportCandidateError(ImportApplyError):
    pass


class ImportReplayConflictError(ImportApplyError):
    pass


class StagedArchiveInvalidError(ImportApplyError):
    pass


@dataclass(frozen=True, slots=True)
class _SelectedSession:
    candidate_id: str
    book_candidate_id: str
    book_id: str
    staged_book_title: object
    source: ArchiveReadingSession
    name: str
    notes: str
    possible_duplicate: bool


def apply_import(*, user, import_token: str, reading_sessions: list[dict]) -> dict:
    deadline = time.monotonic() + 10
    while True:
        try:
            return _apply_import_once(
                user=user,
                import_token=import_token,
                reading_sessions=reading_sessions,
            )
        except StagedArchiveInvalidError:
            logger.error("Marginalia import apply found inconsistent staged data.")
            raise
        except OperationalError as exc:
            if "locked" not in str(exc).lower() or time.monotonic() >= deadline:
                raise
            time.sleep(0.05)


@transaction.atomic
def _apply_import_once(
    *, user, import_token: str, reading_sessions: list[dict]
) -> dict:
    stage = claim_import_stage(user=user, token=import_token)
    preview_candidates = _preview_candidates(stage.preview)
    selections = _normalize_selections(
        reading_sessions,
        preview_candidates,
        allow_applied_inaccessible=stage.state == ImportStage.STATE_APPLIED,
    )
    fingerprint = _request_fingerprint(selections)

    if stage.state == ImportStage.STATE_APPLIED:
        if stage.request_fingerprint != fingerprint:
            raise ImportReplayConflictError
        return stage.result
    if stage.state != ImportStage.STATE_APPLYING:
        raise ImportStageUnavailableError

    try:
        archive = parse_archive(read_staged_archive(stage))
    except ImportStageUnavailableError:
        raise
    except (
        ArchiveValidationError,
        MalformedArchiveError,
        UnsupportedArchiveProfileError,
    ) as exc:
        raise StagedArchiveInvalidError from exc

    selected = _resolve_selected_sessions(
        archive=archive,
        selections=selections,
        preview_candidates=preview_candidates,
    )

    _validate_local_books(selected)
    accessible, inaccessible = _partition_current_book_access(
        user=user,
        selected=selected,
    )
    try:
        imported = _create_sessions(user=user, selected=accessible)
    except (IntegrityError, ValueError) as exc:
        raise StagedArchiveInvalidError from exc

    updated_preview = _preview_with_inaccessible_candidates(
        preview=stage.preview,
        inaccessible=inaccessible,
    )
    result = _result(
        imported,
        preview=updated_preview,
    )
    applied_at = timezone.now()
    stage.state = ImportStage.STATE_APPLIED
    stage.request_fingerprint = fingerprint
    stage.preview = updated_preview
    stage.result = result
    stage.applied_at = applied_at
    stage.save(
        update_fields=[
            "state",
            "request_fingerprint",
            "preview",
            "result",
            "applied_at",
            "updated_at",
        ]
    )
    # The staged archive remains the source for unmatched-download recovery.
    if not result["unmatched_download_available"]:
        transaction.on_commit(partial(delete_stage_file, stage.storage_name))
    if inaccessible:
        transaction.on_commit(
            partial(
                _log_partial_apply_summary,
                user_id=user.pk,
                stage_ref=stage.token_digest[:8],
                applied_count=len(imported),
                inaccessible_count=len(inaccessible),
                other_unmatched_count=(
                    result["unmatched_reading_session_count"] - len(inaccessible)
                ),
            )
        )
    return result


def _preview_candidates(preview: dict) -> dict[str, dict]:
    candidates = {}
    try:
        for book in preview["books"]:
            match = book["match"]
            for session in book["reading_sessions"]:
                candidates[session["candidate_id"]] = {
                    **session,
                    "book_candidate_id": book["candidate_id"],
                    "book_id": match.get("book_id"),
                    "staged_book_title": book.get("title"),
                    "matched": match["status"] == "matched",
                }
    except (KeyError, TypeError) as exc:
        raise StagedArchiveInvalidError from exc
    return candidates


def _normalize_selections(
    reading_sessions: list[dict],
    preview_candidates: dict[str, dict],
    *,
    allow_applied_inaccessible: bool,
) -> tuple[dict, ...]:
    normalized = []
    for requested in reading_sessions:
        candidate = preview_candidates.get(requested["candidate_id"])
        if (
            candidate is None
            or not candidate["matched"]
            or (
                not candidate["will_import"]
                and not (
                    allow_applied_inaccessible
                    and candidate.get("unmatched_reason") == "book_inaccessible"
                )
            )
        ):
            raise ImportCandidateError
        normalized.append(
            {
                "candidate_id": requested["candidate_id"],
                "name": requested.get("name", candidate["name"]),
                "notes": requested.get("notes", candidate["notes"]),
            }
        )
    return tuple(sorted(normalized, key=lambda item: item["candidate_id"]))


def _request_fingerprint(selections: tuple[dict, ...]) -> str:
    normalized = json.dumps(
        selections,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def _resolve_selected_sessions(
    *, archive, selections: tuple[dict, ...], preview_candidates: dict[str, dict]
) -> tuple[_SelectedSession, ...]:
    source_sessions = {
        session.source_reading_session_id: session
        for book in archive.books
        for session in book.reading_sessions
    }
    selected = []
    for selection in selections:
        candidate = preview_candidates[selection["candidate_id"]]
        source = source_sessions.get(candidate["source_reading_session_id"])
        if source is None or not candidate["book_id"]:
            raise StagedArchiveInvalidError
        selected.append(
            _SelectedSession(
                candidate_id=selection["candidate_id"],
                book_candidate_id=candidate["book_candidate_id"],
                book_id=candidate["book_id"],
                staged_book_title=candidate["staged_book_title"],
                source=source,
                name=selection["name"],
                notes=selection["notes"],
                possible_duplicate=bool(candidate.get("possible_duplicate")),
            )
        )
    return tuple(selected)


def _validate_local_books(selected: tuple[_SelectedSession, ...]) -> None:
    book_ids = {item.book_id for item in selected}
    if Book.objects.filter(pk__in=book_ids).count() != len(book_ids):
        raise StagedArchiveInvalidError


def _create_sessions(
    *, user, selected: tuple[_SelectedSession, ...]
) -> list[tuple[_SelectedSession, ReadingSession]]:
    pairs = []
    for item in selected:
        source = item.source
        closed_at = _timestamp(source.closed_at or source.updated_at)
        session = ReadingSession(
            user=user,
            book_id=item.book_id,
            name=item.name,
            notes=item.notes,
            status=ReadingSession.STATUS_CLOSED,
            started_at=_timestamp(source.started_at),
            closed_at=closed_at,
            progress_cfi=source.progress.cfi if source.progress else "",
            progress_location_label=(
                (source.progress.location_label or "") if source.progress else ""
            ),
            progress_updated_at=(
                _timestamp(source.progress.updated_at) if source.progress else None
            ),
            created_at=_timestamp(source.created_at),
            updated_at=_timestamp(source.updated_at),
        )
        pairs.append((item, session))

    sessions = [session for _item, session in pairs]
    if not sessions:
        return []
    ReadingSession.objects.bulk_create(sessions)
    for item, session in pairs:
        source = item.source
        session.started_at = _timestamp(source.started_at)
        session.created_at = _timestamp(source.created_at)
        session.updated_at = _timestamp(source.updated_at)
    ReadingSession.objects.bulk_update(
        sessions,
        ["started_at", "created_at", "updated_at"],
    )
    _create_annotations(pairs)
    return pairs


def _partition_current_book_access(
    *, user, selected: tuple[_SelectedSession, ...]
) -> tuple[tuple[_SelectedSession, ...], tuple[_SelectedSession, ...]]:
    """Recheck uncached Library authority at the import mutation boundary."""
    book_ids = {item.book_id for item in selected}
    visible_ids = {
        str(book_id)
        for book_id in visible_books_for_user(user, cached=False)
        .filter(pk__in=book_ids)
        .values_list("pk", flat=True)
    }
    return (
        tuple(item for item in selected if item.book_id in visible_ids),
        tuple(item for item in selected if item.book_id not in visible_ids),
    )


def _normalized_staged_book_title(value: object) -> str:
    if not isinstance(value, str):
        return UNTITLED_BOOK
    normalized = " ".join(value.split())
    if not normalized:
        return UNTITLED_BOOK
    return normalized


def _preview_with_inaccessible_candidates(
    *, preview: dict, inaccessible: tuple[_SelectedSession, ...]
) -> dict:
    updated = deepcopy(preview)
    inaccessible_ids = {item.candidate_id for item in inaccessible}
    if not inaccessible_ids:
        return updated

    affected_books = set()
    for book in updated["books"]:
        for candidate in book["reading_sessions"]:
            if candidate["candidate_id"] not in inaccessible_ids:
                continue
            candidate["will_import"] = False
            candidate["unmatched_reason"] = "book_inaccessible"
            affected_books.add(book["candidate_id"])
    if len(inaccessible_ids) != len(inaccessible):
        raise StagedArchiveInvalidError
    updated["unmatched_book_count"] += len(affected_books)
    updated["unmatched_reading_session_count"] += len(inaccessible)
    updated["unmatched_downloadable_reading_session_count"] += len(inaccessible)
    return updated


def _log_partial_apply_summary(
    *,
    user_id,
    stage_ref: str,
    applied_count: int,
    inaccessible_count: int,
    other_unmatched_count: int,
) -> None:
    logger.info(
        "Marginalia import partial apply completed. user_id=%s stage_ref=%s "
        "applied_count=%s inaccessible_count=%s other_unmatched_count=%s",
        user_id,
        stage_ref,
        applied_count,
        inaccessible_count,
        other_unmatched_count,
    )


def _create_annotations(
    pairs: list[tuple[_SelectedSession, ReadingSession]],
) -> None:
    annotations = []
    timestamp_pairs = []
    for item, session in pairs:
        for source in item.source.annotations:
            values = {
                "session": session,
                "client_id": source.client_annotation_id,
                "kind": source.kind,
                "cfi": source.location_cfi,
                "location_label": source.location_label or "",
                "created_at": _timestamp(source.created_at),
                "updated_at": _timestamp(source.updated_at),
            }
            if isinstance(source, ArchiveHighlight):
                values.update(
                    highlight_text=source.body.text,
                    quote_prefix=source.body.prefix or "",
                    quote_suffix=source.body.suffix or "",
                    highlight_color=source.body.color,
                    comment_text=source.body.note or "",
                )
            elif not isinstance(source, ArchiveBookmark):
                raise StagedArchiveInvalidError
            annotation = Annotation(**values)
            annotations.append(annotation)
            timestamp_pairs.append((annotation, source))
    Annotation.objects.bulk_create(annotations)
    for annotation, source in timestamp_pairs:
        annotation.created_at = _timestamp(source.created_at)
        annotation.updated_at = _timestamp(source.updated_at)
    if annotations:
        Annotation.objects.bulk_update(annotations, ["created_at", "updated_at"])


def _result(
    imported: list[tuple[_SelectedSession, ReadingSession]],
    *,
    preview: dict,
) -> dict:
    rows = [
        {
            "candidate_id": item.candidate_id,
            "reading_session_id": str(session.pk),
            "status": session.status,
            "name": session.name,
            "annotation_count": len(item.source.annotations),
        }
        for item, session in imported
    ]
    warnings = [
        {
            "code": "POSSIBLE_DUPLICATE_SESSION",
            "message": "A similar Reading Session already existed at preview time.",
            "candidate_id": item.candidate_id,
        }
        for item, _session in imported
        if item.possible_duplicate
    ]
    unmatched_books = []
    for book in preview["books"]:
        match = book["match"]
        reasons = {
            candidate.get("unmatched_reason")
            for candidate in book["reading_sessions"]
            if candidate.get("unmatched_reason")
        }
        reason = (
            match.get("reason")
            if match["status"] == "unmatched"
            else ("book_inaccessible" if "book_inaccessible" in reasons else None)
        )
        if reason is not None:
            unmatched_books.append(
                {
                    "candidate_id": book["candidate_id"],
                    "title": _normalized_staged_book_title(book.get("title")),
                    "reason": reason,
                }
            )
    unmatched_count = preview["unmatched_reading_session_count"]
    downloadable_count = preview["unmatched_downloadable_reading_session_count"]
    return {
        "imported_reading_session_count": len(rows),
        "imported_annotation_count": sum(row["annotation_count"] for row in rows),
        "unmatched_reading_session_count": unmatched_count,
        "unmatched_downloadable_reading_session_count": downloadable_count,
        "unmatched_download_available": downloadable_count > 0,
        "unmatched_books": unmatched_books,
        "reading_sessions": rows,
        "warnings": warnings,
    }


def _timestamp(value: str):
    parsed = parse_datetime(value)
    if parsed is None:
        raise StagedArchiveInvalidError
    return parsed
