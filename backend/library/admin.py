from types import MethodType

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.admin.widgets import FilteredSelectMultiple, RelatedFieldWidgetWrapper
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseRedirect
from django.db.models import Count, Prefetch
from django.forms.formsets import DELETION_FIELD_NAME
from django.forms.models import BaseInlineFormSet
from django.utils.html import format_html
from django.template.response import TemplateResponse
from django.urls import path, reverse

from core import server_settings
from library.catalog.description_html import sanitize_book_description
from library.file_repair import (
    ChecksumChangeConfirmationRequired,
    ChecksumCollisionError,
    ReplaceExistingConfirmationRequired,
    StoredEpubRepairError,
    repair_stored_epub,
)
from library.cover_services import (
    InvalidBookCover,
    clear_book_cover,
    replace_book_cover,
    validate_book_cover_upload,
)
from library.catalog.tag_services import (
    CatalogTagMergeError,
    CatalogTagMergeNameConflict,
    CatalogTagMergePlanStale,
    CatalogTagMergeSelectionError,
    available_catalog_tag_slug,
    build_catalog_tag_merge_plan,
    merge_catalog_tags,
    normalize_catalog_tag_name,
    normalize_catalog_tag_sort_name,
)
from library.groups import memberships as membership_services
from library.groups import book_assignments as book_assignment_services
from library.groups.public_group import is_public_group

from .models import (
    Author,
    Book,
    BookAuthor,
    BookCatalogTag,
    BookGroupAssignment,
    BookIdentifier,
    BookSeries,
    CatalogTag,
    LibraryGroup,
    LibraryGroupMembership,
    Series,
)


LIBRARY_ADMIN_MODEL_ORDER = {
    "Book": (10, "Books"),
    "CatalogTag": (20, "Catalog Tags"),
    "LibraryGroup": (30, "Library Groups"),
    "LibraryGroupMembership": (40, "User Group Assignments"),
    "BookGroupAssignment": (50, "Book Group Assignments"),
}


def _install_view_only_related_widget_controls():
    if hasattr(RelatedFieldWidgetWrapper, "_secondpass_original_get_context"):
        return

    RelatedFieldWidgetWrapper._secondpass_original_get_context = (
        RelatedFieldWidgetWrapper.get_context
    )

    def get_context(self, name, value, attrs):
        context = self._secondpass_original_get_context(name, value, attrs)
        context["can_add_related"] = False
        context["can_change_related"] = False
        context["can_delete_related"] = False
        return context

    RelatedFieldWidgetWrapper.get_context = get_context


_install_view_only_related_widget_controls()


def _sort_library_admin_models(app):
    for model in app["models"]:
        configuration = LIBRARY_ADMIN_MODEL_ORDER.get(model["object_name"])
        if configuration is not None:
            model["name"] = configuration[1]
    app["models"].sort(
        key=lambda model: (
            LIBRARY_ADMIN_MODEL_ORDER.get(model["object_name"], (100, ""))[0],
            model["name"],
        )
    )


def _install_library_admin_app_list_ordering():
    if hasattr(admin.site, "_secondpass_library_original_get_app_list"):
        return

    admin.site._secondpass_library_original_get_app_list = admin.site.get_app_list

    def get_app_list(self, request, app_label=None):
        app_list = self._secondpass_library_original_get_app_list(request, None)
        library_app = next(
            (app for app in app_list if app["app_label"] == "library"),
            None,
        )
        if library_app is not None:
            _sort_library_admin_models(library_app)
        if app_label is not None:
            app_list = [app for app in app_list if app["app_label"] == app_label]
        return app_list

    admin.site.get_app_list = MethodType(get_app_list, admin.site)


class StoredEpubRepairAdminForm(forms.Form):
    replacement_epub = forms.FileField(label="Replacement EPUB")
    replace_existing = forms.BooleanField(
        required=False,
        label="Replace existing stored file",
    )
    allow_checksum_change = forms.BooleanField(
        required=False,
        label="Allow different checksum",
        help_text=(
            "A different EPUB may invalidate existing EPUB CFI anchors used by "
            "progress, highlights, notes, and bookmarks."
        ),
    )


class AdvancedGroupsAssignmentAdminMixin:
    @staticmethod
    def _advanced_groups_enabled():
        return server_settings.advanced_library_groups_enabled()

    def get_model_perms(self, request):
        if not self._advanced_groups_enabled():
            return {}
        return super().get_model_perms(request)

    def has_module_permission(self, request):
        return self._advanced_groups_enabled() and super().has_module_permission(request)


