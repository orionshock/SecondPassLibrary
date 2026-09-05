from django import forms
from django.contrib import admin, messages
from django.http import Http404
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from core.server_settings import (
    get_marginalia_active_session_tombstone_retention_days,
    get_marginalia_closed_session_tombstone_retention_days,
    set_marginalia_active_session_tombstone_retention_days,
    set_marginalia_closed_session_tombstone_retention_days,
)

from .models import MaintenanceTaskConfig, MaintenanceTaskRun
from .registry import get_task_definition
from .results import result_count_label
from .services import (
    ActiveMaintenanceRunError,
    UnknownMaintenanceTaskError,
    create_admin_run,
    delete_completed_run_history,
    prune_completed_runs,
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


DELETED_ANNOTATION_CLEANUP_TASK_KEY = "cleanup_deleted_annotations"


class MaintenanceTaskConfigAdminForm(forms.ModelForm):
    active_retention_days = forms.IntegerField(
        required=False,
        min_value=0,
        label="Active Session Annotation Tombstone Retention",
        help_text=(
            "Days to retain tombstoned Annotations while their Reading Session "
            "remains active before permanent deletion."
        ),
    )
    closed_retention_days = forms.IntegerField(
        required=False,
        min_value=0,
        label="Closed Session Annotation Tombstone Retention",
        help_text=(
            "Days to retain tombstoned Annotations once their Reading Session "
            "is closed before permanent deletion."
        ),
    )

    class Meta:
        model = MaintenanceTaskConfig
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.task_key != DELETED_ANNOTATION_CLEANUP_TASK_KEY:
            self.fields.pop("active_retention_days", None)
            self.fields.pop("closed_retention_days", None)
            return
        self.fields["active_retention_days"].required = True
        self.fields["closed_retention_days"].required = True
        self.initial["active_retention_days"] = (
            get_marginalia_active_session_tombstone_retention_days()
        )
        self.initial["closed_retention_days"] = (
            get_marginalia_closed_session_tombstone_retention_days()
        )


@admin.register(MaintenanceTaskConfig)
class MaintenanceTaskConfigAdmin(SuperuserMaintenanceAdminMixin, admin.ModelAdmin):
    form = MaintenanceTaskConfigAdminForm
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

    def get_changelist_form(self, request, **kwargs):
        return super().get_changelist_form(
            request,
            form=forms.ModelForm,
            **kwargs,
        )

    def get_fieldsets(self, request, obj=None):
        if obj is None or obj.task_key != DELETED_ANNOTATION_CLEANUP_TASK_KEY:
            return super().get_fieldsets(request, obj)
        return (
            (
                "Task",
                {"fields": ("task_key", "task_name", "task_description")},
            ),
            ("Schedule", {"fields": ("enabled", "frequency")}),
            (
                "Annotation tombstone retention",
                {"fields": ("active_retention_days", "closed_retention_days")},
            ),
            (
                "Execution",
                {
                    "fields": (
                        "next_due_at",
                        "last_dispatched_at",
                        "latest_run",
                        "latest_status",
                    )
                },
            ),
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.task_key != DELETED_ANNOTATION_CLEANUP_TASK_KEY:
            return
        set_marginalia_active_session_tombstone_retention_days(
            form.cleaned_data["active_retention_days"]
        )
        set_marginalia_closed_session_tombstone_retention_days(
            form.cleaned_data["closed_retention_days"]
        )

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
    change_form_template = "admin/maintenance/maintenancetaskrun/change_form.html"
    change_list_template = "admin/maintenance/maintenancetaskrun/change_list.html"
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

    def get_urls(self):
        return [
            path(
                "prune-history/",
                self.admin_site.admin_view(self.prune_history_view),
                name="maintenance_task_run_prune_history",
            ),
            path(
                "delete-history/",
                self.admin_site.admin_view(self.delete_history_view),
                name="maintenance_task_run_delete_history",
            ),
        ] + super().get_urls()

    def prune_history_view(self, request):
        if not self.has_view_permission(request):
            raise Http404
        if request.method == "POST":
            deleted = prune_completed_runs()
            self.message_user(
                request,
                f"Pruned {deleted} completed maintenance task run(s).",
                level=messages.SUCCESS,
            )
            return redirect("admin:maintenance_maintenancetaskrun_changelist")
        context = {
            **self.admin_site.each_context(request),
            "title": "Prune Maintenance Task Run History",
            "opts": self.model._meta,
        }
        return TemplateResponse(
            request,
            "admin/maintenance/maintenancetaskrun/prune_history.html",
            context,
        )

    def delete_history_view(self, request):
        if not self.has_view_permission(request):
            raise Http404
        if request.method == "POST":
            deleted = delete_completed_run_history()
            self.message_user(
                request,
                f"Deleted {deleted} completed maintenance task run(s).",
                level=messages.SUCCESS,
            )
            return redirect("admin:maintenance_maintenancetaskrun_changelist")
        context = {
            **self.admin_site.each_context(request),
            "title": "Delete Completed Maintenance Task Run History",
            "opts": self.model._meta,
        }
        return TemplateResponse(
            request,
            "admin/maintenance/maintenancetaskrun/delete_history.html",
            context,
        )

    def change_view(self, request, object_id, form_url="", extra_context=None):
        run = self.get_object(request, object_id)
        context = dict(extra_context or {})
        if run is not None:
            definition = get_task_definition(run.task_key)
            context.update(
                {
                    "run_task_name": (
                        definition.name
                        if definition
                        else f"Retired task: {run.task_key}"
                    ),
                    "run_task_description": (
                        definition.description
                        if definition
                        else "No registered executor is available for this task."
                    ),
                    "run_source": self._run_source(run),
                    "run_duration": self._run_duration(run),
                    "run_result_rows": [
                        (
                            result_count_label(key),
                            value,
                        )
                        for key, value in run.result_counts.items()
                    ],
                }
            )
        return super().change_view(request, object_id, form_url, context)

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

    @staticmethod
    def _run_source(run):
        if run.trigger == MaintenanceTaskRun.Trigger.ADMIN:
            return (
                f"Run now by {run.requested_by}"
                if run.requested_by is not None
                else "Run now by a former user"
            )
        return "Scheduled maintenance"

    @staticmethod
    def _run_duration(run):
        if run.started_at is None or run.completed_at is None:
            return None
        seconds = (run.completed_at - run.started_at).total_seconds()
        return f"{seconds:.2f} seconds"
