from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError

from .models import UserProfile, UserWebSession


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
        if old_role == UserProfile.ROLE_MANAGER and new_role != UserProfile.ROLE_MANAGER:
            raise ValidationError("Only the Owner can change a Manager's role.")

        return new_role

    class Meta:
        model = UserProfile
        fields = "__all__"


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    form = UserProfileAdminForm
    list_display = ["user", "role", "external_subject_id", "created_at"]
    search_fields = ["user__username", "user__email", "external_subject_id"]
    list_filter = ["role"]
    readonly_fields = ["created_at", "updated_at"]

    def get_form(self, request, obj=None, **kwargs):
        Form = super().get_form(request, obj, **kwargs)

        class RequestForm(Form):
            def __init__(self, *args, **inner_kwargs):
                inner_kwargs["request"] = request
                super().__init__(*args, **inner_kwargs)

        return RequestForm


@admin.register(UserWebSession)
class UserWebSessionAdmin(admin.ModelAdmin):
    list_display = ["user", "session_key", "ip_address", "short_user_agent", "created_at", "updated_at"]
    search_fields = ["user__username", "user__email", "session_key", "ip_address", "user_agent"]
    readonly_fields = ["user", "session_key", "user_agent", "ip_address", "created_at", "updated_at"]
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