class BookAdminForm(forms.ModelForm):
    cover_upload = forms.FileField(
        required=False,
        label="Upload or replace cover",
        help_text="Upload a cover image.",
    )
    clear_cover = forms.BooleanField(
        required=False,
        label="Clear cover",
    )
    selected_authors = forms.ModelMultipleChoiceField(
        queryset=Author.objects.all(),
        required=False,
        label="Authors",
        widget=FilteredSelectMultiple("authors", is_stacked=False),
    )
    selected_catalog_tags = forms.ModelMultipleChoiceField(
        queryset=CatalogTag.objects.all(),
        required=False,
        label="Catalog tags",
        widget=FilteredSelectMultiple("catalog tags", is_stacked=False),
    )

    class Meta:
        model = Book
        exclude = ["authors", "catalog_tags", "cover_file"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["selected_authors"].initial = self.instance.authors.all()
            self.fields["selected_catalog_tags"].initial = (
                self.instance.catalog_tags.all()
            )

        admin_site = getattr(self, "admin_site", None)
        if admin_site is not None:
            for field_name, model_field_name in (
                ("selected_authors", "authors"),
                ("selected_catalog_tags", "catalog_tags"),
            ):
                relation = Book._meta.get_field(model_field_name).remote_field
                self.fields[field_name].widget = RelatedFieldWidgetWrapper(
                    self.fields[field_name].widget,
                    relation,
                    admin_site,
                    can_add_related=True,
                    can_change_related=True,
                    can_view_related=True,
                )

    def _save_m2m(self):
        # Explicit through models require their own synchronization below.
        self.sync_catalog_relationships()

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("cover_upload") and cleaned_data.get("clear_cover"):
            raise forms.ValidationError("Choose either a replacement cover or clear cover.")
        return cleaned_data

    def clean_cover_upload(self):
        upload = self.cleaned_data.get("cover_upload")
        if not upload:
            return upload
        try:
            self._validated_cover_upload = validate_book_cover_upload(upload)
        except InvalidBookCover as exc:
            raise forms.ValidationError(str(exc)) from exc
        return upload

    def clean_description(self):
        return sanitize_book_description(self.cleaned_data.get("description"))

    def save(self, commit=True):
        book = super().save(commit=commit)
        if commit:
            self.apply_cover_change()
        return book

    def apply_cover_change(self):
        if getattr(self, "_cover_change_applied", False):
            return
        book = self.instance
        upload = self.cleaned_data.get("cover_upload")
        if upload:
            replace_book_cover(
                book=book,
                cover=self._validated_cover_upload,
                actor=getattr(self, "_cover_actor", None),
            )
        elif self.cleaned_data.get("clear_cover"):
            clear_book_cover(book=book, actor=getattr(self, "_cover_actor", None))
        self._cover_change_applied = True

    def sync_catalog_relationships(self):
        if not self.instance.pk:
            return
        selected_authors = list(self.cleaned_data.get("selected_authors", ()))
        selected_author_ids = {author.pk for author in selected_authors}
        existing_authors = list(
            self.instance.book_authors.select_related("author").order_by("position", "id")
        )
        self.instance.book_authors.exclude(author_id__in=selected_author_ids).delete()
        existing_ids = {row.author_id for row in existing_authors}
        next_position = max((row.position for row in existing_authors), default=-1) + 1
        for author in selected_authors:
            if author.pk not in existing_ids:
                BookAuthor.objects.create(
                    book=self.instance,
                    author=author,
                    position=next_position,
                )
                next_position += 1

        selected_tag_ids = {
            tag.pk for tag in self.cleaned_data.get("selected_catalog_tags", ())
        }
        self.instance.book_catalog_tags.exclude(
            catalog_tag_id__in=selected_tag_ids
        ).delete()
        existing_tag_ids = set(
            self.instance.book_catalog_tags.values_list("catalog_tag_id", flat=True)
        )
        BookCatalogTag.objects.bulk_create(
            [
                BookCatalogTag(book=self.instance, catalog_tag_id=tag_id)
                for tag_id in selected_tag_ids - existing_tag_ids
            ]
        )


class BookSeriesInline(admin.StackedInline):
    model = BookSeries
    fields = ["series", "series_index"]
    extra = 1
    max_num = 1
    verbose_name = "Series"
    verbose_name_plural = "Series"


class BookIdentifierInline(admin.TabularInline):
    model = BookIdentifier
    fields = ["scheme", "value", "normalized_value"]
    extra = 1
    verbose_name_plural = "Book Identifiers"


class BookGroupAssignmentInline(admin.TabularInline):
    model = BookGroupAssignment
    fields = ["group", "added_by", "created_at", "updated_at"]
    readonly_fields = ["created_at", "updated_at"]
    extra = 1
    verbose_name_plural = "Book Group Assignments"


class BookSeriesListFilter(admin.SimpleListFilter):
    title = "Series"
    parameter_name = "series"

    def lookups(self, request, model_admin):
        return Series.objects.values_list("id", "name")

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        return queryset.filter(book_series__series_id=self.value())


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    form = BookAdminForm
    list_display = [
        "title_display",
        "authors_display",
        "series_display",
        "series_index_display",
        "repair_epub_link",
        "created_at_display",
    ]
    list_display_links = ["title_display"]
    list_filter = [BookSeriesListFilter, "language", "created_at"]
    search_fields = ["title", "sort_title", "checksum"]
    readonly_fields = [
        "cover_preview",
        "cover_metadata",
        "book_file",
        "file_format",
        "checksum",
        "file_size",
        "stored_epub_repair",
        "created_at",
        "updated_at",
    ]
    fieldsets = [
        ("Book identity", {"fields": ["title", "subtitle", "description"]}),
        ("Authors", {"fields": ["selected_authors"]}),
        (
            "Cover",
            {
                "fields": [
                    "cover_preview",
                    "cover_upload",
                    "clear_cover",
                    "cover_metadata",
                ]
            },
        ),
        (
            "Bibliographic",
            {
                "fields": [
                    "publisher",
                    "language",
                    "published_year",
                    "published_month",
                    "published_day",
                    "published_date_precision",
                    "selected_catalog_tags",
                ]
            },
        ),
        (
            "Stored EPUB",
            {
                "fields": [
                    "book_file",
                    "file_format",
                    "checksum",
                    "file_size",
                    "stored_epub_repair",
                ]
            },
        ),
        ("Timestamps", {"fields": ["created_at", "updated_at"]}),
    ]
    inlines = [BookSeriesInline, BookIdentifierInline, BookGroupAssignmentInline]
    change_form_template = "admin/library/book/change_form.html"

    def get_form(self, request, obj=None, change=False, **kwargs):
        form_class = super().get_form(request, obj, change=change, **kwargs)
        form_class.admin_site = self.admin_site
        return form_class

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("book_series__series")
            .prefetch_related(
                Prefetch(
                    "book_authors",
                    queryset=BookAuthor.objects.select_related("author").order_by(
                        "position", "id"
                    ),
                    to_attr="_admin_book_authors",
                )
            )
        )

    @admin.display(description="Title", ordering="title")
    def title_display(self, obj):
        return obj.title

    @admin.display(description="Authors")
    def authors_display(self, obj):
        rows = getattr(obj, "_admin_book_authors", None)
        if rows is None:
            rows = obj.book_authors.select_related("author").order_by("position", "id")
        return ", ".join(row.author.name for row in rows) or "-"

    @admin.display(description="Series", ordering="book_series__series__name")
    def series_display(self, obj):
        book_series = getattr(obj, "book_series", None)
        return book_series.series.name if book_series else "-"

    @admin.display(description="Series Index", ordering="book_series__series_index")
    def series_index_display(self, obj):
        book_series = getattr(obj, "book_series", None)
        if book_series is None or book_series.series_index is None:
            return "-"
        return book_series.series_index

    @admin.display(description="Repair EPUB")
    def repair_epub_link(self, obj):
        url = reverse("admin:library_book_repair_stored_epub", args=[obj.pk])
        return format_html('<a href="{}">Repair stored EPUB</a>', url)

    @admin.display(description="Created At", ordering="created_at")
    def created_at_display(self, obj):
        return obj.created_at

    def get_inlines(self, request, obj):
        inlines = [BookSeriesInline, BookIdentifierInline]
        if server_settings.advanced_library_groups_enabled():
            inlines.append(BookGroupAssignmentInline)
        return inlines

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        form._cover_actor = request.user
        form.apply_cover_change()

    @admin.display(description="Current cover")
    def cover_preview(self, obj):
        if not obj or not obj.cover_file:
            return "No cover stored."
        return format_html(
            '<img src="{}" alt="Current cover" style="max-height: 320px; max-width: 240px;">',
            obj.cover_file.url,
        )

    @admin.display(description="Cover metadata")
    def cover_metadata(self, obj):
        if not obj or not obj.cover_file:
            return "No cover stored."
        try:
            size = obj.cover_file.size
        except OSError:
            return "Stored cover reference exists, but the file is missing."
        return f"Stored cover present ({size:,} bytes)."

    @admin.display(description="Repair stored EPUB")
    def stored_epub_repair(self, obj):
        if not obj or not obj.pk:
            return "Save the Book before repairing its stored EPUB."
        url = reverse("admin:library_book_repair_stored_epub", args=[obj.pk])
        return format_html('<a class="button" href="{}">Repair stored EPUB</a>', url)

    def get_urls(self):
        return [
            path(
                "<path:object_id>/repair-stored-epub/",
                self.admin_site.admin_view(self.repair_stored_epub_view),
                name="library_book_repair_stored_epub",
            ),
            *super().get_urls(),
        ]

    def render_change_form(
        self,
        request,
        context,
        add=False,
        change=False,
        form_url="",
        obj=None,
    ):
        context["show_stored_epub_repair"] = bool(
            obj is not None and request.user.is_superuser
        )
        return super().render_change_form(
            request,
            context,
            add=add,
            change=change,
            form_url=form_url,
            obj=obj,
        )

    def repair_stored_epub_view(self, request, object_id):
        if not request.user.is_superuser:
            raise PermissionDenied
        book = self.get_object(request, object_id)
        if book is None:
            raise Http404

        change_url = reverse("admin:library_book_change", args=[book.pk])
        if request.method == "POST":
            form = StoredEpubRepairAdminForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    result = repair_stored_epub(
                        book=book,
                        uploaded_epub=form.cleaned_data["replacement_epub"],
                        replace_existing=form.cleaned_data["replace_existing"],
                        allow_checksum_change=form.cleaned_data[
                            "allow_checksum_change"
                        ],
                        actor=request.user,
                    )
                except StoredEpubRepairError as exc:
                    form.add_error(None, _bounded_file_repair_error(exc))
                else:
                    if result.checksum_changed:
                        messages.warning(
                            request,
                            "The stored EPUB checksum changed. Existing EPUB CFI "
                            "anchors may no longer match.",
                        )
                    messages.success(request, "Stored EPUB repaired successfully.")
                    return HttpResponseRedirect(change_url)
        else:
            form = StoredEpubRepairAdminForm()

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Repair stored EPUB",
            "book": book,
            "form": form,
            "change_url": change_url,
            "file_state": _book_file_state(book),
        }
        return TemplateResponse(
            request,
            "admin/library/book/repair_stored_epub.html",
            context,
        )


