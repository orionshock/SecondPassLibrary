from django.contrib import admin
from django.contrib.admin import DateFieldListFilter
from django.db.models import Count

from .models import Author, Book, BookFile, BookMetadata, Series


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ['name', 'book_count', 'created_at', 'updated_at']
    search_fields = ['name', 'biography']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at']

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(_book_count=Count('books', distinct=True))

    @admin.display(ordering='_book_count', description='Books')
    def book_count(self, obj):
        return obj._book_count


@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin):
    list_display = ['name', 'book_count', 'created_at', 'updated_at']
    search_fields = ['name', 'summary']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at']

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(_book_count=Count('books', distinct=True))

    @admin.display(ordering='_book_count', description='Books')
    def book_count(self, obj):
        return obj._book_count


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['title', 'author_list', 'series', 'series_index', 'created_at']
    search_fields = ['title', 'subtitle', 'authors__name', 'series__name']
    list_filter = [
        'series',
        ('created_at', DateFieldListFilter),
    ]
    filter_horizontal = ['authors']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        (
            None,
            {
                'fields': (
                    'title',
                    'subtitle',
                    'authors',
                    ('series', 'series_index'),
                    'summary',
                )
            },
        ),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

    @admin.display(description='Authors')
    def author_list(self, obj):
        return obj.author_list()


@admin.register(BookMetadata)
class BookMetadataAdmin(admin.ModelAdmin):
    list_display = ['book', 'publisher', 'language', 'published_date', 'isbn']
    search_fields = ['book__title', 'book__authors__name', 'isbn', 'publisher']
    list_filter = [('created_at', DateFieldListFilter)]
    raw_id_fields = ['book']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        (None, {'fields': ('book',)}),
        ('Publication', {'fields': ('publisher', 'language', 'published_date', 'isbn')}),
        ('Subjects', {'fields': ('subjects',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(BookFile)
class BookFileAdmin(admin.ModelAdmin):
    list_display = [
        'book',
        'file_format',
        'checksum_short',
        'file_size_human',
        'source_filename',
        'created_at',
    ]
    search_fields = ['book__title', 'book__authors__name', 'checksum', 'source_filename']
    list_filter = [
        'format',
        ('created_at', DateFieldListFilter),
    ]
    raw_id_fields = ['book']
    readonly_fields = ['created_at', 'updated_at', 'checksum', 'file_size', 'source_filename']

    fieldsets = (
        (None, {'fields': ('book', 'file', 'format')}),
        ('File details', {'fields': ('checksum', 'file_size', 'source_filename')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

    @admin.display(description='Format', ordering='format')
    def file_format(self, obj):
        return obj.get_format_display()

    @admin.display(description='Checksum')
    def checksum_short(self, obj):
        return obj.checksum_short()

    @admin.display(description='Size', ordering='file_size')
    def file_size_human(self, obj):
        return obj.file_size_human()
