from django import forms
from django.contrib import admin, messages
from django.contrib.admin.widgets import AutocompleteSelect
from django.core.exceptions import ValidationError
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from library.groups.public_group import (
    PUBLIC_GROUP_ID_SETTING,
    get_public_group_id,
)
from library.models import LibraryGroup
from library.models import BookGroupAssignment
from library.groups.public_services import repair_public_group_identity, set_public_group_identity
from library.groups.consolidation import (
    AdvancedGroupsConsolidationError,
    AdvancedGroupsConsolidationNotNeeded,
    AdvancedGroupsPlanStale,
    build_advanced_groups_disable_plan,
    execute_advanced_groups_disable_plan,
)
from . import server_settings
from .admin_menu import install_admin_menu
from .models import ServerSetting


class ServerIdentityAdminForm(forms.ModelForm):
    server_name = forms.CharField(
        label="Server Name",
        help_text="Display name used in Product UI and discovery.",
        max_length=server_settings.SERVER_NAME_MAX_LEN,
        widget=forms.TextInput(attrs={"size": 80}),
    )
    server_description = forms.CharField(
        label="Server Description",
        help_text=(
            "Sanitized limited HTML used in discovery and server identity. "
            "Links, images, attributes, and arbitrary HTML are removed."
        ),
        required=False,
        max_length=server_settings.SERVER_DESCRIPTION_MAX_LEN,
        widget=forms.Textarea(attrs={"rows": 4, "cols": 100}),
    )
    server_banner_message = forms.CharField(
        label="Server Banner Message",
        help_text=(
            "Sanitized limited HTML shown in Product UI. Links, images, "
            "attributes, and arbitrary HTML are removed."
        ),
        required=False,
        max_length=server_settings.SERVER_BANNER_MESSAGE_MAX_LEN,
        widget=forms.Textarea(attrs={"rows": 3, "cols": 100}),
    )

    class Meta:
        model = ServerSetting
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial.update(
            {
                "server_name": server_settings.get_server_name(),
                "server_description": server_settings.get_server_description(),
                "server_banner_message": server_settings.get_server_banner_message(),
            }
        )