def _book_file_state(book):
    file_name = str(book.book_file.name or "")
    physical_exists = False
    if file_name:
        try:
            physical_exists = book.book_file.storage.exists(file_name)
        except Exception:
            physical_exists = False
    checksum = str(book.checksum or "")
    return {
        "has_reference": bool(file_name),
        "physical_exists": physical_exists,
        "format": str(book.file_format or "").upper(),
        "file_size": book.file_size,
        "checksum_short": f"{checksum[:12]}…" if checksum else "Not recorded",
    }


def _bounded_file_repair_error(exc):
    if isinstance(exc, ReplaceExistingConfirmationRequired):
        return "Confirm replacement of the existing stored EPUB to continue."
    if isinstance(exc, ChecksumChangeConfirmationRequired):
        return (
            "Confirm the different checksum to continue. Existing EPUB CFI "
            "anchors may no longer match."
        )
    if isinstance(exc, ChecksumCollisionError):
        return "Another Book already owns this EPUB content."
    return "Stored EPUB repair could not be completed."


class RelationshipRemovalFormSet(BaseInlineFormSet):
    removal_label = "Remove relationship"

    def add_fields(self, form, index):
        super().add_fields(form, index)
        if DELETION_FIELD_NAME in form.fields:
            form.fields[DELETION_FIELD_NAME].label = self.removal_label


