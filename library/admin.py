from types import MethodType

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.widgets import FilteredSelectMultiple, RelatedFieldWidgetWrapper
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseRedirect
from django.db.models import Prefetch
from django.utils.html import format_html
from django.template.response import TemplateResponse
from django.urls import path, reverse

from core import server_settings
from library.file_repair import (
    ChecksumChangeConfirmationRequired,
    ChecksumCollisionError,
    ReplaceExistingConfirmationRequired,
    StoredEpubRepairError,
    repair_stored_epub,
)
from library.cover_services import set_book_cover_from_bytes
from library.groups import services as group_services
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

    def has_view_permission(self, request, obj=None):
        return self._advanced_groups_enabled() and super().has_view_permission(
            request,
            obj=obj,
        )

    def has_add_permission(self, request):
        return self._advanced_groups_enabled() and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return self._advanced_groups_enabled() and super().has_change_permission(
            request,
            obj=obj,
        )

    def has_delete_permission(self, request, obj=None):
        return self._advanced_groups_enabled() and super().has_delete_permission(
            request,
            obj=obj,
        )


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

    def save(self, commit=True):
        book = super().save(commit=commit)
        if commit:
            self.apply_cover_change()
        return book

    def apply_cover_change(self):
        if getattr(self, "_cover_change_applied", False):
            return
        book = self.instance
        old_cover_name = str(book.cover_file.name or "")
        upload = self.cleaned_data.get("cover_upload")
        if upload:
            set_book_cover_from_bytes(book=book, data=upload.read())
        elif self.cleaned_data.get("clear_cover"):
            book.cover_file = ""
            book.save(update_fields=["cover_file", "updated_at"])
        new_cover_name = str(book.cover_file.name or "")
        if old_cover_name and old_cover_name != new_cover_name:
            storage = Book._meta.get_field("cover_file").storage
            if not Book.objects.filter(cover_file=old_cover_name).exists():
                storage.delete(old_cover_name)
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


@admin.register(LibraryGroup)
class LibraryGroupAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    search_fields = ["name", "sort_name"]


@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin):
    search_fields = ["name", "sort_name"]


@admin.register(CatalogTag)
class CatalogTagAdmin(admin.ModelAdmin):
    search_fields = ["name", "normalized_name"]


@admin.register(LibraryGroupMembership)
class LibraryGroupMembershipAdmin(
    AdvancedGroupsAssignmentAdminMixin,
    admin.ModelAdmin,
):
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
                group_services.set_group_membership_curator(
                    membership=obj,
                    is_curator=obj.is_curator,
                )
            return
        membership = group_services.add_user_to_group(
            user=obj.user,
            group=obj.group,
            is_curator=obj.is_curator,
        )
        obj.pk = membership.pk
        obj.is_curator = membership.is_curator
        obj.created_at = membership.created_at
        obj.updated_at = membership.updated_at

    def delete_model(self, request, obj):
        group_services.remove_user_from_group(user=obj.user, group=obj.group)

    @admin.action(description="Remove selected user-group assignments")
    def remove_assignments(self, request, queryset):
        removed = 0
        memberships = list(queryset.select_related("user", "group"))
        for membership in memberships:
            removed += group_services.remove_user_from_group(
                user=membership.user,
                group=membership.group,
            )
        self.message_user(request, f"Removed {removed} user-group assignment(s).")

@admin.register(BookGroupAssignment)
class BookGroupAssignmentAdmin(
    AdvancedGroupsAssignmentAdminMixin,
    admin.ModelAdmin,
):
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
        assignment = group_services.add_book_to_group(
            book=obj.book,
            group=obj.group,
            actor=request.user,
        )
        obj.pk = assignment.pk
        obj.added_by = assignment.added_by
        obj.created_at = assignment.created_at
        obj.updated_at = assignment.updated_at

    def delete_model(self, request, obj):
        group_services.remove_book_from_group(
            book=obj.book,
            group=obj.group,
            actor=request.user,
        )

    @admin.action(description="Remove selected book-group assignments")
    def remove_assignments(self, request, queryset):
        removed = 0
        assignments = list(queryset.select_related("book", "group"))
        for assignment in assignments:
            removed += group_services.remove_book_from_group(
                book=assignment.book,
                group=assignment.group,
                actor=request.user,
            )
        self.message_user(request, f"Removed {removed} book-group assignment(s).")

    def has_change_permission(self, request, obj=None):
        return False


_install_library_admin_app_list_ordering()
