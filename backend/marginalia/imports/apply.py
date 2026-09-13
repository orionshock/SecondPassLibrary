from __future__ import annotations

import hashlib
import json
import logging
import time

from functools import partial

from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from library.models import Book
from library.queries import visible_books_for_user
from marginalia.archives import (
    ArchiveBookmark,
    ArchiveHighlight,
    ArchiveValidationError,
    MalformedArchiveError,
    UnsupportedArchiveProfileError,
    parse_archive,
)
from marginalia.models import Annotation, ImportStage, ReadingSession

from .plan import (
    PlanSelection,
    ResolvedSelection,
    StagedImportPlan,
    StagedImportPlanError,
    StagedImportSelectionError,
)
from .staging import (
    ImportStageUnavailableError,
    claim_import_stage,
    delete_stage_file,
    read_staged_archive,
)


logger = logging.getLogger(__name__)
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
    try:
        plan = StagedImportPlan.decode(stage.preview)
        selections = plan.normalize_selections(
            reading_sessions,
            allow_applied_inaccessible=stage.state == ImportStage.STATE_APPLIED,
        )
    except StagedImportSelectionError as exc:
        raise ImportCandidateError from exc
    except StagedImportPlanError as exc:
        raise StagedArchiveInvalidError from exc
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

    try:
        selected = plan.resolve_selections(
            archive=archive,
            selections=selections,
            include_empty_sessions=stage.include_empty_sessions,
        )
    except StagedImportPlanError as exc:
        raise StagedArchiveInvalidError from exc

    _validate_local_books(selected)
    accessible, inaccessible = _partition_current_book_access(
        user=user,
        selected=selected,
    )
    try:
        imported = _create_sessions(user=user, selected=accessible)
    except (IntegrityError, ValueError) as exc:
        raise StagedArchiveInvalidError from exc

    try:
        updated_plan = plan.with_access_lost(
            {item.candidate_id for item in inaccessible}
        )
    except StagedImportPlanError as exc:
        raise StagedArchiveInvalidError from exc
    result = _result(
        imported,
        plan=updated_plan,
    )
    applied_at = timezone.now()
    stage.state = ImportStage.STATE_APPLIED
    stage.request_fingerprint = fingerprint
    stage.preview = updated_plan.encode()
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


def _request_fingerprint(selections: tuple[PlanSelection, ...]) -> str:
    normalized = json.dumps(
        [
            {
                "candidate_id": selection.candidate_id,
                "name": selection.name,
                "notes": selection.notes,
            }
            for selection in selections
        ],
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def _validate_local_books(selected: tuple[ResolvedSelection, ...]) -> None:
    book_ids = {item.book_id for item in selected}
    if Book.objects.filter(pk__in=book_ids).count() != len(book_ids):
        raise StagedArchiveInvalidError


def _create_sessions(
    *, user, selected: tuple[ResolvedSelection, ...]
) -> list[tuple[ResolvedSelection, ReadingSession]]:
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
    *, user, selected: tuple[ResolvedSelection, ...]
) -> tuple[tuple[ResolvedSelection, ...], tuple[ResolvedSelection, ...]]:
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
    pairs: list[tuple[ResolvedSelection, ReadingSession]],
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
    imported: list[tuple[ResolvedSelection, ReadingSession]],
    *,
    plan: StagedImportPlan,
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
    unmatched_count = plan.unmatched_session_count
    downloadable_count = plan.unmatched_session_count
    return {
        "imported_reading_session_count": len(rows),
        "imported_annotation_count": sum(row["annotation_count"] for row in rows),
        "unmatched_reading_session_count": unmatched_count,
        "unmatched_downloadable_reading_session_count": downloadable_count,
        "unmatched_download_available": downloadable_count > 0,
        "unmatched_books": plan.unmatched_summaries(),
        "reading_sessions": rows,
        "warnings": warnings,
    }


def _timestamp(value: str):
    parsed = parse_datetime(value)
    if parsed is None:
        raise StagedArchiveInvalidError
    return parsed