class GroupMembershipContextInline(admin.TabularInline):
    model = LibraryGroupMembership
    formset = RelationshipRemovalFormSet
    template = "admin/edit_inline/contextual_tabular.html"
    fields = [
        "user_link",
        "membership_role",
        "updated_at",
    ]
    readonly_fields = fields
    extra = 0
    verbose_name = "User membership"
    verbose_name_plural = "Users and memberships — removal deletes only the membership"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="User", ordering="user__username")
    def user_link(self, obj):
        url = reverse("admin:auth_user_change", args=[obj.user_id])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_username())

    @admin.display(description="Role", ordering="is_curator")
    def membership_role(self, obj):
        return "Curator" if obj.is_curator else "Member"

class GroupBookContextInline(admin.TabularInline):
    model = BookGroupAssignment
    formset = RelationshipRemovalFormSet
    template = "admin/edit_inline/contextual_tabular.html"
    fields = [
        "book_link",
        "primary_author",
        "series_name",
    ]
    readonly_fields = fields
    extra = 0
    verbose_name = "Assigned Book"
    verbose_name_plural = "Assigned Books — removal deletes only the Group assignment"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("book__book_series__series", "added_by")
            .prefetch_related(
                Prefetch(
                    "book__book_authors",
                    queryset=BookAuthor.objects.select_related("author").order_by(
                        "position", "id"
                    ),
                    to_attr="_admin_group_book_authors",
                )
            )
        )

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="Book", ordering="book__title")
    def book_link(self, obj):
        url = reverse("admin:library_book_change", args=[obj.book_id])
        return format_html('<a href="{}">{}</a>', url, obj.book.title)

    @admin.display(description="Primary author")
    def primary_author(self, obj):
        rows = getattr(obj.book, "_admin_group_book_authors", ())
        primary = next(iter(rows), None)
        return primary.author.name if primary else "-"

    @admin.display(description="Series", ordering="book__book_series__series__name")
    def series_name(self, obj):
        book_series = getattr(obj.book, "book_series", None)
        return book_series.series.name if book_series else "-"


