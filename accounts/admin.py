from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "external_subject_id", "created_at"]
    search_fields = ["user__username", "user__email", "external_subject_id"]
    list_filter = ["role"]
    readonly_fields = ["created_at", "updated_at"]
