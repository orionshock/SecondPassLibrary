from typing import Any, cast

from django import forms
from django.contrib import admin
from django.contrib.admin import DateFieldListFilter
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html

from .book_file_services import BookFileUploadMetadata, inspect_epub_upload
from .cover_services import set_book_cover_from_bytes, MAX_COVER_BYTES
from .models import (
    Author,
    Book,
    BookFile,
    Series,
    BookIdentifier,
    LibraryGroup,
    LibraryGroupMembership,
    BookGroupAssignment,
)
from .public_group import is_public_group


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ["name", "book_count", "created_at", "updated_at"]
    search_fields = ["name", "biography"]
    ordering = ["name"]
    readonly_fields = ["created_at", "updated_at"]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(_book_count=Count("books", distinct=True))

    @admin.display(ordering="_book_count", description="Books")
    def book_count(self, obj):
        return obj._book_count


@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin):
    list_display = ["name", "book_count", "created_at", "updated_at"]
    search_fields = ["name", "summary"]
    ordering = ["name"]
    readonly_fields = ["created_at", "updated_at"]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(_book_count=Count("books", distinct=True))

    @admin.display(ordering="_book_count", description="Books")
    def book_count(self, obj):
        return obj._book_count


class BookIdentifierInline(admin.TabularInline):
    model = BookIdentifier
    extra = 0
    fields = ["scheme", "value", "source", "is_primary", "created_at", "updated_at"]
    readonly_fields = ["created_at", "updated_at"]


class BookGroupAssignmentInline(admin.TabularInline):
    model = BookGroupAssignment
    extra = 0
    raw_id_fields = ["group", "added_by"]
    fields = ["group", "added_by", "created_at", "updated_at"]
    readonly_fields = ["created_at", "updated_at"]