@admin.register(LibraryGroup)
class LibraryGroupAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    inlines = [GroupMembershipContextInline, GroupBookContextInline]

    def save_formset(self, request, form, formset, change):
        if formset.model is LibraryGroupMembership:
            formset.save(commit=False)
            removed = 0
            for membership in formset.deleted_objects:
                removed += membership_services.remove_user_from_group(
                    user=membership.user,
                    group=form.instance,
                    actor=request.user,
                )
            formset.save_m2m()
            if removed:
                self.message_user(request, f"Removed {removed} membership(s).")
            return
        if formset.model is BookGroupAssignment:
            formset.save(commit=False)
            removed = 0
            for assignment in formset.deleted_objects:
                removed += book_assignment_services.remove_book_from_group(
                    book=assignment.book,
                    group=form.instance,
                    actor=request.user,
                )
            formset.save_m2m()
            if removed:
                self.message_user(request, f"Removed {removed} Book assignment(s).")
            return
        return super().save_formset(request, form, formset, change)


class AuthorBookContextInline(admin.TabularInline):
    model = BookAuthor
    formset = RelationshipRemovalFormSet
    template = "admin/edit_inline/contextual_tabular.html"
    fields = ["book_link", "position", "series_name"]
    readonly_fields = fields
    extra = 0
    verbose_name = "Authored Book"
    verbose_name_plural = "Books by this Author — removal does not delete the Book"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "book__book_series__series"
        )

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="Book", ordering="book__title")
    def book_link(self, obj):
        url = reverse("admin:library_book_change", args=[obj.book_id])
        return format_html('<a href="{}">{}</a>', url, obj.book.title)

    @admin.display(description="Series", ordering="book__book_series__series__name")
    def series_name(self, obj):
        book_series = getattr(obj.book, "book_series", None)
        return book_series.series.name if book_series else "-"


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    search_fields = ["name", "sort_name", "normalized_name"]
    inlines = [AuthorBookContextInline]


class SeriesBookContextInline(admin.TabularInline):
    model = BookSeries
    formset = RelationshipRemovalFormSet
    template = "admin/edit_inline/contextual_tabular.html"
    fields = ["book_link", "primary_author", "series_index"]
    readonly_fields = fields
    extra = 0
    verbose_name = "Series Book"
    verbose_name_plural = "Books in this Series — removal does not delete the Book"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("book").prefetch_related(
            Prefetch(
                "book__book_authors",
                queryset=BookAuthor.objects.select_related("author").order_by(
                    "position", "id"
                ),
                to_attr="_admin_series_book_authors",
            )
        )

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="Book", ordering="book__title")
    def book_link(self, obj):
        url = reverse("admin:library_book_change", args=[obj.book_id])
        return format_html('<a href="{}">{}</a>', url, obj.book.title)

    @admin.display(description="Primary author")
    def primary_author(self, obj):
        rows = getattr(obj.book, "_admin_series_book_authors", ())
        primary = next(iter(rows), None)
        return primary.author.name if primary else "-"


