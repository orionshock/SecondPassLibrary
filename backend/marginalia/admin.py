from functools import partial

from django.contrib import admin
from django.contrib.admin import DateFieldListFilter
from django.db import transaction
from django.db.models import Count

from marginalia.imports.staging import (
    ImportStageStorageError,
    delete_stage_file,
    stage_file_path,
)
from marginalia.models import Annotation, ImportStage, ReadingSession


@admin.register(ReadingSession)
class ReadingSessionAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "book",
        "display_name",
        "status",
        "started_at",
        "closed_at",
        "updated_at",
        "has_progress",
        "annotation_count",
    ]
    list_filter = [
        "status",
        ("started_at", DateFieldListFilter),
        ("closed_at", DateFieldListFilter),
        ("updated_at", DateFieldListFilter),
    ]
    search_fields = [
        "=id",
        "name",
        "book__title",
        "user__username",
        "user__email",
    ]
    autocomplete_fields = ["user", "book"]
    readonly_fields = ["id", "started_at", "created_at", "updated_at"]
    fieldsets = [
        (
            "Reading Session",
            {"fields": ["id", "user", "book", "name", "notes", "status"]},
        ),
        ("Lifecycle", {"fields": ["started_at", "closed_at"]}),
        (
            "Saved progress",
            {
                "fields": [
                    "progress_cfi",
                    "progress_location_label",
                    "progress_updated_at",
                ]
            },
        ),
        ("Record timestamps", {"fields": ["created_at", "updated_at"]}),
    ]
    date_hierarchy = "updated_at"
    list_per_page = 50

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("user", "book")
            .annotate(_admin_annotation_count=Count("annotations"))
        )

    @admin.display(description="Session", ordering="name")
    def display_name(self, obj: ReadingSession) -> str:
        return obj.name.strip() if obj.name else "Unnamed Session"

    @admin.display(description="Progress", boolean=True, ordering="progress_cfi")
    def has_progress(self, obj: ReadingSession) -> bool:
        return bool(obj.progress_cfi)

    @admin.display(description="Annotations", ordering="_admin_annotation_count")
    def annotation_count(self, obj: ReadingSession) -> int:
        return obj._admin_annotation_count


@admin.register(Annotation)
class AnnotationAdmin(admin.ModelAdmin):
    list_display = [
        "session",
        "session_user",
        "session_book",
        "kind",
        "client_id",
        "location_label",
        "is_deleted",
        "created_at",
        "updated_at",
    ]
    list_filter = [
        "kind",
        "is_deleted",
        ("created_at", DateFieldListFilter),
        ("updated_at", DateFieldListFilter),
    ]
    search_fields = [
        "=id",
        "=session__id",
        "client_id",
        "location_label",
        "highlight_text",
        "comment_text",
        "session__book__title",
        "session__user__username",
        "session__user__email",
    ]
    autocomplete_fields = ["session"]
    readonly_fields = ["id", "created_at", "updated_at"]
    fieldsets = [
        ("Annotation", {"fields": ["id", "session", "client_id", "kind"]}),
        ("Location", {"fields": ["cfi", "location_label"]}),
        (
            "Highlight body",
            {
                "fields": [
                    "highlight_text",
                    "quote_prefix",
                    "quote_suffix",
                    "highlight_color",
                    "comment_text",
                ]
            },
        ),
        ("Deletion", {"fields": ["is_deleted"]}),
        ("Record timestamps", {"fields": ["created_at", "updated_at"]}),
    ]
    date_hierarchy = "updated_at"
    list_per_page = 50

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "session",
            "session__user",
            "session__book",
        )

    @admin.display(description="User", ordering="session__user__username")
    def session_user(self, obj: Annotation) -> str:
        return obj.session.user.get_username()

    @admin.display(description="Book", ordering="session__book__title")
    def session_book(self, obj: Annotation) -> str:
        return obj.session.book.title


@admin.register(ImportStage)
class ImportStageAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "state",
        "created_at",
        "expires_at",
        "applied_at",
        "include_empty_sessions",
        "preview_book_count",
        "preview_session_count",
        "staged_file_exists",
    ]
    list_filter = [
        "state",
        "include_empty_sessions",
        ("expires_at", DateFieldListFilter),
        ("applied_at", DateFieldListFilter),
    ]
    search_fields = ["=id", "user__username", "user__email"]
    autocomplete_fields = ["user"]
    readonly_fields = ["id", "created_at", "updated_at"]
    fieldsets = [
        ("Stage", {"fields": ["id", "user", "state", "include_empty_sessions"]}),
        (
            "Lifetime",
            {"fields": ["created_at", "updated_at", "expires_at", "applied_at"]},
        ),
        ("Storage", {"fields": ["storage_name"]}),
        ("Token and replay", {"fields": ["token_digest", "request_fingerprint"]}),
        ("Persisted preview", {"fields": ["preview"]}),
        ("Persisted result", {"fields": ["result"]}),
    ]
    date_hierarchy = "expires_at"
    list_per_page = 50

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

    @admin.display(description="Books")
    def preview_book_count(self, obj: ImportStage) -> int:
        return self._preview_summary_count(obj, "book_count")

    @admin.display(description="Sessions")
    def preview_session_count(self, obj: ImportStage) -> int:
        return self._preview_summary_count(obj, "reading_session_count")

    @admin.display(description="File", boolean=True)
    def staged_file_exists(self, obj: ImportStage) -> bool:
        try:
            return stage_file_path(obj.storage_name).is_file()
        except (OSError, ImportStageStorageError):
            return False

    def delete_model(self, request, obj):
        storage_name = obj.storage_name
        super().delete_model(request, obj)
        transaction.on_commit(partial(delete_stage_file, storage_name))

    def delete_queryset(self, request, queryset):
        storage_names = list(queryset.values_list("storage_name", flat=True))
        super().delete_queryset(request, queryset)
        for storage_name in storage_names:
            transaction.on_commit(partial(delete_stage_file, storage_name))

    @staticmethod
    def _preview_summary_count(obj: ImportStage, key: str) -> int:
        summary = obj.preview.get("summary", {}) if isinstance(obj.preview, dict) else {}
        value = summary.get(key, 0) if isinstance(summary, dict) else 0
        return value if isinstance(value, int) and not isinstance(value, bool) else 0
