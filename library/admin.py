from django.contrib import admin

from .models import Author, Book, BookFile, BookMetadata, Series


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at', 'updated_at']
    search_fields = ['name']


@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at', 'updated_at']
    search_fields = ['name']


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['title', 'series', 'created_at', 'updated_at']
    search_fields = ['title', 'subtitle']
    list_filter = ['series']
    filter_horizontal = ['authors']


@admin.register(BookMetadata)
class BookMetadataAdmin(admin.ModelAdmin):
    list_display = ['book', 'publisher', 'language', 'published_date']
    search_fields = ['book__title', 'isbn']


@admin.register(BookFile)
class BookFileAdmin(admin.ModelAdmin):
    list_display = ['book', 'format', 'checksum', 'file_size', 'source_filename', 'created_at']
    search_fields = ['book__title', 'checksum', 'source_filename']