@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin):
    search_fields = ["name", "sort_name", "normalized_name"]
    inlines = [SeriesBookContextInline]


class CatalogTagAdminForm(forms.ModelForm):
    class Meta:
        model = CatalogTag
        fields = ["name", "sort_name"]

    def clean_name(self):
        try:
            display_name, normalized_name = normalize_catalog_tag_name(
                self.cleaned_data["name"]
            )
        except forms.ValidationError as exc:
            raise forms.ValidationError("Enter a valid catalog tag name.") from exc
        conflict = CatalogTag.objects.filter(normalized_name=normalized_name)
        if self.instance.pk:
            conflict = conflict.exclude(pk=self.instance.pk)
        if conflict.exists():
            raise forms.ValidationError(
                "A Catalog Tag with this normalized name already exists."
            )
        self._normalized_name = normalized_name
        return display_name

    def clean_sort_name(self):
        try:
            return normalize_catalog_tag_sort_name(self.cleaned_data["sort_name"])
        except forms.ValidationError as exc:
            raise forms.ValidationError("Enter a valid sort name.") from exc

    def save(self, commit=True):
        tag = super().save(commit=False)
        tag.normalized_name = self._normalized_name
        if not tag.slug:
            tag.slug = available_catalog_tag_slug(tag.normalized_name)
        if commit:
            tag.save()
            self.save_m2m()
        return tag


class CatalogTagMergeAdminForm(forms.Form):
    fingerprint = forms.CharField(widget=forms.HiddenInput)
    survivor = forms.ModelChoiceField(
        queryset=CatalogTag.objects.none(),
        widget=forms.RadioSelect,
        label="Surviving identity",
    )
    name = forms.CharField(max_length=255, label="Final name")
    sort_name = forms.CharField(max_length=255, required=False, label="Final sort name")
    confirm = forms.BooleanField(
        required=True,
        label=(
            "I understand that the non-surviving Catalog Tags will be deleted "
            "after their Book relationships are merged."
        ),
    )

    def __init__(self, *args, plan, **kwargs):
        super().__init__(*args, **kwargs)
        selected_ids = [item.id for item in plan.tags]
        self.fields["survivor"].queryset = CatalogTag.objects.filter(
            pk__in=selected_ids
        )
        self._selected_ids = selected_ids
        if not self.is_bound:
            recommended = sorted(
                plan.tags,
                key=lambda item: (
                    -item.book_count,
                    (item.sort_name or item.name).casefold(),
                    item.name.casefold(),
                    item.id,
                ),
            )[0]
            self.initial.update(
                {
                    "fingerprint": plan.fingerprint,
                    "survivor": recommended.id,
                    "name": recommended.name,
                    "sort_name": recommended.sort_name,
                }
            )

    def clean_name(self):
        try:
            display_name, normalized_name = normalize_catalog_tag_name(
                self.cleaned_data["name"]
            )
        except forms.ValidationError as exc:
            raise forms.ValidationError("Enter a valid Catalog Tag name.") from exc
        conflict = (
            CatalogTag.objects.exclude(pk__in=self._selected_ids)
            .filter(normalized_name=normalized_name)
            .first()
        )
        if conflict is not None:
            raise forms.ValidationError(
                f'Catalog Tag "{conflict.name}" already uses that normalized name. '
                "Include it in the selection and choose it as the survivor."
            )
        return display_name


