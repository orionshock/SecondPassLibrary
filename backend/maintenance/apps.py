from django.apps import AppConfig
from django.db.models.signals import post_migrate


class MaintenanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "maintenance"

    def ready(self):
        from maintenance.services import synchronize_task_configurations

        post_migrate.connect(
            synchronize_task_configurations,
            sender=self,
            dispatch_uid="maintenance.synchronize_task_configurations",
        )
