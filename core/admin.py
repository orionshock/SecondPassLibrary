from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from library.groups.consolidation import (
    AdvancedGroupsConsolidationError,
    AdvancedGroupsConsolidationNotNeeded,
    AdvancedGroupsPlanStale,
    build_advanced_groups_disable_plan,
    execute_advanced_groups_disable_plan,
)
from . import server_settings
from .models import ServerSetting


class ServerSettingAdminForm(forms.ModelForm):
    class Meta:
        model = ServerSetting
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk:
            return cleaned
        if self.instance.key != server_settings.ADVANCED_LIBRARY_GROUPS_SETTING:
            return cleaned

        old = ServerSetting.objects.get(pk=self.instance.pk)
        new_value = cleaned.get("value")
        if old.value is True and new_value is not True:
            raise forms.ValidationError(
                "Use the advanced library groups recovery flow to disable this setting."
            )
        return cleaned


class AdvancedGroupsDisableAdminForm(forms.Form):
    fingerprint = forms.CharField(widget=forms.HiddenInput)
    confirm = forms.BooleanField(
        required=True,
        label=(
            "I understand this deletes custom group containers, memberships, "
            "curator assignments, and non-Public book associations."
        ),
    )
    confirmation_text = forms.CharField(
        label='Type "DISABLE ADVANCED GROUPS"',
        max_length=32,
    )

    def clean_confirmation_text(self):
        value = str(self.cleaned_data.get("confirmation_text") or "").strip()
        if value != "DISABLE ADVANCED GROUPS":
            raise forms.ValidationError("Confirmation text does not match.")
        return value


@admin.register(ServerSetting)
class ServerSettingAdmin(admin.ModelAdmin):
    form = ServerSettingAdminForm
    list_display = ["key", "updated_at"]
    search_fields = ["key", "description"]
    readonly_fields = ["key", "created_at", "updated_at"]

    def _is_advanced_groups_setting(self, obj) -> bool:
        return (
            obj is not None
            and obj.key == server_settings.ADVANCED_LIBRARY_GROUPS_SETTING
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "advanced-groups-disable/",
                self.admin_site.admin_view(self.advanced_groups_disable_view),
                name="core_serversetting_advanced_groups_disable",
            ),
        ]
        return custom_urls + urls

    def get_fieldsets(self, request, obj=None):
        if self._is_advanced_groups_setting(obj):
            return (
                (
                    "Advanced library groups",
                    {
                        "fields": (
                            "advanced_groups_status",
                            "advanced_groups_recovery_summary",
                            "advanced_groups_recovery_link",
                        )
                    },
                ),
                (
                    "Database metadata",
                    {"classes": ("collapse",), "fields": ("key", "created_at", "updated_at")},
                ),
            )
        return super().get_fieldsets(request, obj=obj)

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj=obj))
        if self._is_advanced_groups_setting(obj):
            fields.extend(
                [
                    "value",
                    "description",
                    "advanced_groups_status",
                    "advanced_groups_recovery_summary",
                    "advanced_groups_recovery_link",
                ]
            )
        return list(dict.fromkeys(fields))

    def has_delete_permission(self, request, obj=None):
        if self._is_advanced_groups_setting(obj):
            return False
        return super().has_delete_permission(request, obj=obj)

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        if self._is_advanced_groups_setting(obj):
            context.update(
                {
                    "show_save": False,
                    "show_save_and_add_another": False,
                    "show_save_and_continue": False,
                    "show_delete": False,
                }
            )
        return super().render_change_form(
            request,
            context,
            add=add,
            change=change,
            form_url=form_url,
            obj=obj,
        )

    @admin.display(description="Current status")
    def advanced_groups_status(self, obj):
        return "Enabled" if obj.value is True else "Disabled"

    @admin.display(description="Recovery guidance")
    def advanced_groups_recovery_summary(self, obj):
        return format_html(
            "<strong>{}</strong> "
            "Product UI can enable advanced groups, but disabling after use must "
            "run the recovery flow so custom group shelves, books, users, and "
            "containers are consolidated safely into Public Library.",
            "Do not edit this database setting directly.",
        )

    @admin.display(description="Recovery action")
    def advanced_groups_recovery_link(self, obj):
        if obj.key != server_settings.ADVANCED_LIBRARY_GROUPS_SETTING:
            return ""
        url = reverse("admin:core_serversetting_advanced_groups_disable")
        return format_html('<a href="{}">Disable and consolidate into Public Library</a>', url)

    def advanced_groups_disable_view(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied

        plan = build_advanced_groups_disable_plan(display_limit=100)
        if request.method == "POST":
            form = AdvancedGroupsDisableAdminForm(request.POST)
            if form.is_valid():
                try:
                    result = execute_advanced_groups_disable_plan(
                        actor=request.user,
                        expected_fingerprint=form.cleaned_data["fingerprint"],
                    )
                except AdvancedGroupsPlanStale as exc:
                    messages.error(request, str(exc))
                    plan = build_advanced_groups_disable_plan(display_limit=100)
                    form = AdvancedGroupsDisableAdminForm(
                        initial={"fingerprint": plan.fingerprint}
                    )
                except AdvancedGroupsConsolidationNotNeeded as exc:
                    messages.info(request, str(exc))
                    return HttpResponseRedirect(reverse("admin:core_serversetting_changelist"))
                except AdvancedGroupsConsolidationError as exc:
                    messages.error(request, f"Recovery failed: {exc}")
                    plan = build_advanced_groups_disable_plan(display_limit=100)
                    form = AdvancedGroupsDisableAdminForm(
                        initial={"fingerprint": plan.fingerprint}
                    )
                else:
                    messages.success(
                        request,
                        "Advanced library groups disabled and consolidated into Public Library.",
                    )
                    return self._advanced_groups_completion_response(request, result)
        else:
            form = AdvancedGroupsDisableAdminForm(initial={"fingerprint": plan.fingerprint})

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Disable advanced library groups and consolidate into Public Library",
            "plan": plan,
            "form": form,
            "display_limit": 100,
        }
        return TemplateResponse(
            request,
            "admin/core/serversetting/advanced_groups_disable.html",
            context,
        )

    def _advanced_groups_completion_response(self, request, result):
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Advanced library groups disabled",
            "result": result,
            "plan": result.plan,
            "summary": result.summary,
        }
        return TemplateResponse(
            request,
            "admin/core/serversetting/advanced_groups_disable_complete.html",
            context,
        )
