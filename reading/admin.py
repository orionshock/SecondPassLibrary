from django.contrib import admin
from django.contrib.admin import DateFieldListFilter

from .models import Annotation, Device, ReadingProgress, ReadingSession


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "device_type",
        "user",
        "last_seen_at",
        "is_active",
        "updated_at",
    ]
    search_fields = ["name", "user__username", "user__email"]
    list_filter = ["device_type", "is_active", ("updated_at", DateFieldListFilter)]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ReadingSession)
class ReadingSessionAdmin(admin.ModelAdmin):
    list_display = ["book", "user", "status", "is_active", "started_at", "completed_at"]
    search_fields = [
        "book__title",
        "book__authors__name",
        "user__username",
        "user__email",
        "name",
    ]
    list_filter = ["status", "is_active", ("started_at", DateFieldListFilter)]
    readonly_fields = ["created_at", "updated_at", "started_at"]


@admin.register(ReadingProgress)
class ReadingProgressAdmin(admin.ModelAdmin):
    list_display = ["session", "device", "progression", "updated_at"]
    search_fields = ["session__book__title", "session__user__username", "device__name"]
    list_filter = [("updated_at", DateFieldListFilter)]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Annotation)
class AnnotationAdmin(admin.ModelAdmin):
    list_display = ["kind", "session", "device", "is_deleted", "created_at"]
    search_fields = [
        "session__book__title",
        "session__user__username",
        "selected_text",
        "note",
        "device__name",
    ]
    list_filter = ["kind", "is_deleted", ("created_at", DateFieldListFilter)]
    readonly_fields = ["created_at", "updated_at"]
