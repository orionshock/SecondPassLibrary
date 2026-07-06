from django import forms
from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError

from .models import (
    ClientLoginRequest,
    ExternalIdentity,
    UserClientSession,
    UserProfile,
    UserWebSession,
)


UNUSED_AUTH_USER_FIELDS = {"groups", "user_permissions"}


def _without_unused_auth_user_fields(fields):
    return tuple(field for field in fields if field not in UNUSED_AUTH_USER_FIELDS)


def _fieldsets_without_unused_auth_user_fields(fieldsets):
    cleaned = []
    for title, options in fieldsets:
        updated = dict(options)
        updated["fields"] = _without_unused_auth_user_fields(updated.get("fields", ()))
        cleaned.append((title, updated))
    return tuple(cleaned)


class SecondPassUserAdmin(DjangoUserAdmin):
    filter_horizontal = _without_unused_auth_user_fields(
        DjangoUserAdmin.filter_horizontal
    )
    list_filter = _without_unused_auth_user_fields(DjangoUserAdmin.list_filter)

    def get_fieldsets(self, request, obj=None):
        return _fieldsets_without_unused_auth_user_fields(
            super().get_fieldsets(request, obj=obj)
        )


try:
    admin.site.unregister(Group)
except NotRegistered:
    pass

try:
    admin.site.unregister(User)
except NotRegistered:
    pass
admin.site.register(User, SecondPassUserAdmin)


class UserProfileAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

    def clean_role(self):
        new_role = self.cleaned_data.get("role")
        request = self.request
        if request is None:
            return new_role

        if request.user.is_superuser:
            return new_role

        instance: UserProfile = self.instance
        old_role = instance.role if instance and instance.pk else None

        # Non-owners cannot promote to manager or demote an existing manager.
        if new_role == UserProfile.ROLE_MANAGER:
            raise ValidationError("Only the Owner can assign the Manager role.")
        if (
            old_role == UserProfile.ROLE_MANAGER
            and new_role != UserProfile.ROLE_MANAGER
        ):
            raise ValidationError("Only the Owner can change a Manager's role.")

        return new_role

    class Meta:
        model = UserProfile
        fields = "__all__"


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    form = UserProfileAdminForm
    list_display = [
        "username",
        "profile_id",
        "role",
        "external_subject_id",
        "created_at",
    ]
    list_display_links = ["username"]
    search_fields = ["user__username", "user__email", "external_subject_id"]
    list_filter = ["role"]
    readonly_fields = [
        "profile_id",
        "external_subject_id",
        "created_at",
        "updated_at",
    ]
    list_select_related = ["user"]

    @admin.display(ordering="user__username", description="Username")
    def username(self, obj: UserProfile):
        return obj.user.get_username()

    @admin.display(description="Profile ID")
    def profile_id(self, obj: UserProfile):
        return obj.id

    def get_form(self, request, obj=None, **kwargs):
        Form = super().get_form(request, obj, **kwargs)

        class RequestForm(Form):
            def __init__(self, *args, **inner_kwargs):
                inner_kwargs["request"] = request
                super().__init__(*args, **inner_kwargs)

        return RequestForm


@admin.register(ExternalIdentity)
class ExternalIdentityAdmin(admin.ModelAdmin):
    list_display = [
        "provider",
        "issuer",
        "subject",
        "user",
        "email_at_login",
        "email_verified",
        "last_seen_at",
    ]
    search_fields = [
        "provider",
        "issuer",
        "subject",
        "user__username",
        "user__email",
        "email_at_login",
    ]
    list_filter = ["provider", "email_verified"]
    readonly_fields = [
        "id",
        "user",
        "provider",
        "issuer",
        "subject",
        "email_at_login",
        "email_verified",
        "selected_claims",
        "last_seen_at",
        "created_at",
        "updated_at",
    ]
    list_select_related = ["user"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj=obj)


@admin.register(UserWebSession)
class UserWebSessionAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "session_key",
        "ip_address",
        "short_user_agent",
        "created_at",
        "updated_at",
    ]
    search_fields = [
        "user__username",
        "user__email",
        "session_key",
        "ip_address",
        "user_agent",
    ]
    readonly_fields = [
        "user",
        "session_key",
        "user_agent",
        "ip_address",
        "created_at",
        "updated_at",
    ]
    list_select_related = ["user"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def short_user_agent(self, obj: UserWebSession):
        ua = obj.user_agent or ""
        if len(ua) <= 80:
            return ua
        return f"{ua[:77]}..."

    short_user_agent.short_description = "User agent"


@admin.register(ClientLoginRequest)
class ClientLoginRequestAdmin(admin.ModelAdmin):
    list_display = [
        "client_name",
        "client_type",
        "status",
        "approved_by",
        "expires_at",
        "approved_at",
        "consumed_at",
        "created_at",
    ]
    search_fields = [
        "client_name",
        "client_type",
        "approved_by__username",
        "approved_by__email",
    ]
    list_filter = ["status", "client_type"]
    readonly_fields = [
        "id",
        "code_hash",
        "client_name",
        "client_type",
        "status",
        "approved_by",
        "expires_at",
        "approved_at",
        "consumed_at",
        "request_user_agent",
        "request_ip",
        "created_at",
        "updated_at",
    ]
    list_select_related = ["approved_by"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(UserClientSession)
class UserClientSessionAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "name",
        "client_type",
        "last_seen_at",
        "expires_at",
        "revoked_at",
        "created_at",
    ]
    search_fields = ["user__username", "user__email", "name", "client_type"]
    list_filter = ["client_type", "revoked_at"]
    readonly_fields = [
        "id",
        "user",
        "name",
        "client_type",
        "token_hash",
        "last_seen_at",
        "expires_at",
        "revoked_at",
        "created_at",
        "updated_at",
    ]
    list_select_related = ["user"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
