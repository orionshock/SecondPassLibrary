from __future__ import annotations

import logging
from collections import Counter
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.server_settings import (
    get_marginalia_active_session_tombstone_retention_days,
    get_marginalia_closed_session_tombstone_retention_days,
    get_marginalia_tombstone_retention_days,
)
from maintenance.results import MaintenanceResult
from marginalia.models import Annotation, ReadingSession

from .services import hard_delete_annotation_tombstones


logger = logging.getLogger(__name__)
DEFAULT_ANNOTATION_CLEANUP_LIMIT = 1000
MAX_ANNOTATION_CLEANUP_LIMIT = 10_000


def execute_deleted_annotation_cleanup(
    *,
    dry_run: bool = False,
    limit: int = DEFAULT_ANNOTATION_CLEANUP_LIMIT,
    now=None,
    active_retention_days: int | None = None,
    closed_retention_days: int | None = None,
) -> MaintenanceResult:
    if limit < 1 or limit > MAX_ANNOTATION_CLEANUP_LIMIT:
        raise ValueError(
            f"limit must be between 1 and {MAX_ANNOTATION_CLEANUP_LIMIT}."
        )
    stored_active_days, stored_closed_days = _stored_retention_days(
        active_retention_days,
        closed_retention_days,
    )
    active_days = _retention_days(
        active_retention_days,
        stored_active_days,
        "active_retention_days",
    )
    closed_days = _retention_days(
        closed_retention_days,
        stored_closed_days,
        "closed_retention_days",
    )
    now = now or timezone.now()
    cutoffs = {
        ReadingSession.STATUS_ACTIVE: now - timedelta(days=active_days),
        ReadingSession.STATUS_CLOSED: now - timedelta(days=closed_days),
    }
    eligible = Annotation.objects.filter(
        is_deleted=True,
        deleted_at__isnull=False,
    )
    eligible_by_status = {
        status: eligible.filter(
            session__status=status,
            deleted_at__lt=cutoff,
        )
        for status, cutoff in cutoffs.items()
    }
    candidate_counts = {
        status: queryset.count() for status, queryset in eligible_by_status.items()
    }
    eligibility = Q()
    for status, cutoff in cutoffs.items():
        eligibility |= Q(session__status=status, deleted_at__lt=cutoff)
    selected = list(
        eligible.filter(eligibility)
        .order_by("deleted_at", "id")
        .values_list("id", "session__status")[:limit]
    )
    selected_counts = Counter(status for _annotation_id, status in selected)
    deleted_counts = Counter()

    logger.info(
        "Deleted Annotation cleanup started: dry_run=%s limit=%d "
        "active_retention_days=%d closed_retention_days=%d",
        dry_run,
        limit,
        active_days,
        closed_days,
    )
    if not dry_run and selected:
        selected_ids = {
            status: [
                annotation_id
                for annotation_id, selected_status in selected
                if selected_status == status
            ]
            for status in cutoffs
        }
        with transaction.atomic():
            for status, annotation_ids in selected_ids.items():
                deleted_counts[status] = hard_delete_annotation_tombstones(
                    annotation_ids=annotation_ids,
                    session_status=status,
                    deleted_before=cutoffs[status],
                )

    active_candidates = candidate_counts[ReadingSession.STATUS_ACTIVE]
    closed_candidates = candidate_counts[ReadingSession.STATUS_CLOSED]
    active_selected = selected_counts[ReadingSession.STATUS_ACTIVE]
    closed_selected = selected_counts[ReadingSession.STATUS_CLOSED]
    active_deleted = deleted_counts[ReadingSession.STATUS_ACTIVE]
    closed_deleted = deleted_counts[ReadingSession.STATUS_CLOSED]
    total_candidates = active_candidates + closed_candidates
    total_deleted = active_deleted + closed_deleted
    counts = {
        "active_candidates": active_candidates,
        "active_selected": active_selected,
        "active_deleted": active_deleted,
        "closed_candidates": closed_candidates,
        "closed_selected": closed_selected,
        "closed_deleted": closed_deleted,
        "total_deleted": total_deleted,
        "deferred_by_limit": max(total_candidates - len(selected), 0),
        "failures": 0,
        "active_retention_days": active_days,
        "closed_retention_days": closed_days,
    }
    result = MaintenanceResult(
        summary=(
            "Deleted Annotation cleanup complete: "
            f"active={active_deleted} closed={closed_deleted} total={total_deleted}."
        ),
        counts=counts,
    )
    logger.info("Deleted Annotation cleanup completed: counts=%s", counts)
    return result


def _retention_days(value, stored_value: int, name: str) -> int:
    resolved = stored_value if value is None else value
    if isinstance(resolved, bool) or not isinstance(resolved, int) or resolved < 0:
        raise ValueError(f"{name} must be a non-negative integer.")
    return resolved


def _stored_retention_days(
    active_retention_days: int | None,
    closed_retention_days: int | None,
) -> tuple[int, int]:
    if active_retention_days is None and closed_retention_days is None:
        return get_marginalia_tombstone_retention_days()
    return (
        get_marginalia_active_session_tombstone_retention_days()
        if active_retention_days is None
        else active_retention_days,
        get_marginalia_closed_session_tombstone_retention_days()
        if closed_retention_days is None
        else closed_retention_days,
    )
