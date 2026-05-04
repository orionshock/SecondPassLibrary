from django.contrib import admin
from django.contrib.admin import DateFieldListFilter
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html

from .models import Author, Book, BookFile, Series, ImportJob, ImportJobItem


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


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
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
    readonly_fields = ["created_at", "updated_at"]

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
            "Bibliographic",
            {"fields": ("publisher", "language", "published_date", "isbn", "subjects")},
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Authors")
    def author_list(self, obj):
        return obj.author_list()


@admin.register(BookFile)
class BookFileAdmin(admin.ModelAdmin):
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


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    """
    Import jobs are created by the import API/services.

    Admin is intended for inspection and limited repair/debugging only.
    """

    list_display = [
        "id",
        "user",
        "status",
        "source_type",
        "source_filename",
        "total_found",
        "imported_count",
        "duplicate_count",
        "failed_count",
        "created_at",
    ]
    list_filter = ["status", "source_type", ("created_at", DateFieldListFilter)]
    search_fields = ["id", "source_filename", "user__username", "user__email"]
    readonly_fields = [
        "admin_note",
        "created_at",
        "updated_at",
        "user",
        "source_type",
        "source_filename",
        "internal_staged_path",
        "total_found",
        "imported_count",
        "duplicate_count",
        "failed_count",
    ]

    fieldsets = (
        ("Note", {"fields": ("admin_note",)}),
        (None, {"fields": ("user", "source_type", "source_filename")}),
        ("Status", {"fields": ("status", "message")}),
        (
            "Counts",
            {
                "fields": (
                    "total_found",
                    "imported_count",
                    "duplicate_count",
                    "failed_count",
                )
            },
        ),
        ("Diagnostics", {"fields": ("internal_staged_path",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="")
    def admin_note(self, obj: ImportJob) -> str:
        return "Import jobs are created by the import API/upload workflow. Edit only for inspection or limited repair/debugging."

    @admin.display(description="Internal staged path")
    def internal_staged_path(self, obj: ImportJob) -> str:
        return obj.staged_path or ""


@admin.register(ImportJobItem)
class ImportJobItemAdmin(admin.ModelAdmin):
    """
    Import job items are created by the import API/services.

    Admin is intended for inspection and limited repair/debugging only.
    """

    list_display = [
        "id",
        "job",
        "status",
        "source_name",
        "book",
        "book_file",
        "created_at",
    ]
    list_filter = ["status", ("created_at", DateFieldListFilter)]
    search_fields = ["id", "job__id", "source_name", "book__title", "book_file__checksum"]
    raw_id_fields = ["book", "book_file"]
    readonly_fields = [
        "admin_note",
        "created_at",
        "updated_at",
        "job",
        "source_name",
    ]

    fieldsets = (
        ("Note", {"fields": ("admin_note",)}),
        (None, {"fields": ("job", "source_name")}),
        ("Repair", {"fields": ("status", "message", "book", "book_file")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="")
    def admin_note(self, obj: ImportJobItem) -> str:
        return "Import job items are created by the import API/upload workflow. Edit only for inspection or limited repair/debugging."
