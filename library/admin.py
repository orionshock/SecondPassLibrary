from django.contrib import admin

from library.groups import services as group_services

from .models import Book, BookGroupAssignment, CatalogTag, LibraryGroup


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    search_fields = ["title", "sort_title", "checksum"]


@admin.register(LibraryGroup)
class LibraryGroupAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(CatalogTag)
class CatalogTagAdmin(admin.ModelAdmin):
    search_fields = ["name", "normalized_name"]


@admin.register(BookGroupAssignment)
class BookGroupAssignmentAdmin(admin.ModelAdmin):
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
        for assignment in queryset.select_related("book", "group"):
            removed += group_services.remove_book_from_group(
                book=assignment.book,
                group=assignment.group,
                actor=request.user,
            )
        self.message_user(request, f"Removed {removed} book-group assignment(s).")

    def has_change_permission(self, request, obj=None):
        return False
