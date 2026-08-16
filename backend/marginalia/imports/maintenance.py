from maintenance.results import MaintenanceOperationError, MaintenanceResult

from .staging import cleanup_import_stages


def execute_import_stage_cleanup(*, dry_run: bool = False) -> MaintenanceResult:
    result = cleanup_import_stages(dry_run=dry_run)
    summary = (
        "expired_stages_found={0} records_deleted={1} files_deleted={2} "
        "missing_files={3} failures={4}"
    ).format(
        result.expired_stages_found,
        result.records_deleted,
        result.files_deleted,
        result.missing_files,
        result.failures,
    )
    maintenance_result = MaintenanceResult(
        summary=summary,
        counts={
            "expired_stages": result.expired_stages_found,
            "records_deleted": result.records_deleted,
            "files_deleted": result.files_deleted,
            "missing_files": result.missing_files,
        },
    )
    if result.failures:
        raise MaintenanceOperationError(
            "Marginalia import stage cleanup completed with failures.",
            result=maintenance_result,
        )
    return maintenance_result
