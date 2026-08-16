from django.contrib import admin, messages
from django.http import Http404
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from .models import MaintenanceTaskConfig, MaintenanceTaskRun
from .registry import get_task_definition
from .services import (
    ActiveMaintenanceRunError,
    UnknownMaintenanceTaskError,
    create_admin_run,
)


class SuperuserMaintenanceAdminMixin:
    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MaintenanceTaskConfig)
class MaintenanceTaskConfigAdmin(SuperuserMaintenanceAdminMixin, admin.ModelAdmin):
    actions = None
    fields = (
        "task_key",
        "task_name",
        "task_description",
        "enabled",
        "frequency",
        "next_due_at",
        "last_dispatched_at",
        "latest_run",
        "latest_status",
    )
    readonly_fields = (
        "task_key",
        "task_name",
        "task_description",
        "next_due_at",
        "last_dispatched_at",
        "latest_run",
        "latest_status",
    )
    list_display = (
        "task_name",
        "task_description",
        "enabled",
        "frequency",
        "latest_run",
        "latest_status",
        "run_now_link",
    )
    list_editable = ("enabled", "frequency")

    @admin.display(description="Name", ordering="task_key")
    def task_name(self, obj):
        definition = get_task_definition(obj.task_key)
        return definition.name if definition else f"Retired task: {obj.task_key}"

    @admin.display(description="Description")
    def task_description(self, obj):
        definition = get_task_definition(obj.task_key)
        return (
            definition.description
            if definition
            else "No registered executor is available for this task key."
        )

    @admin.display(description="Last Run")
    def latest_run(self, obj):
        run = obj.runs.first()
        if run is None:
            return "Never"
        url = reverse("admin:maintenance_maintenancetaskrun_change", args=(run.pk,))
        return format_html('<a href="{}">{}</a>', url, run.queued_at)

    @admin.display(description="Last Status")
    def latest_status(self, obj):
        run = obj.runs.first()
        return run.get_status_display() if run else "—"

    @admin.display(description="Run Now")
    def run_now_link(self, obj):
        if get_task_definition(obj.task_key) is None:
            return "Unavailable"
        url = reverse("admin:maintenance_task_run_now", args=(obj.pk,))
        return format_html('<a class="button" href="{}">Run now</a>', url)

    def get_urls(self):
        return [
            path(
                "<path:object_id>/run-now/",
                self.admin_site.admin_view(self.run_now_view),
                name="maintenance_task_run_now",
            )
        ] + super().get_urls()

    def run_now_view(self, request, object_id):
        configuration = self.get_object(request, object_id)
        if configuration is None or not self.has_change_permission(
            request, configuration
        ):
            raise Http404
        definition = get_task_definition(configuration.task_key)
        if definition is None:
            self.message_user(
                request,
                "This retired task has no registered executor.",
                level=messages.ERROR,
            )
            return redirect("admin:maintenance_maintenancetaskconfig_changelist")
        if request.method == "POST":
            try:
                run = create_admin_run(configuration=configuration, user=request.user)
            except ActiveMaintenanceRunError:
                self.message_user(
                    request,
                    "This task already has a queued or running execution.",
                    level=messages.WARNING,
                )
                return redirect(
                    "admin:maintenance_maintenancetaskconfig_change",
                    configuration.pk,
                )
            except UnknownMaintenanceTaskError as exc:
                raise Http404 from exc
            return redirect(
                "admin:maintenance_maintenancetaskrun_change",
                run.pk,
            )
        context = {
            **self.admin_site.each_context(request),
            "title": f"Run {definition.name}",
            "opts": self.model._meta,
            "configuration": configuration,
            "definition": definition,
        }
        return TemplateResponse(
            request,
            "admin/maintenance/maintenancetaskconfig/run_now.html",
            context,
        )


@admin.register(MaintenanceTaskRun)
class MaintenanceTaskRunAdmin(SuperuserMaintenanceAdminMixin, admin.ModelAdmin):
    actions = None
    list_display = (
        "task_name",
        "trigger",
        "status",
        "queued_at",
        "started_at",
        "completed_at",
    )
    list_filter = ("status", "trigger", "task_key")
    readonly_fields = (
        "id",
        "task_name",
        "task_description",
        "task_key",
        "trigger",
        "requested_by",
        "status",
        "queued_at",
        "started_at",
        "completed_at",
        "result_summary",
        "result_counts",
        "failure_summary",
    )
    fields = readonly_fields

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Task")
    def task_name(self, obj):
        definition = get_task_definition(obj.task_key)
        return definition.name if definition else f"Retired task: {obj.task_key}"

    @admin.display(description="Description")
    def task_description(self, obj):
        definition = get_task_definition(obj.task_key)
        return (
            definition.description
            if definition
            else "No registered executor is available for this task key."
        )