class CatalogTagBookInline(admin.TabularInline):
    model = BookCatalogTag
    fields = ["book_link", "primary_author_link", "series_link"]
    readonly_fields = ["book_link", "primary_author_link", "series_link"]
    extra = 0
    classes = ["catalog-tag-books-inline"]
    verbose_name = "Tagged book"
    verbose_name_plural = "Books carrying this tag"

    class Media:
        css = {"all": ["library/admin/catalog_tag_books.css"]}
        js = ["library/admin/catalog_tag_books.js"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("book__book_series__series", "catalog_tag")
            .prefetch_related(
                Prefetch(
                    "book__book_authors",
                    queryset=BookAuthor.objects.select_related("author").order_by(
                        "position", "id"
                    ),
                    to_attr="_admin_tag_book_authors",
                )
            )
        )

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="Book", ordering="book__title")
    def book_link(self, obj):
        url = reverse("admin:library_book_change", args=[obj.book_id])
        return format_html('<a href="{}">{}</a>', url, obj.book.title)

    @admin.display(description="Primary author")
    def primary_author_link(self, obj):
        rows = getattr(obj.book, "_admin_tag_book_authors", None)
        if rows is None:
            rows = obj.book.book_authors.select_related("author").order_by(
                "position", "id"
            )
        primary = next(iter(rows), None)
        if primary is None:
            return "-"
        url = reverse("admin:library_author_change", args=[primary.author_id])
        return format_html('<a href="{}">{}</a>', url, primary.author.name)

    @admin.display(description="Series")
    def series_link(self, obj):
        book_series = getattr(obj.book, "book_series", None)
        if book_series is None:
            return "-"
        url = reverse("admin:library_series_change", args=[book_series.series_id])
        if book_series.series_index is None:
            return format_html('<a href="{}">{}</a>', url, book_series.series.name)
        return format_html(
            '<a href="{}">{}</a> <span class="catalog-tag-series-index">#{}</span>',
            url,
            book_series.series.name,
            book_series.series_index,
        )


@admin.register(CatalogTag)
class CatalogTagAdmin(admin.ModelAdmin):
    form = CatalogTagAdminForm
    fields = ["name", "sort_name", "normalized_name", "slug"]
    inlines = [CatalogTagBookInline]
    list_display = ["name", "book_count"]
    list_display_links = ["name"]
    readonly_fields = ["normalized_name", "slug"]
    search_fields = ["name", "normalized_name"]
    actions = ["merge_selected_tags"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_book_count=Count("book_catalog_tags"))

    @admin.display(description="Books", ordering="_book_count")
    def book_count(self, obj):
        return obj._book_count

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not request.user.is_superuser:
            actions.pop("merge_selected_tags", None)
        return actions

    @admin.action(description="Merge selected Catalog Tags")
    def merge_selected_tags(self, request, queryset):
        if not request.user.is_superuser:
            raise PermissionDenied
        if request.POST.get("select_across") == "1":
            self.message_user(
                request,
                "Select the Catalog Tags explicitly; merging across every result "
                "page is not supported.",
                level=messages.ERROR,
            )
            return None
        selected_ids = request.POST.getlist(ACTION_CHECKBOX_NAME)
        try:
            plan = build_catalog_tag_merge_plan(selected_ids)
        except CatalogTagMergeSelectionError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
            return None

        if request.POST.get("confirm_merge"):
            form = CatalogTagMergeAdminForm(request.POST, plan=plan)
            if form.is_valid():
                try:
                    result = merge_catalog_tags(
                        tag_ids=selected_ids,
                        survivor_id=form.cleaned_data["survivor"].pk,
                        final_name=form.cleaned_data["name"],
                        final_sort_name=form.cleaned_data["sort_name"],
                        expected_fingerprint=form.cleaned_data["fingerprint"],
                        actor=request.user,
                    )
                except CatalogTagMergePlanStale as exc:
                    self.message_user(request, str(exc), level=messages.ERROR)
                    form = CatalogTagMergeAdminForm(plan=plan)
                except CatalogTagMergeNameConflict as exc:
                    form.add_error("name", str(exc))
                except CatalogTagMergeError as exc:
                    form.add_error(None, str(exc))
                else:
                    self.log_change(
                        request,
                        result.survivor,
                        (
                            f"Merged {result.source_tags_deleted} Catalog Tag(s); "
                            f"preserved {result.books_affected} Book relationship(s); "
                            "collapsed "
                            f"{result.duplicate_relationships_collapsed} overlap(s)."
                        ),
                    )
                    self.message_user(
                        request,
                        (
                            f'Merged into "{result.survivor.name}": '
                            f"{result.source_tags_deleted} source tag(s) deleted, "
                            f"{result.books_affected} Book(s) preserved, and "
                            f"{result.duplicate_relationships_collapsed} "
                            "overlap(s) collapsed."
                        ),
                        level=messages.SUCCESS,
                    )
                    return HttpResponseRedirect(
                        reverse("admin:library_catalogtag_changelist")
                    )
        else:
            form = CatalogTagMergeAdminForm(plan=plan)

        recommended = sorted(
            plan.tags,
            key=lambda item: (
                -item.book_count,
                (item.sort_name or item.name).casefold(),
                item.name.casefold(),
                item.id,
            ),
        )[0]
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Merge Catalog Tags",
            "plan": plan,
            "form": form,
            "selected_ids": selected_ids,
            "action_checkbox_name": ACTION_CHECKBOX_NAME,
            "recommended_survivor_id": recommended.id,
        }
        return TemplateResponse(
            request,
            "admin/library/catalogtag/merge_selected.html",
            context,
        )


