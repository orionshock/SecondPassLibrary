from django.contrib import admin

from .models import Book, CatalogTag, LibraryGroup


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    search_fields = ["title", "sort_title", "checksum"]


@admin.register(LibraryGroup)
class LibraryGroupAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(CatalogTag)
class CatalogTagAdmin(admin.ModelAdmin):
    search_fields = ["name", "normalized_name"]