class BookAdminForm(forms.ModelForm):
    cover_upload = forms.FileField(
        required=False,
        help_text="Upload a cover image (JPEG/PNG/WebP). Stored as original validated bytes.",
    )
    clear_cover = forms.BooleanField(
        required=False,
        initial=False,
        help_text="Remove the stored cover image and clear cover metadata.",
    )

    class Meta:
        model = Book
        fields = "__all__"

    def clean_cover_upload(self):
        f = self.cleaned_data.get("cover_upload")
        if f is None:
            return None
        size = getattr(f, "size", None)
        if isinstance(size, int) and size > MAX_COVER_BYTES:
            raise forms.ValidationError("Cover image exceeds 5MB limit.")
        return f


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    form = BookAdminForm
    list_display = [
        "title",
        "author_list",
        "series",
        "series_index",
        "publisher",
        "language",
        "published_date",
        "created_at",
    ]
    search_fields = [
        "title",
        "subtitle",
        "authors__name",
        "series__name",
        "publisher",
        "isbn",
    ]
    list_filter = [
        "series",
        "language",
        ("created_at", DateFieldListFilter),
    ]
    filter_horizontal = ["authors"]
    readonly_fields = [
        "cover_preview",
        "cover_internal_path",
        "cover_source",
        "cover_mime",
        "cover_width",
        "cover_height",
        "created_at",
        "updated_at",
    ]
    inlines = [BookIdentifierInline, BookGroupAssignmentInline]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "subtitle",
                    "authors",
                    ("series", "series_index"),
                    "summary",
                )
            },
        ),
        (
            "Cover",
            {
                "fields": (
                    "cover_preview",
                    "cover_upload",
                    "clear_cover",
                    "cover_source",
                    "cover_mime",
                    ("cover_width", "cover_height"),
                    "cover_internal_path",
                )
            },
        ),
        (
            "Bibliographic",
            {"fields": ("publisher", "language", "published_date", "isbn", "subjects")},
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def has_add_permission(self, request):
        # Books are file-backed and created via import only. Django admin remains
        # a service hatch for editing existing records, not creating new books.
        return False

    @admin.display(description="Authors")
    def author_list(self, obj):
        return obj.author_list()

    @admin.display(description="Cover")
    def cover_preview(self, obj: Book) -> str:
        cover = getattr(obj, "cover_file", None)
        if not cover:
            return format_html("<span class='muted'>No cover.</span>")
        try:
            url = cover.url
        except Exception:
            url = ""
        if not url:
            return format_html("<span class='muted'>Cover missing.</span>")
        return format_html(
            '<img src="{}" alt="Cover" style="max-height: 240px; max-width: 180px; border: 1px solid #ccc; border-radius: 6px;" />',
            url,
        )

    @admin.display(description="Cover stored path")
    def cover_internal_path(self, obj: Book) -> str:
        cover = getattr(obj, "cover_file", None)
        return cover.name if cover else ""

    def save_model(self, request, obj: Book, form, change):
        super().save_model(request, obj, form, change)

        clear_cover = bool(form.cleaned_data.get("clear_cover"))
        cover_upload = form.cleaned_data.get("cover_upload")

        if clear_cover and getattr(obj, "cover_file", None):
            try:
                obj.cover_file.delete(save=False)
            except Exception:
                pass
            obj.cover_source = ""
            obj.cover_mime = ""
            obj.cover_width = None
            obj.cover_height = None
            # Clear the FileField value; Django stores empty FileFields as "".
            setattr(cast(Any, obj), "cover_file", "")
            obj.save(
                update_fields=[
                    "cover_file",
                    "cover_source",
                    "cover_mime",
                    "cover_width",
                    "cover_height",
                    "updated_at",
                ]
            )
            return

        if cover_upload is None:
            return

        try:
            data = cover_upload.read()
        except Exception:
            return

        # Validate + store via shared service helper (content-addressed filename).
        try:
            set_book_cover_from_bytes(
                book=obj,
                data=data,
                source="manual",
                source_filename=getattr(cover_upload, "name", None),
                save=True,
            )
        except ValueError:
            # Treat invalid cover upload as non-fatal; operator can retry.
            return


class BookFileAdminForm(forms.ModelForm):
    computed_upload_metadata: BookFileUploadMetadata | None = None

    class Meta:
        model = BookFile
        fields = "__all__"

    def clean_file(self):
        upload = self.cleaned_data.get("file")
        if not upload:
            return upload

        try:
            metadata = inspect_epub_upload(upload)
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc

        duplicate = BookFile.objects.filter(checksum=metadata.checksum)
        if self.instance and self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError(
                "An EPUB with this checksum is already stored."
            )

        self.computed_upload_metadata = metadata
        return upload

    def clean(self):
        cleaned_data = super().clean()
        book = cleaned_data.get("book")
        if book is None:
            return cleaned_data

        existing = BookFile.objects.filter(book=book)
        if self.instance and self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            self.add_error("book", "Selected book already has a stored file.")

        return cleaned_data


@admin.register(BookFile)
class BookFileAdmin(admin.ModelAdmin):
    form = BookFileAdminForm
    list_display = [
        "book",
        "file_format",
        "checksum_short",
        "file_size_human",
        "source_filename",
        "created_at",
    ]
    search_fields = [
        "book__title",
        "book__authors__name",
        "checksum",
        "source_filename",
    ]
    list_filter = [
        "format",
        ("created_at", DateFieldListFilter),
    ]
    raw_id_fields = ["book"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "checksum",
        "file_size",
        "file_size_human",
        "source_filename",
        "internal_stored_path",
        "download_epub_link",
    ]

    add_fieldsets = (
        (None, {"fields": ("book", "file", "format")}),
        ("File details", {"fields": ("checksum", "file_size", "source_filename")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    change_fieldsets = (
        (None, {"fields": ("book", "format")}),
        ("Download", {"fields": ("download_epub_link",)}),
        (
            "File details",
            {"fields": ("checksum", "file_size", "file_size_human", "source_filename")},
        ),
        ("Diagnostics", {"fields": ("internal_stored_path",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return self.add_fieldsets
        return self.change_fieldsets

    def save_model(self, request, obj: BookFile, form, change):
        metadata = getattr(form, "computed_upload_metadata", None)
        if metadata is not None:
            obj.checksum = metadata.checksum
            obj.file_size = metadata.file_size
            obj.source_filename = metadata.source_filename
        super().save_model(request, obj, form, change)

    @admin.display(description="Format", ordering="format")
    def file_format(self, obj):
        return obj.get_format_display()

    @admin.display(description="Checksum")
    def checksum_short(self, obj):
        return obj.checksum_short()

    @admin.display(description="Size", ordering="file_size")
    def file_size_human(self, obj):
        return obj.file_size_human()

    @admin.display(description="Internal stored path")
    def internal_stored_path(self, obj: BookFile) -> str:
        # Storage-relative path (never an absolute filesystem path).
        return obj.file.name if obj.file else ""

    @admin.display(description="Download EPUB")
    def download_epub_link(self, obj: BookFile) -> str:
        url = reverse("library:bookfile-download", args=[obj.pk])
        return format_html('<a href="{}">Download EPUB</a>', url)


@admin.register(LibraryGroup)
class LibraryGroupAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name", "description"]
    list_filter = [("created_at", DateFieldListFilter)]
    readonly_fields = ["created_at", "updated_at"]

    def has_delete_permission(self, request, obj=None):
        if obj is not None and is_public_group(obj):
            return False
        return super().has_delete_permission(request, obj=obj)

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj=obj))
        if obj is not None and is_public_group(obj):
            fields.extend(["name"])
        return fields


@admin.register(LibraryGroupMembership)
class LibraryGroupMembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "group", "is_curator", "created_at"]
    search_fields = ["user__username", "user__email", "group__name"]
    list_filter = ["is_curator", ("created_at", DateFieldListFilter)]
    raw_id_fields = ["user", "group"]
    readonly_fields = ["created_at", "updated_at"]

    def has_delete_permission(self, request, obj=None):
        # Public membership may be removed if another group remains.
        return super().has_delete_permission(request, obj=obj)

    def has_add_permission(self, request):
        # Membership creation should be managed via services/policies later.
        return super().has_add_permission(request)


@admin.register(BookGroupAssignment)
class BookGroupAssignmentAdmin(admin.ModelAdmin):
    list_display = ["book", "group", "added_by", "created_at"]
    search_fields = ["book__title", "group__name", "added_by__username"]
    list_filter = [("created_at", DateFieldListFilter), "group"]
    raw_id_fields = ["book", "group", "added_by"]
    readonly_fields = ["created_at", "updated_at"]
