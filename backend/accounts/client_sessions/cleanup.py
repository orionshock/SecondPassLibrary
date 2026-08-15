from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import ClientLoginRequest
from accounts.operational_logging import logger


PAIRING_TERMINAL_RETENTION_HOURS = 24
DEFAULT_PAIRING_CLEANUP_LIMIT = 1000
MAX_PAIRING_CLEANUP_LIMIT = 10_000


@dataclass(frozen=True)
class PairingCleanupResult:
    eligible_count: int
    selected_count: int
    deleted_count: int
    skipped_limit_count: int
    retained_count: int
    dry_run: bool

    @property
    def would_delete_count(self) -> int:
        return self.selected_count if self.dry_run else 0


def cleanup_client_pairing_requests(
    *, dry_run: bool = False, limit: int = DEFAULT_PAIRING_CLEANUP_LIMIT
) -> PairingCleanupResult:
    if limit < 1 or limit > MAX_PAIRING_CLEANUP_LIMIT:
        raise ValueError(
            f"limit must be between 1 and {MAX_PAIRING_CLEANUP_LIMIT}."
        )

    now = timezone.now()
    terminal_cutoff = now - timedelta(hours=PAIRING_TERMINAL_RETENTION_HOURS)
    removable = Q(
        status__in=(
            ClientLoginRequest.STATUS_PENDING,
            ClientLoginRequest.STATUS_APPROVED,
        ),
        expires_at__lte=now,
    ) | Q(
        status__in=(
            ClientLoginRequest.STATUS_DENIED,
            ClientLoginRequest.STATUS_CONSUMED,
            ClientLoginRequest.STATUS_EXPIRED,
        ),
        updated_at__lte=terminal_cutoff,
    )

    with transaction.atomic():
        total_count = ClientLoginRequest.objects.count()
        eligible_count = ClientLoginRequest.objects.filter(removable).count()
        candidate_ids = list(
            ClientLoginRequest.objects.select_for_update()
            .filter(removable)
            .order_by("created_at", "pk")
            .values_list("pk", flat=True)[:limit]
        )
        deleted_count = 0
        if not dry_run and candidate_ids:
            deleted_count, _details = ClientLoginRequest.objects.filter(
                pk__in=candidate_ids
            ).delete()

    result = PairingCleanupResult(
        eligible_count=eligible_count,
        selected_count=len(candidate_ids),
        deleted_count=deleted_count,
        skipped_limit_count=eligible_count - len(candidate_ids),
        retained_count=total_count - deleted_count,
        dry_run=dry_run,
    )
    logger.info(
        "Client pairing cleanup completed: dry_run=%s eligible=%d selected=%d "
        "would_delete=%d deleted=%d skipped_limit=%d retained=%d",
        result.dry_run,
        result.eligible_count,
        result.selected_count,
        result.would_delete_count,
        result.deleted_count,
        result.skipped_limit_count,
        result.retained_count,
    )
    return result