class ServerSettingAdminForm(forms.ModelForm):
    admin_site = None
    confirm_public_reassignment = forms.BooleanField(
        required=False,
        label="Confirm Public/Common Room reassignment",
        help_text=(
            "The selected LibraryGroup becomes the protected Public/Common Room "
            "identity. The former Public group remains an ordinary group."
        ),
    )

    class Meta:
        model = ServerSetting
        fields = ["value"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._configure_value_field()

    def _configure_value_field(self):
        value = self.instance.value if self.instance and self.instance.pk else None
        key = self.instance.key if self.instance and self.instance.pk else ""
        if key != PUBLIC_GROUP_ID_SETTING:
            self.fields.pop("confirm_public_reassignment", None)

        if key == server_settings.APPLICATION_LOG_LEVEL_SETTING:
            self.fields["value"] = forms.ChoiceField(
                label="Application Log Level",
                help_text=(
                    "Controls diagnostic output from Second Pass Library application "
                    "code. INFO is recommended for normal operation; use DEBUG "
                    "temporarily when diagnosing a problem."
                ),
                choices=[(level, level) for level in server_settings.APPLICATION_LOG_LEVELS],
                initial=value,
            )
            return

        if key == server_settings.SECOND_PASS_READER_WEB_CLIENT_URL_SETTING:
            self.fields["value"] = forms.CharField(
                label="Second Pass Reader Web Client URL",
                help_text=(
                    "Enter an absolute http or https URL. Only its scheme, host, "
                    "and optional port are stored; path, query, and fragment are removed."
                ),
                required=False,
                max_length=server_settings.SECOND_PASS_READER_WEB_CLIENT_URL_MAX_LEN,
                disabled=server_settings.second_pass_reader_web_client_url_locked(),
                widget=forms.URLInput(attrs={"size": 80}),
                initial=value,
            )
            return

        if key == PUBLIC_GROUP_ID_SETTING:
            group_field = BookGroupAssignment._meta.get_field("group")
            self.fields["value"] = forms.ModelChoiceField(
                label="Public/Common Room Group",
                help_text="Select the LibraryGroup that should hold the protected Public identity.",
                queryset=LibraryGroup.objects.order_by("name"),
                required=True,
                widget=AutocompleteSelect(group_field, self.admin_site),
                initial=value,
            )
            return

        self.fields.pop("confirm_public_reassignment", None)

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk:
            return cleaned
        if self.instance.key == PUBLIC_GROUP_ID_SETTING:
            selected_id = str(cleaned.get("value") or "")
            selected = LibraryGroup.objects.filter(pk=selected_id).first()
            if selected is not None and selected.memberships.filter(
                is_curator=True
            ).exists():
                self.add_error(
                    "value",
                    "Remove curator memberships before selecting this group as Public.",
                )
            if (
                selected_id
                and selected_id != str(self.instance.value)
                and not cleaned.get("confirm_public_reassignment")
            ):
                self.add_error(
                    "confirm_public_reassignment",
                    "Confirm the Public/Common Room reassignment.",
                )
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

    def clean_value(self):
        value = self.cleaned_data["value"]
        if self.instance.key == PUBLIC_GROUP_ID_SETTING:
            return str(value.pk)
        if (
            self.instance.key
            == server_settings.SECOND_PASS_READER_WEB_CLIENT_URL_SETTING
        ):
            try:
                return server_settings.normalize_second_pass_reader_web_client_url(value)
            except ValueError as exc:
                raise forms.ValidationError(str(exc)) from exc
        return value

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


class PublicGroupRepairAdminForm(forms.Form):
    create_new_common_room = forms.BooleanField(
        required=False,
        label="Create a new Common Room",
        help_text=(
            "When selected, create a fresh protected Common Room and make it the "
            "Public identity. Otherwise repair using the currently configured group."
        ),
    )


@admin.register(ServerSetting)
class ServerSettingAdmin(admin.ModelAdmin):
    form = ServerSettingAdminForm
    list_display = ["display_key", "operator_value", "operator_purpose", "updated_at"]
    search_fields = ["key", "description"]
    readonly_fields = ["key", "description", "created_at", "updated_at"]
    actions = None

    def has_add_permission(self, request):
        return False

    def _is_advanced_groups_setting(self, obj) -> bool:
        return (
            obj is not None
            and obj.key == server_settings.ADVANCED_LIBRARY_GROUPS_SETTING
        )

    @staticmethod
    def _is_server_identity_setting(obj) -> bool:
        return obj is not None and obj.key == server_settings.SERVER_NAME_SETTING

    @staticmethod
    def _is_public_group_setting(obj) -> bool:
        return obj is not None and obj.key == PUBLIC_GROUP_ID_SETTING

    @staticmethod
    def _is_structural_setting(obj) -> bool:
        return bool(
            obj is not None
            and (
                obj.key in server_settings.EDITABLE_SERVER_SETTING_DEFAULTS
                or obj.key == PUBLIC_GROUP_ID_SETTING
            )
        )

    @admin.display(description="Key", ordering="key")
    def display_key(self, obj):
        return obj.display_key

    @admin.display(description="Configured value or status")
    def operator_value(self, obj):
        if self._is_advanced_groups_setting(obj):
            return "Enabled" if obj.value is True else "Disabled"
        if self._is_public_group_setting(obj):
            group = _configured_public_group()
            return group.name if group is not None else "Identity needs repair"
        return obj.value

    @admin.display(description="Operator purpose")
    def operator_purpose(self, obj):
        return _setting_operator_copy(obj.key)

    def get_queryset(self, request):
        server_settings.ensure_editable_server_settings()
        return super().get_queryset(request).exclude(
            key__in={
                server_settings.SERVER_DESCRIPTION_SETTING,
                server_settings.SERVER_BANNER_MESSAGE_SETTING,
                server_settings.MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
                server_settings.MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
            }
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "advanced-groups-disable/",
                self.admin_site.admin_view(self.advanced_groups_disable_view),
                name="core_serversetting_advanced_groups_disable",
            ),
            path(
                "public-group-repair/",
                self.admin_site.admin_view(self.public_group_repair_view),
                name="core_serversetting_public_group_repair",
            ),
        ]
        return custom_urls + urls

    def get_fieldsets(self, request, obj=None):
        if self._is_server_identity_setting(obj):
            return (
                (
                    "Server identity and banner",
                    {
                        "fields": (
                            "server_name",
                            "server_description",
                            "server_banner_message",
                        )
                    },
                ),
                (
                    "Database metadata",
                    {
                        "classes": ("collapse",),
                        "fields": ("created_at", "updated_at"),
                    },
                ),
            )
        if self._is_advanced_groups_setting(obj):
            status_fields = ["advanced_groups_status"]
            if obj is not None and obj.value is True:
                status_fields.extend(
                    [
                        "advanced_groups_recovery_summary",
                        "advanced_groups_recovery_link",
                    ]
                )
            return (
                (
                    "Advanced library groups",
                    {"fields": tuple(status_fields)},
                ),
                (
                    "Database metadata",
                    {
                        "classes": ("collapse",),
                        "fields": ("created_at", "updated_at"),
                    },
                ),
            )
        if self._is_public_group_setting(obj):
            return (
                (
                    "Public/Common Room Group",
                    {
                        "fields": (
                            "value",
                            "confirm_public_reassignment",
                            "public_group_guidance",
                            "public_group_recovery_link",
                        )
                    },
                ),
                (
                    "Database metadata",
                    {
                        "classes": ("collapse",),
                        "fields": ("created_at", "updated_at"),
                    },
                ),
            )
        return (
            (
                None,
                {
                    "fields": (
                        "value",
                        "created_at",
                        "updated_at",
                    )
                },
            ),
        )

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
        if self._is_public_group_setting(obj):
            fields.extend(
                [
                    "description",
                    "public_group_guidance",
                    "public_group_recovery_link",
                ]
            )
        return list(dict.fromkeys(fields))

    def get_form(self, request, obj=None, change=False, **kwargs):
        if self._is_server_identity_setting(obj):
            return ServerIdentityAdminForm
        form = super().get_form(request, obj=obj, change=change, **kwargs)
        form.admin_site = self.admin_site
        return form

    def has_delete_permission(self, request, obj=None):
        if self._is_structural_setting(obj):
            return False
        return super().has_delete_permission(request, obj=obj)

    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None
    ):
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

    def save_model(self, request, obj, form, change):
        if self._is_server_identity_setting(obj):
            server_settings.set_server_identity(
                name=form.cleaned_data["server_name"],
                description=form.cleaned_data["server_description"],
                banner_message=form.cleaned_data["server_banner_message"],
            )
            return
        if obj.key == server_settings.SECOND_PASS_READER_WEB_CLIENT_URL_SETTING:
            if not server_settings.second_pass_reader_web_client_url_locked():
                server_settings.set_second_pass_reader_web_client_url(obj.value)
            return
        if self._is_public_group_setting(obj):
            try:
                group = LibraryGroup.objects.get(pk=obj.value)
                selected = set_public_group_identity(group=group)
            except (LibraryGroup.DoesNotExist, ValidationError) as exc:
                raise forms.ValidationError(str(exc)) from exc
            obj.value = str(selected.pk)
            return
        if obj.key == server_settings.APPLICATION_LOG_LEVEL_SETTING:
            server_settings.set_application_log_level(obj.value)
            return
        super().save_model(request, obj, form, change)

    @admin.display(description="Current status")
    def advanced_groups_status(self, obj):
        return "Enabled" if obj.value is True else "Disabled"

    @admin.display(description="Recovery guidance")
    def advanced_groups_recovery_summary(self, obj):
        return format_html(
            "<strong>{}</strong> "
            "Product UI can enable advanced groups, but disabling after use must "
            "run the recovery flow so custom group shelves, books, users, and "
            "containers are consolidated safely into the configured Public/Common "
            "Room group. That group still uses normal group access control.",
            "Do not edit this database setting directly.",
        )

    @admin.display(description="Recovery action")
    def advanced_groups_recovery_link(self, obj):
        if (
            obj.key != server_settings.ADVANCED_LIBRARY_GROUPS_SETTING
            or obj.value is not True
        ):
            return ""
        url = reverse("admin:core_serversetting_advanced_groups_disable")
        return format_html(
            '<a href="{}">Disable and consolidate into Public/Common Room</a>', url
        )

    @admin.display(description="Identity guidance")
    def public_group_guidance(self, obj):
        return (
            "This is the configured protected Public/Common Room identity. "
            "It remains a normal LibraryGroup for access control. Reassignment "
            "requires explicit confirmation and a group without curators."
        )

    @admin.display(description="Recovery action")
    def public_group_recovery_link(self, obj):
        url = reverse("admin:core_serversetting_public_group_repair")
        return format_html('<a href="{}">Repair Public/Common Room identity</a>', url)

    def public_group_repair_view(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied
        if request.method == "POST":
            form = PublicGroupRepairAdminForm(request.POST)
            if form.is_valid():
                result = repair_public_group_identity(
                    create_new_common_room=form.cleaned_data[
                        "create_new_common_room"
                    ],
                    actor=request.user,
                )
                action = "Created" if result.created_new_group else "Verified"
                messages.success(
                    request,
                    f"{action} Public/Common Room identity as {result.group.name}. "
                    f"Restored {result.users_restored} user(s) and "
                    f"{result.books_restored} book(s) that had no group.",
                )
                return HttpResponseRedirect(
                    reverse("admin:core_serversetting_changelist")
                )
        else:
            form = PublicGroupRepairAdminForm()
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Repair Public/Common Room identity",
            "configured_group": _configured_public_group(),
            "form": form,
        }
        return TemplateResponse(
            request,
            "admin/core/serversetting/public_group_repair.html",
            context,
        )

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
                    return HttpResponseRedirect(
                        reverse("admin:core_serversetting_changelist")
                    )
                except AdvancedGroupsConsolidationError:
                    messages.error(
                        request,
                        "Recovery failed and no changes were committed. "
                        "Review the current state and try again.",
                    )
                    plan = build_advanced_groups_disable_plan(display_limit=100)
                    form = AdvancedGroupsDisableAdminForm(
                        initial={"fingerprint": plan.fingerprint}
                    )
                else:
                    messages.success(
                        request,
                        "Advanced library groups disabled and consolidated into "
                        "the configured Public/Common Room group.",
                    )
                    return self._advanced_groups_completion_response(request, result)
        else:
            form = AdvancedGroupsDisableAdminForm(
                initial={"fingerprint": plan.fingerprint}
            )

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": (
                "Disable advanced library groups and consolidate into "
                "Public/Common Room"
            ),
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


def _configured_public_group():
    group_id = get_public_group_id()
    if group_id is None:
        return None
    return LibraryGroup.objects.filter(pk=group_id).first()


def _setting_operator_copy(key):
    return {
        server_settings.SERVER_NAME_SETTING: (
            "Display name used in Product UI and discovery."
        ),
        server_settings.SERVER_DESCRIPTION_SETTING: (
            "Description used in discovery and server identity."
        ),
        server_settings.SERVER_BANNER_MESSAGE_SETTING: (
            "Banner message shown in Product UI."
        ),
        server_settings.SECOND_PASS_READER_WEB_CLIENT_URL_SETTING: (
            "Canonical base URL used to open Books in the Second Pass Reader web client."
        ),
        server_settings.APPLICATION_LOG_LEVEL_SETTING: (
            "Controls Second Pass Library application diagnostics. INFO is recommended "
            "for normal operation."
        ),
        PUBLIC_GROUP_ID_SETTING: (
            "Configured protected Public/Common Room identity."
        ),
        server_settings.ADVANCED_LIBRARY_GROUPS_SETTING: (
            "Enabled/disabled status with explicit recovery guidance."
        ),
    }.get(key, "Managed server setting.")


install_admin_menu()
