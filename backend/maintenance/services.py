from __future__ import annotations

import logging
from datetime import timedelta
from time import monotonic

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import MaintenanceFrequency, MaintenanceTaskConfig, MaintenanceTaskRun
from .registry import TASK_DEFINITIONS, get_task_definition
from .results import MaintenanceOperationError


logger = logging.getLogger(__name__)
ACTIVE_STATUSES = (
    MaintenanceTaskRun.Status.QUEUED,
    MaintenanceTaskRun.Status.RUNNING,
)
FAILURE_SUMMARY = "Task failed. Review application logs for details."
RUN_RETENTION = timedelta(days=90)


class UnknownMaintenanceTaskError(Exception):
    pass


class ActiveMaintenanceRunError(Exception):
    pass


def synchronize_task_configurations(*args, **kwargs) -> None:
    for definition in TASK_DEFINITIONS:
        MaintenanceTaskConfig.objects.get_or_create(
            task_key=definition.key,
            defaults={
                "enabled": definition.default_enabled,
                "frequency": definition.default_frequency,
            },
        )


def create_admin_run(*, configuration: MaintenanceTaskConfig, user):
    if get_task_definition(configuration.task_key) is None:
        raise UnknownMaintenanceTaskError(configuration.task_key)
    run = _create_run(
        configuration=configuration,
        trigger=MaintenanceTaskRun.Trigger.ADMIN,
        requested_by=user,
    )
    transaction.on_commit(lambda: enqueue_run(run.pk))
    return run


def _create_run(*, configuration, trigger, requested_by=None):
    try:
        with transaction.atomic():
            return MaintenanceTaskRun.objects.create(
                configuration=configuration,
                task_key=configuration.task_key,
                trigger=trigger,
                requested_by=requested_by,
            )
    except IntegrityError as exc:
        raise ActiveMaintenanceRunError(configuration.task_key) from exc


def enqueue_run(run_id) -> None:
    try:
        from .tasks import execute_maintenance_run

        execute_maintenance_run(run_id)
    except Exception:
        logger.exception("Maintenance run enqueue failed: run_id=%s", run_id)
        MaintenanceTaskRun.objects.filter(
            pk=run_id,
            status=MaintenanceTaskRun.Status.QUEUED,
        ).update(
            status=MaintenanceTaskRun.Status.FAILED,
            completed_at=timezone.now(),
            failure_summary="Task could not be queued. Review application logs.",
        )


def dispatch_due_tasks(*, now=None) -> int:
    now = now or timezone.now()
    enqueued_ids = []
    due_ids = list(
        MaintenanceTaskConfig.objects.filter(
            enabled=True,
            next_due_at__lte=now,
        )
        .exclude(frequency=MaintenanceFrequency.MANUAL)
        .values_list("pk", flat=True)
    )
    for config_id in due_ids:
        with transaction.atomic():
            configuration = MaintenanceTaskConfig.objects.select_for_update().get(
                pk=config_id
            )
            if (
                not configuration.enabled
                or configuration.frequency == MaintenanceFrequency.MANUAL
                or configuration.next_due_at is None
                or configuration.next_due_at > now
            ):
                continue
            interval = MaintenanceFrequency(configuration.frequency).interval
            configuration.last_dispatched_at = now
            configuration.next_due_at = now + interval
            configuration.save(
                update_fields=("last_dispatched_at", "next_due_at", "updated_at")
            )
            if get_task_definition(configuration.task_key) is None:
                continue
            if MaintenanceTaskRun.objects.filter(
                task_key=configuration.task_key,
                status__in=ACTIVE_STATUSES,
            ).exists():
                continue
            try:
                run = MaintenanceTaskRun.objects.create(
                    configuration=configuration,
                    task_key=configuration.task_key,
                    trigger=MaintenanceTaskRun.Trigger.SCHEDULED,
                )
            except IntegrityError:
                continue
            enqueued_ids.append(run.pk)
            transaction.on_commit(lambda run_id=run.pk: enqueue_run(run_id))
    _prune_old_runs(now=now)
    return len(enqueued_ids)


def execute_run(run_id) -> None:
    started_at = timezone.now()
    with transaction.atomic():
        updated = MaintenanceTaskRun.objects.filter(
            pk=run_id,
            status=MaintenanceTaskRun.Status.QUEUED,
        ).update(status=MaintenanceTaskRun.Status.RUNNING, started_at=started_at)
    if not updated:
        return

    run = MaintenanceTaskRun.objects.get(pk=run_id)
    definition = get_task_definition(run.task_key)
    if definition is None:
        _fail_run(run, "Registered task is no longer available.")
        return

    started_clock = monotonic()
    logger.info(
        "Maintenance task started: task_key=%s trigger=%s run_id=%s",
        run.task_key,
        run.trigger,
        run.pk,
    )
    try:
        result = definition.execute()
    except MaintenanceOperationError as exc:
        summary = str(exc)
        if exc.result is not None:
            summary = f"{summary} {exc.result.summary}"
        _fail_run(run, summary, started_clock=started_clock)
        return
    except Exception:
        logger.exception(
            "Maintenance task failed: task_key=%s trigger=%s run_id=%s duration_ms=%d",
            run.task_key,
            run.trigger,
            run.pk,
            int((monotonic() - started_clock) * 1000),
        )
        _store_failed_run(run, FAILURE_SUMMARY)
        return

    duration_ms = int((monotonic() - started_clock) * 1000)
    MaintenanceTaskRun.objects.filter(pk=run.pk).update(
        status=MaintenanceTaskRun.Status.SUCCEEDED,
        completed_at=timezone.now(),
        result_summary=result.summary,
        result_counts=dict(result.counts),
        failure_summary="",
    )
    logger.info(
        "Maintenance task succeeded: task_key=%s trigger=%s run_id=%s "
        "duration_ms=%d counts=%s",
        run.task_key,
        run.trigger,
        run.pk,
        duration_ms,
        dict(result.counts),
    )


def _fail_run(run, summary, *, started_clock=None):
    duration_ms = (
        int((monotonic() - started_clock) * 1000) if started_clock is not None else 0
    )
    logger.error(
        "Maintenance task failed: task_key=%s trigger=%s run_id=%s duration_ms=%d",
        run.task_key,
        run.trigger,
        run.pk,
        duration_ms,
    )
    _store_failed_run(run, str(summary)[:1000])


def _store_failed_run(run, summary):
    MaintenanceTaskRun.objects.filter(pk=run.pk).update(
        status=MaintenanceTaskRun.Status.FAILED,
        completed_at=timezone.now(),
        failure_summary=" ".join(str(summary).split())[:1000],
    )


def _prune_old_runs(*, now) -> None:
    stale_ids = list(
        MaintenanceTaskRun.objects.filter(
            status__in=(
                MaintenanceTaskRun.Status.SUCCEEDED,
                MaintenanceTaskRun.Status.FAILED,
            ),
            completed_at__lt=now - RUN_RETENTION,
        ).values_list("pk", flat=True)[:1000]
    )
    if stale_ids:
        MaintenanceTaskRun.objects.filter(pk__in=stale_ids).delete()
