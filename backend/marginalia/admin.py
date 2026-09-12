from functools import partial

from django.contrib import admin
from django.contrib.admin import DateFieldListFilter
from django import forms
from django.db import transaction
from django.db.models import Count
from django.forms.formsets import DELETION_FIELD_NAME
from django.forms.models import BaseInlineFormSet
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from marginalia.annotations import services as annotation_services
from marginalia.imports.staging import (
    ImportStageStorageError,
    delete_stage_file,
    stage_file_path,
)
from marginalia.models import Annotation, ImportStage, ReadingSession


def _bounded_preview(value, *, limit=100):
    preview = " ".join(str(value or "").split())
    return preview if len(preview) <= limit else f"{preview[: limit - 3]}..."


class SessionAnnotationForm(forms.ModelForm):
    soft_delete = forms.BooleanField(
        required=False,
        label="Soft delete",
        help_text="Store the existing tombstone; the Annotation row remains.",
    )

    class Meta:
        model = Annotation
        fields = []


class SessionAnnotationFormSet(BaseInlineFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)
        if DELETION_FIELD_NAME in form.fields:
            form.fields[DELETION_FIELD_NAME].label = "Hard delete permanently"


class SessionAnnotationInline(admin.TabularInline):
    model = Annotation
    form = SessionAnnotationForm
    formset = SessionAnnotationFormSet
    template = "admin/edit_inline/contextual_tabular.html"
    fields = [
        "annotation_link",
        "quote_preview",
        "note_preview",
        "location_label",
        "deleted_state",
        "updated_at",
        "soft_delete",
    ]
    readonly_fields = [
        "annotation_link",
        "quote_preview",
        "note_preview",
        "location_label",
        "deleted_state",
        "updated_at",
    ]
    extra = 0
    verbose_name = "Annotation"
    verbose_name_plural = "Annotations — soft delete keeps a tombstone; hard delete is permanent"

    def get_queryset(self, request):
        return super().get_queryset(request).order_by("-created_at", "-id")

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="Annotation")
    def annotation_link(self, obj):
        url = reverse("admin:marginalia_annotation_change", args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.get_kind_display())

    @admin.display(description="Quote")
    def quote_preview(self, obj):
        return _bounded_preview(obj.highlight_text) or "-"

    @admin.display(description="Note")
    def note_preview(self, obj):
        return _bounded_preview(obj.comment_text) or "-"

    @admin.display(description="State")
    def deleted_state(self, obj):
        if obj.is_deleted:
            return format_html('<strong class="errornote">{}</strong>', "Deleted")
        return format_html("<span>{}</span>", "")


@admin.register(ReadingSession)
class ReadingSessionAdmin(admin.ModelAdmin):
    list_display = [
        "user_account",
        "book",
        "display_name",
        "status",
        "started_at",
        "closed_at",
        "updated_at",
        "has_progress",
        "annotation_count",
    ]
    list_display_links = ["display_name"]
    list_filter = [
        ("user", admin.RelatedOnlyFieldListFilter),
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
    inlines = [SessionAnnotationInline]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("user", "book")
            .annotate(_admin_annotation_count=Count("annotations"))
        )

    @admin.display(description="User", ordering="user__username")
    def user_account(self, obj):
        url = reverse("admin:auth_user_change", args=[obj.user_id])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_username())

    @admin.display(description="Session", ordering="name")
    def display_name(self, obj: ReadingSession) -> str:
        return obj.name.strip() if obj.name else "Unnamed Session"

    @admin.display(description="Progress", boolean=True, ordering="progress_cfi")
    def has_progress(self, obj: ReadingSession) -> bool:
        return bool(obj.progress_cfi)

    @admin.display(description="Annotations", ordering="_admin_annotation_count")
    def annotation_count(self, obj: ReadingSession) -> int:
        return obj._admin_annotation_count

    def save_formset(self, request, form, formset, change):
        if formset.model is not Annotation:
            return super().save_formset(request, form, formset, change)

        formset.save(commit=False)
        hard_delete_ids = {obj.pk for obj in formset.deleted_objects}
        soft_delete_ids = {
            inline_form.instance.pk
            for inline_form in formset.forms
            if inline_form.cleaned_data.get("soft_delete")
            and not inline_form.cleaned_data.get(DELETION_FIELD_NAME)
        }
        soft_deleted = annotation_services.soft_delete_annotations(
            session=form.instance,
            annotation_ids=soft_delete_ids,
            actor=request.user,
        )
        hard_deleted = annotation_services.hard_delete_annotations(
            session=form.instance,
            annotation_ids=hard_delete_ids,
            actor=request.user,
        )
        formset.save_m2m()
        if soft_deleted or hard_deleted:
            self.message_user(
                request,
                f"Soft deleted {soft_deleted} "
                f"{'annotation' if soft_deleted == 1 else 'annotations'}; "
                f"permanently deleted {hard_deleted} "
                f"{'annotation' if hard_deleted == 1 else 'annotations'}.",
            )


@admin.register(Annotation)
class AnnotationAdmin(admin.ModelAdmin):
    # Registered only to preserve direct Annotation change forms linked from
    # Reading Sessions. Keep it hidden from the global Admin index/changelist UI.
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
        ("session__user", admin.RelatedOnlyFieldListFilter),
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
        ("Deletion", {"fields": ["is_deleted", "deleted_at"]}),
        ("Record timestamps", {"fields": ["created_at", "updated_at"]}),
    ]
    date_hierarchy = "updated_at"
    list_per_page = 50

    def get_readonly_fields(self, request, obj=None):
        return [*self.readonly_fields, "deleted_at"]

    def save_model(self, request, obj, form, change):
        previous = (
            Annotation.objects.filter(pk=obj.pk)
            .values("is_deleted", "deleted_at")
            .first()
            if change
            else None
        )
        was_deleted = bool(previous and previous["is_deleted"])
        if obj.is_deleted and not was_deleted:
            obj.deleted_at = timezone.now()
        elif not obj.is_deleted:
            obj.deleted_at = None
        super().save_model(request, obj, form, change)

    def get_model_perms(self, request):
        return {}

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
