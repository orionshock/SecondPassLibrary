from __future__ import annotations

import logging

from django.core.exceptions import ObjectDoesNotExist

from library.imports.results import ImportBatchResult


logger = logging.getLogger(__name__)


def log_import_batch_completed(
    *,
    result: ImportBatchResult,
    actor=None,
    processed_bytes: int | None = None,
) -> None:
    actor_id = _actor_uuid(actor)
    message = (
        "Library import completed: actor=%s source_type=%s imported=%d "
        "duplicate=%d conflict=%d failed=%d skipped=%d"
    )
    args = [
        actor_id,
        result.source_type,
        result.imported_count,
        result.duplicate_count,
        result.conflict_count,
        result.failed_count,
        result.skipped_count,
    ]
    if processed_bytes is not None:
        message += " processed_bytes=%d"
        args.append(max(0, int(processed_bytes)))
    logger.info(message, *args)


def _actor_uuid(actor) -> str:
    if actor is None or getattr(actor, "is_anonymous", False):
        return "none"
    try:
        profile = actor.profile
    except (AttributeError, ObjectDoesNotExist):
        return "none"
    return str(profile.pk)
