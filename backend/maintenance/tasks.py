from huey import crontab
from huey.contrib.djhuey import db_periodic_task, db_task

from .services import dispatch_due_tasks, execute_run


@db_task(retries=0)
def execute_maintenance_run(run_id) -> None:
    execute_run(run_id)


@db_periodic_task(crontab(minute="*/5"), retries=0)
def dispatch_maintenance_tasks() -> None:
    dispatch_due_tasks()
