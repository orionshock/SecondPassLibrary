import json

from django import forms
from django.contrib import admin
from django.contrib.admin import DateFieldListFilter
from django.contrib.admin.utils import quote
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html

from core.admin_widgets import UserRelatedViewOnlyControlsMixin

from .models import HIGHLIGHT_COLOR_TOKENS, Annotation, ReadingProgress, ReadingSession


def _short_id(value) -> str:
    return str(value)[:8]


HIGHLIGHT_COLOR_CHOICES = [("", "---------")] + [
    (token, token.title()) for token in sorted(HIGHLIGHT_COLOR_TOKENS)
]


class AnnotationAdminForm(forms.ModelForm):
    highlight_color = forms.ChoiceField(
        choices=HIGHLIGHT_COLOR_CHOICES,
        required=False,
        help_text="Semantic highlight color token. Highlights default to yellow when blank.",
    )

    class Meta:
        model = Annotation
        fields = "__all__"


class AnnotationInline(admin.TabularInline):
    model = Annotation
    template = "admin/reading/readingsession/edit_inline/annotations_tabular.html"
    extra = 0
    fields = [
        "kind_display",
        "annotation_link",
        "created_at",
        "updated_at",
    ]
    readonly_fields = fields
    can_delete = True
    show_change_link = False

    @admin.display(description="Kind")
    def kind_display(self, obj: Annotation) -> str:
        return obj.get_anchor_kind_display()

    @admin.display(description="ID")
    def annotation_link(self, obj: Annotation) -> str:
        if obj.pk is None:
            return ""
        try:
            url = reverse("admin:reading_annotation_change", args=[obj.pk])
        except NoReverseMatch:
            url = f"/admin/reading/annotation/{quote(obj.pk)}/change/"
        return format_html('<a href="{}">{}</a>', url, _short_id(obj.pk))

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("book", "book_file")
            .order_by("-created_at")
        )


class ReadingProgressInline(admin.StackedInline):
    model = ReadingProgress
    extra = 0
    max_num = 1
    can_delete = False
    fields = [
        "progression",
        "current_location_summary",
        "profile_version",
        "created_at",
        "updated_at",
    ]
    readonly_fields = fields

    @admin.display(description="Current location")
    def current_location_summary(self, obj: ReadingProgress) -> str:
        if not obj.current_location:
            return "No location recorded"
        summary = json.dumps(
            obj.current_location,
            sort_keys=True,
            separators=(",", ": "),
        )
        if len(summary) > 200:
            return f"{summary[:199]}..."
        return summary

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReadingSession)
class ReadingSessionAdmin(UserRelatedViewOnlyControlsMixin, admin.ModelAdmin):
    list_display = [
        "short_session_id",
        "session_label",
        "user",
        "book",
        "status",
        "is_active",
        "created_at",
        "updated_at",
    ]
    search_fields = [
        "id",
        "book__title",
        "book__authors__name",
        "user__username",
        "user__email",
        "name",
    ]
    list_filter = [
        "status",
        "is_active",
        ("created_at", DateFieldListFilter),
        ("updated_at", DateFieldListFilter),
        ("started_at", DateFieldListFilter),
        ("completed_at", DateFieldListFilter),
    ]
    readonly_fields = ["id", "created_at", "updated_at", "started_at"]
    autocomplete_fields = ["user", "book"]
    fields = [
        "name",
        "id",
        "user",
        "book",
        "status",
        "is_active",
        "notes",
        "completed_at",
        "created_at",
        "updated_at",
        "started_at",
    ]
    inlines = [ReadingProgressInline, AnnotationInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "book")

    @admin.display(description="ID", ordering="id")
    def short_session_id(self, obj: ReadingSession) -> str:
        return _short_id(obj.pk)

    @admin.display(description="Session", ordering="name")
    def session_label(self, obj: ReadingSession) -> str:
        return obj.name.strip() if obj.name else "Unnamed session"


@admin.register(ReadingProgress)
class ReadingProgressAdmin(admin.ModelAdmin):
    list_display = ["session", "progression", "updated_at"]
    search_fields = ["session__book__title", "session__user__username"]
    list_filter = [("updated_at", DateFieldListFilter)]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Annotation)
class AnnotationAdmin(admin.ModelAdmin):
    form = AnnotationAdminForm
    list_display = [
        "short_annotation_id",
        "session_user",
        "short_session_id",
        "motivation",
        "created_at",
    ]
    search_fields = [
        "id",
        "session__book__title",
        "session__user__username",
    ]
    list_filter = ["motivation", "is_deleted", ("created_at", DateFieldListFilter)]
    readonly_fields = ["created_at", "updated_at"]

    @admin.display(description="ID", ordering="id")
    def short_annotation_id(self, obj: Annotation) -> str:
        return _short_id(obj.pk)

    @admin.display(description="User", ordering="session__user__username")
    def session_user(self, obj: Annotation) -> str:
        return obj.session.user.get_username()

    @admin.display(description="Session ID", ordering="session__id")
    def short_session_id(self, obj: Annotation) -> str:
        return _short_id(obj.session_id)