class LibraryGroupMembershipAdmin(
    AdvancedGroupsAssignmentAdminMixin,
    admin.ModelAdmin,
):
    # Retained temporarily as a cleanup candidate. Membership operations now live
    # on contextual User and Library Group Admin pages; this class is unregistered.
    list_display = ["user", "group", "is_curator", "created_at", "updated_at"]
    list_display_links = ["user"]
    list_filter = ["group", "is_curator"]
    search_fields = ["user__username", "user__email", "group__name"]
    readonly_fields = [
        "id",
        "user",
        "group",
        "created_at",
        "updated_at",
    ]
    actions = ["remove_assignments"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "group")

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ["id", "created_at", "updated_at"]
        return self.readonly_fields

    def get_fields(self, request, obj=None):
        fields = ["user", "group"]
        if self._can_edit_curator(obj):
            fields.append("is_curator")
        if obj is not None:
            fields.extend(["created_at", "updated_at"])
        return fields

    @staticmethod
    def _can_edit_curator(obj):
        return bool(
            obj is not None
            and server_settings.advanced_library_groups_enabled()
            and not is_public_group(obj.group)
        )

    def save_model(self, request, obj, form, change):
        if change:
            if self._can_edit_curator(obj):
                membership_services.set_group_membership_curator(
                    membership=obj,
                    is_curator=obj.is_curator,
                    actor=request.user,
                )
            return
        membership = membership_services.add_user_to_group(
            user=obj.user,
            group=obj.group,
            is_curator=obj.is_curator,
            actor=request.user,
        )
        obj.pk = membership.pk
        obj.is_curator = membership.is_curator
        obj.created_at = membership.created_at
        obj.updated_at = membership.updated_at

    def delete_model(self, request, obj):
        membership_services.remove_user_from_group(
            user=obj.user,
            group=obj.group,
            actor=request.user,
        )

    @admin.action(description="Remove selected user-group assignments")
    def remove_assignments(self, request, queryset):
        removed = 0
        memberships = list(queryset.select_related("user", "group"))
        for membership in memberships:
            removed += membership_services.remove_user_from_group(
                user=membership.user,
                group=membership.group,
                actor=request.user,
            )
        self.message_user(request, f"Removed {removed} user-group assignment(s).")

class BookGroupAssignmentAdmin(
    AdvancedGroupsAssignmentAdminMixin,
    admin.ModelAdmin,
):
    # Retained temporarily as a cleanup candidate. Assignment operations now live
    # on contextual Library Group Admin pages; this class is unregistered.
    list_display = ["book", "group", "added_by", "created_at", "updated_at"]
    list_display_links = ["book"]
    list_filter = ["group"]
    search_fields = ["book__title", "book__checksum", "group__name", "added_by__username"]
    readonly_fields = ["id", "book", "group", "added_by", "created_at", "updated_at"]
    actions = ["remove_assignments"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("book", "group", "added_by")

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ["id", "added_by", "created_at", "updated_at"]
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        if change:
            return
        assignment = book_assignment_services.add_book_to_group(
            book=obj.book,
            group=obj.group,
            actor=request.user,
        )
        obj.pk = assignment.pk
        obj.added_by = assignment.added_by
        obj.created_at = assignment.created_at
        obj.updated_at = assignment.updated_at

    def delete_model(self, request, obj):
        book_assignment_services.remove_book_from_group(
            book=obj.book,
            group=obj.group,
            actor=request.user,
        )

    @admin.action(description="Remove selected book-group assignments")
    def remove_assignments(self, request, queryset):
        removed = 0
        assignments = list(queryset.select_related("book", "group"))
        for assignment in assignments:
            removed += book_assignment_services.remove_book_from_group(
                book=assignment.book,
                group=assignment.group,
                actor=request.user,
            )
        self.message_user(request, f"Removed {removed} book-group assignment(s).")

    def has_change_permission(self, request, obj=None):
        return False


_install_library_admin_app_list_ordering()
