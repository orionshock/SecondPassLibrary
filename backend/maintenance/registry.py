from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from accounts.client_sessions.maintenance import execute_pairing_request_cleanup
from marginalia.imports.maintenance import execute_import_stage_cleanup
from shelves.maintenance import execute_unavailable_shelf_item_cleanup

from .models import MaintenanceFrequency
from .results import MaintenanceResult


@dataclass(frozen=True, slots=True)
class MaintenanceTaskDefinition:
    key: str
    name: str
    description: str
    default_frequency: MaintenanceFrequency
    execute: Callable[[], MaintenanceResult]
    default_enabled: bool = False


TASK_DEFINITIONS = (
    MaintenanceTaskDefinition(
        key="cleanup_client_pairing_requests",
        name="Cleanup Client Pairing Requests",
        description="Remove expired and retained terminal Reader pairing requests.",
        default_frequency=MaintenanceFrequency.DAILY,
        execute=execute_pairing_request_cleanup,
    ),
    MaintenanceTaskDefinition(
        key="cleanup_marginalia_import_stages",
        name="Cleanup Marginalia Import Stages",
        description="Remove expired import stages and safe orphaned stage files.",
        default_frequency=MaintenanceFrequency.HOURLY,
        execute=execute_import_stage_cleanup,
    ),
    MaintenanceTaskDefinition(
        key="cleanup_unavailable_shelf_items",
        name="Cleanup Unavailable Shelf Items",
        description="Remove unavailable Books from user-owned Shelves.",
        default_frequency=MaintenanceFrequency.WEEKLY,
        execute=execute_unavailable_shelf_item_cleanup,
    ),
)

TASK_REGISTRY = {definition.key: definition for definition in TASK_DEFINITIONS}


def get_task_definition(task_key: str) -> MaintenanceTaskDefinition | None:
    return TASK_REGISTRY.get(task_key)
