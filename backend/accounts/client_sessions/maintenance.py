from maintenance.results import MaintenanceResult

from .cleanup import DEFAULT_PAIRING_CLEANUP_LIMIT, cleanup_client_pairing_requests


def execute_pairing_request_cleanup(
    *, dry_run: bool = False, limit: int = DEFAULT_PAIRING_CLEANUP_LIMIT
) -> MaintenanceResult:
    result = cleanup_client_pairing_requests(dry_run=dry_run, limit=limit)
    summary = (
        "dry_run={0} eligible={1} selected={2} would_delete={3} deleted={4} "
        "skipped_limit={5} retained={6}"
    ).format(
        result.dry_run,
        result.eligible_count,
        result.selected_count,
        result.would_delete_count,
        result.deleted_count,
        result.skipped_limit_count,
        result.retained_count,
    )
    return MaintenanceResult(
        summary=summary,
        counts={
            "eligible": result.eligible_count,
            "selected": result.selected_count,
            "deleted": result.deleted_count,
            "skipped_limit": result.skipped_limit_count,
            "retained": result.retained_count,
        },
    )
